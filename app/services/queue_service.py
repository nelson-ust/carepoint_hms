# app/services/queue_service.py
from __future__ import annotations

"""
    Service layer for queue ticket lifecycle and service-point worklists.

    Lifecycle
    ---------
    WAITING  -> CALLED  -> SERVING  -> SERVED
                                    \-> MISSED
                                    \-> TRANSFERRED
    WAITING  -> CANCELLED
    CALLED   -> CANCELLED
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import QueueStatus, VisitFlowStepStatus, VisitStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import QueueTicket, Visit, VisitFlowStep
from app.repositories.queue_repository import QueueRepository
from app.utils.security_event_util import record_security_event
from app.utils.visit_routing import end_visit, route_visit_to_next_sdp


_TERMINAL = {QueueStatus.SERVED, QueueStatus.CANCELLED, QueueStatus.TRANSFERRED, QueueStatus.MISSED}


class QueueService:
    """
    Orchestrates queue ticket transitions and service-point worklists.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = QueueRepository(db)

    # ============================================================
    # LISTINGS
    # ============================================================

    def list_for_service_point(
        self,
        service_delivery_point_id: int,
        *,
        statuses: Optional[list[str]] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[QueueTicket], int]:
        sdp = self.repository.get_service_delivery_point(service_delivery_point_id)
        if not sdp:
            raise NotFoundError(
                message="Service delivery point not found.",
                detail={"service_delivery_point_id": service_delivery_point_id},
            )
        normalized = None
        if statuses:
            normalized = [QueueStatus(s.strip().upper()) for s in statuses]
        
        items, total = self.repository.list_for_service_point(
            service_delivery_point_id, statuses=normalized, skip=skip, limit=limit
        )
        self._populate_history(items)
        return items, total

    def get_worklist(self, service_delivery_point_id: int) -> dict:
        sdp = self.repository.get_service_delivery_point(service_delivery_point_id)
        if not sdp:
            raise NotFoundError(
                message="Service delivery point not found.",
                detail={"service_delivery_point_id": service_delivery_point_id},
            )

        waiting, _ = self.repository.list_for_service_point(
            service_delivery_point_id,
            statuses=[QueueStatus.WAITING, QueueStatus.CALLED],
            skip=0,
            limit=200,
        )
        serving, _ = self.repository.list_for_service_point(
            service_delivery_point_id,
            statuses=[QueueStatus.SERVING],
            skip=0,
            limit=20,
        )
        
        self._populate_history(waiting)
        self._populate_history(serving)
        
        served_today = self.repository.count_today_by_status(service_delivery_point_id, QueueStatus.SERVED)
        cancelled_today = self.repository.count_today_by_status(service_delivery_point_id, QueueStatus.CANCELLED)

        return {
            "service_delivery_point_id": sdp.id,
            "service_delivery_point_name": sdp.name,
            "waiting": waiting,
            "serving": serving,
            "served_today": served_today,
            "cancelled_today": cancelled_today,
        }

    def _populate_history(self, tickets: list[QueueTicket]) -> None:
        """
        Injects historical step information into each ticket object for the frontend.
        """
        for t in tickets:
            previous_tickets = self.repository.get_previous_tickets_for_visit(t.visit_id, t.id)
            t.previous_steps = []
            
            for p in previous_tickets:
                services = []
                # Handle cases where relationship might not be loaded or name is missing
                raw_name = getattr(p.service_delivery_point, "name", "Unknown Service Point")
                sdp_name = raw_name.lower()
                
                # Heuristic for "Services Provided" based on SDP name
                if any(x in sdp_name for x in ["triage", "nursing", "vitals"]):
                    services.append("Vitals & Triage")
                elif any(x in sdp_name for x in ["consult", "clinic", "doctor", "physician"]):
                    services.append("Clinical Consultation")
                elif "lab" in sdp_name:
                    services.append("Laboratory Investigation")
                elif "pharmacy" in sdp_name:
                    services.append("Pharmacy Dispensing")
                elif any(x in sdp_name for x in ["radiology", "imaging", "scan", "xray"]):
                    services.append("Radiology/Imaging")
                elif any(x in sdp_name for x in ["billing", "cashier", "account", "payment"]):
                    services.append("Payment & Billing")
                elif any(x in sdp_name for x in ["front", "reception", "records"]):
                    services.append("Patient Registration/Check-in")
                
                # Fallback if no heuristic matched but we want to show something
                if not services:
                    services.append(f"Service at {raw_name}")
                
                t.previous_steps.append({
                    "service_delivery_point_id": p.service_delivery_point_id,
                    "service_delivery_point_name": raw_name,
                    "status": str(p.status),
                    "services_provided": services,
                    "started_at": p.service_started_at,
                    "ended_at": p.service_ended_at,
                })

    def list_for_visit(self, visit_id: int) -> list[QueueTicket]:
        return self.repository.list_for_visit(visit_id)

    def get_ticket(self, ticket_id: int) -> QueueTicket:
        ticket = self.repository.get_required_by_id(ticket_id)
        self._populate_history([ticket])
        return ticket

    def resolve_user_sdp_ids(self, user) -> list[int]:
        """
        Pull the assigned SDP IDs from the caller's StaffProfile.
        """
        profile = getattr(user, "staff_profile", None)
        if profile is None:
            return []
        
        # Access the property I added to all_models
        return getattr(profile, "assigned_sdp_ids", [])

    def get_my_worklist(self, user, sdp_id: Optional[int] = None) -> dict:
        """
        Worklist for the caller's assigned SDP(s).
        
        If sdp_id is provided, it returns the worklist for that specific point
        (verifying the user is assigned to it).
        
        If sdp_id is NOT provided, it defaults to the first assigned point.
        """
        assigned_ids = self.resolve_user_sdp_ids(user)
        if not assigned_ids:
            raise BadRequestError(
                message="You are not assigned to any service delivery point.",
                detail={"user_id": getattr(user, "id", None)},
            )
        
        target_id = sdp_id or assigned_ids[0]
        
        if target_id not in assigned_ids:
            raise BadRequestError(
                message="You are not assigned to the requested service delivery point.",
                detail={"requested_sdp_id": target_id, "assigned_sdp_ids": assigned_ids}
            )
            
        return self.get_worklist(target_id)

    # ============================================================
    # TRANSITIONS
    # ============================================================

    def call_ticket(self, ticket_id: int, *, actor_user_id: Optional[int] = None) -> QueueTicket:
        ticket = self.repository.get_required_by_id(ticket_id)
        self._assert_active(ticket)
        if ticket.status not in {QueueStatus.WAITING, QueueStatus.CALLED}:
            raise BadRequestError(
                message="Ticket cannot be called from its current state.",
                detail={"status": str(ticket.status)},
            )
        ticket.status = QueueStatus.CALLED
        ticket.called_at = datetime.now(timezone.utc)
        self.repository.save(ticket)
        self._link_step_status(ticket, VisitFlowStepStatus.CALLED)
        self.db.commit()
        return self.get_ticket(ticket.id)

    def start_serving(self, ticket_id: int, *, actor_user_id: Optional[int] = None) -> QueueTicket:
        ticket = self.repository.get_required_by_id(ticket_id)
        self._assert_active(ticket)
        if ticket.status not in {QueueStatus.WAITING, QueueStatus.CALLED}:
            raise BadRequestError(
                message="Ticket cannot start serving from its current state.",
                detail={"status": str(ticket.status)},
            )
        ticket.status = QueueStatus.SERVING
        if ticket.called_at is None:
            ticket.called_at = datetime.now(timezone.utc)
        ticket.service_started_at = datetime.now(timezone.utc)
        self.repository.save(ticket)
        self._link_step_status(ticket, VisitFlowStepStatus.IN_PROGRESS, started=True)
        self.db.commit()
        return self.get_ticket(ticket.id)

    def complete_ticket(self, ticket_id: int, *, actor_user_id: Optional[int] = None) -> QueueTicket:
        ticket = self.repository.get_required_by_id(ticket_id)
        self._assert_active(ticket)
        if ticket.status not in {QueueStatus.SERVING, QueueStatus.CALLED}:
            raise BadRequestError(
                message="Ticket cannot be completed from its current state.",
                detail={"status": str(ticket.status)},
            )
        ticket.status = QueueStatus.SERVED
        ticket.service_ended_at = datetime.now(timezone.utc)
        if ticket.service_started_at is None:
            ticket.service_started_at = ticket.service_ended_at
        self.repository.save(ticket)
        self._link_step_status(ticket, VisitFlowStepStatus.COMPLETED, completed=True)
        self.db.commit()
        return self.get_ticket(ticket.id)

    def mark_missed(self, ticket_id: int, *, actor_user_id: Optional[int] = None) -> QueueTicket:
        ticket = self.repository.get_required_by_id(ticket_id)
        self._assert_active(ticket)
        if ticket.status not in {QueueStatus.WAITING, QueueStatus.CALLED}:
            raise BadRequestError(
                message="Only waiting or called tickets can be marked missed.",
                detail={"status": str(ticket.status)},
            )
        ticket.status = QueueStatus.MISSED
        self.repository.save(ticket)
        self.db.commit()
        return self.get_ticket(ticket.id)

    def cancel_ticket(
        self,
        ticket_id: int,
        *,
        reason: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> QueueTicket:
        ticket = self.repository.get_required_by_id(ticket_id)
        self._assert_active(ticket)
        ticket.status = QueueStatus.CANCELLED
        self.repository.save(ticket)
        self._link_step_status(ticket, VisitFlowStepStatus.CANCELLED, completed=True)
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="QUEUE_TICKET_CANCELLED",
            severity="INFO",
            event_detail=f"Queue ticket {ticket.id} cancelled.",
            event_metadata={"reason": reason, "ticket_id": ticket.id},
        )
        self.db.commit()
        return self.get_ticket(ticket.id)

    def complete_and_route_to(
        self,
        ticket_id: int,
        target_service_delivery_point_id: int,
        *,
        notes: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> QueueTicket:
        """
        Mark the ticket SERVED, close the linked visit-flow step, then create
        a brand-new VisitFlowStep + QueueTicket at the target SDP.

        This is the canonical "I'm done with this patient at this workstation;
        send them on" verb used by clinicians, lab, pharmacy, cashier, etc.
        """
        ticket = self.repository.get_required_by_id(ticket_id)
        self._assert_active(ticket)

        if ticket.service_delivery_point_id == target_service_delivery_point_id:
            raise BadRequestError(
                message="Target service delivery point must differ from current.",
                detail={"service_delivery_point_id": target_service_delivery_point_id},
            )

        target_sdp = self.repository.get_service_delivery_point(target_service_delivery_point_id)
        if target_sdp is None:
            raise NotFoundError(
                message="Target service delivery point not found.",
                detail={"service_delivery_point_id": target_service_delivery_point_id},
            )

        now = datetime.now(timezone.utc)

        # Close the current ticket as SERVED (unless it was just CALLED with no
        # service start — promote that to SERVING+SERVED in one step).
        if ticket.service_started_at is None:
            ticket.service_started_at = now
        ticket.service_ended_at = now
        ticket.status = QueueStatus.SERVED
        self.repository.save(ticket)

        # Mirror back to the linked flow step before we route.
        self._link_step_status(ticket, VisitFlowStepStatus.COMPLETED, completed=True)

        # Append a new flow step + queue ticket at the target SDP.
        new_step, new_ticket = route_visit_to_next_sdp(
            self.db,
            visit_id=ticket.visit_id,
            target_service_delivery_point_id=target_sdp.id,
            routed_by_id=actor_user_id,
            notes=notes,
        )

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="QUEUE_TICKET_COMPLETED_AND_ROUTED",
            severity="INFO",
            event_detail=(
                f"Ticket {ticket.id} completed at SDP {ticket.service_delivery_point_id}; "
                f"routed to SDP {target_sdp.id} on new ticket {new_ticket.id}."
            ),
            event_metadata={
                "ticket_id": ticket.id,
                "new_ticket_id": new_ticket.id,
                "from_sdp": ticket.service_delivery_point_id,
                "to_sdp": target_sdp.id,
                "visit_id": ticket.visit_id,
            },
        )

        self.db.commit()
        return self.get_ticket(new_ticket.id)

    def complete_and_end_visit(
        self,
        ticket_id: int,
        *,
        note: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> Visit:
        """
        Mark the ticket SERVED at the final SDP and close the visit
        (status COMPLETED, check_out_time stamped).
        """
        ticket = self.repository.get_required_by_id(ticket_id)
        self._assert_active(ticket)

        now = datetime.now(timezone.utc)
        if ticket.service_started_at is None:
            ticket.service_started_at = now
        ticket.service_ended_at = now
        ticket.status = QueueStatus.SERVED
        self.repository.save(ticket)

        self._link_step_status(ticket, VisitFlowStepStatus.COMPLETED, completed=True)

        visit = end_visit(self.db, visit_id=ticket.visit_id, actor_user_id=actor_user_id, note=note)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="VISIT_COMPLETED_FROM_QUEUE",
            severity="INFO",
            event_detail=f"Visit {visit.id} completed at SDP {ticket.service_delivery_point_id}.",
            event_metadata={
                "ticket_id": ticket.id,
                "visit_id": visit.id,
                "service_delivery_point_id": ticket.service_delivery_point_id,
                "note": note,
            },
        )

        self.db.commit()
        return visit

    def transfer_ticket(
        self,
        ticket_id: int,
        target_service_delivery_point_id: int,
        *,
        reason: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> QueueTicket:
        ticket = self.repository.get_required_by_id(ticket_id)
        self._assert_active(ticket)

        target_sdp = self.repository.get_service_delivery_point(target_service_delivery_point_id)
        if not target_sdp:
            raise NotFoundError(
                message="Target service delivery point not found.",
                detail={"service_delivery_point_id": target_service_delivery_point_id},
            )

        # Close the current ticket as TRANSFERRED.
        ticket.status = QueueStatus.TRANSFERRED
        ticket.service_ended_at = datetime.now(timezone.utc)
        self.repository.save(ticket)

        # Create the new ticket at the target SDP linked back to the previous one.
        new_ticket = self.repository.create_ticket(
            visit_id=ticket.visit_id,
            patient_id=ticket.patient_id,
            service_delivery_point_id=target_sdp.id,
            visit_flow_step_id=None,
            transferred_from_ticket_id=ticket.id,
        )

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="QUEUE_TICKET_TRANSFERRED",
            severity="INFO",
            event_detail=(
                f"Queue ticket {ticket.id} transferred from SDP "
                f"{ticket.service_delivery_point_id} to SDP {target_sdp.id}."
            ),
            event_metadata={
                "ticket_id": ticket.id,
                "new_ticket_id": new_ticket.id,
                "from_sdp": ticket.service_delivery_point_id,
                "to_sdp": target_sdp.id,
                "reason": reason,
            },
        )
        self.db.commit()
        return self.get_ticket(new_ticket.id)

    # ============================================================
    # INTERNAL HELPERS
    # ============================================================

    def _assert_active(self, ticket: QueueTicket) -> None:
        if ticket.status in _TERMINAL:
            raise BadRequestError(
                message="Ticket has already reached a terminal state.",
                detail={"status": str(ticket.status)},
            )

    def _link_step_status(
        self,
        ticket: QueueTicket,
        new_status: VisitFlowStepStatus,
        *,
        started: bool = False,
        completed: bool = False,
    ) -> None:
        """
        When a queue ticket linked to a VisitFlowStep transitions, mirror the
        step status so visit_flow stays consistent.
        """
        if ticket.visit_flow_step_id is None:
            return
        step = (
            self.db.query(VisitFlowStep)
            .filter(VisitFlowStep.id == ticket.visit_flow_step_id)
            .first()
        )
        if step is None:
            return
        step.status = new_status
        now = datetime.now(timezone.utc)
        if started and step.started_at is None:
            step.started_at = now
        if completed:
            step.completed_at = now
            step.is_current = False
        self.db.add(step)
        self.db.flush()
