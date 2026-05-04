from __future__ import annotations

"""
app.services.visit_service

Service layer for visit initiation and operational care workflow entry.

Purpose
-------
This module implements business logic for:

- initiating a visit for an existing or newly registered patient
- generating a unique visit code
- resolving the first service delivery point
- inheriting appointment context where applicable
- applying a visit flow template
- creating the first runtime flow step
- creating the first queue ticket
- fast-tracking urgent/emergency visits
- rerouting visits dynamically during runtime
- updating visit operational state

Requirements coverage
---------------------
UC-02 - Initiate Visit for Existing or New Patient

Normal flow:
1. Retrieve patient record
2. Create visit with visit code and visit reason
3. Set first service delivery point or use appointment context
4. Create first flow step and queue ticket for the selected point
5. Mark visit as initiated or waiting

Alternate flow:
- If patient has an appointment, visit can inherit the booked service point
- If condition is urgent, priority is set to urgent or emergency and patient is fast-tracked
- Runtime visit flow can be rerouted or extended dynamically
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    QueueStatus,
    VisitFlowStepStatus,
    VisitPriority,
    VisitStatus,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.repositories.visit_repository import VisitRepository
from app.schemas.visit_schemas import (
    VisitInitiateSchema,
    VisitRerouteSchema,
    VisitUpdateSchema,
)


class VisitService:
    """
    Service layer for visit initiation and runtime visit workflow management.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = VisitRepository(db)

    # ============================================================
    # VISIT INITIATION
    # ============================================================

    def initiate_visit(
        self,
        payload: VisitInitiateSchema,
        *,
        routed_by_id: Optional[int] = None,
    ):
        """
        Initiate a visit and place the patient into the operational workflow.

        Business rules
        --------------
        - patient must exist
        - if appointment_id is supplied, appointment must exist
        - if appointment_id is supplied, it must belong to the patient
        - first service point must resolve from one of:
            1. explicit service point
            2. appointment service point
            3. visit flow template first step
        - if explicit service point is used without appointment context,
          it should support walk-ins
        - if appointment-derived service point is used, that point should
          support appointments
        - active visit duplication is blocked by default
        - urgent/emergency + fast_track places patient into the queue with
          priority-compatible state while preserving normal queue logic

        Returns
        -------
        dict
            Structured initiation result that aligns with VisitInitiationResultSchema.
        """
        patient = self.repository.get_patient_by_id(payload.patient_id)
        if not patient:
            raise NotFoundError(
                message="Patient not found.",
                detail={"patient_id": payload.patient_id},
            )

        appointment = None
        if payload.appointment_id is not None:
            appointment = self.repository.get_appointment_by_id(payload.appointment_id)
            if not appointment:
                raise NotFoundError(
                    message="Appointment not found.",
                    detail={"appointment_id": payload.appointment_id},
                )

            if appointment.patient_id != payload.patient_id:
                raise BadRequestError(
                    message="Appointment does not belong to the selected patient.",
                    detail={
                        "appointment_id": payload.appointment_id,
                        "patient_id": payload.patient_id,
                    },
                )

        template = None
        if payload.visit_flow_template_id is not None:
            template = self.repository.get_visit_flow_template_by_id(
                payload.visit_flow_template_id
            )
            if not template:
                raise NotFoundError(
                    message="Visit flow template not found.",
                    detail={"visit_flow_template_id": payload.visit_flow_template_id},
                )

        if self.repository.patient_has_open_or_waiting_visit(payload.patient_id):
            raise BadRequestError(
                message="Patient already has an active visit.",
                detail={"patient_id": payload.patient_id},
            )

        resolved_service_point = self.repository.resolve_first_service_delivery_point(
            first_service_delivery_point_id=payload.first_service_delivery_point_id,
            use_appointment_service_point=payload.use_appointment_service_point,
            appointment=appointment,
            visit_flow_template=template,
        )

        if not resolved_service_point:
            raise BadRequestError(
                message=(
                    "Unable to resolve the first service delivery point. "
                    "Provide a service point, use appointment context, or use a template."
                )
            )

        # INSURANCE FLOW OVERRIDE
        # If the patient is an insurance patient, the first service point should be the Insurance Station
        is_insurance_patient = (
            patient.payer_type == "HMO" or 
            any(rec.policy_status == "ACTIVE" for rec in patient.insurance_records)
        )
        
        if is_insurance_patient:
            insurance_station = self.repository.get_service_delivery_point_by_type("INSURANCE_CONFIRMATION")
            if insurance_station:
                resolved_service_point = insurance_station
                # Update payload to reflect this override for subsequent logic
                payload.first_service_delivery_point_id = insurance_station.id

        if (
            payload.first_service_delivery_point_id is not None
            and payload.appointment_id is None
            and not self.repository.service_delivery_point_supports_walk_in(
                resolved_service_point.id
            )
        ):
            raise BadRequestError(
                message="The selected service delivery point does not support walk-in visits.",
                detail={"service_delivery_point_id": resolved_service_point.id},
            )

        if (
            payload.use_appointment_service_point
            and appointment is not None
            and not self.repository.service_delivery_point_supports_appointments(
                resolved_service_point.id
            )
        ):
            raise BadRequestError(
                message="The appointment-linked service delivery point does not support appointments.",
                detail={"service_delivery_point_id": resolved_service_point.id},
            )

        priority = self._resolve_visit_priority(
            payload.priority,
            fast_track=payload.fast_track,
        )

        visit_status = self._resolve_initial_visit_status(payload)

        visit_code = self.repository.generate_unique_visit_code(
            patient_id=payload.patient_id,
            when=payload.visit_date or datetime.now(timezone.utc),
        )

        visit = self.repository.create_visit(
            patient_id=payload.patient_id,
            appointment_id=payload.appointment_id,
            visit_code=visit_code,
            visit_reason=payload.visit_reason,
            visit_date=payload.visit_date,
            status=visit_status,
            priority=priority,
            first_service_delivery_point_id=resolved_service_point.id,
            current_service_delivery_point_id=resolved_service_point.id,
            referred_from=payload.referred_from,
            check_in_time=payload.check_in_time or datetime.now(timezone.utc),
        )

        first_flow_step = None
        first_queue_ticket = None
        applied_template_payload = None
        inherited_from_appointment = (
            bool(payload.use_appointment_service_point and appointment is not None)
        )

        if template is not None:
            created_steps = self.repository.create_flow_steps_from_template(
                visit_id=visit.id,
                template=template,
                first_step_status=self._resolve_flow_step_status(
                    payload.first_step_status
                ),
                routed_by_id=routed_by_id,
                started_at_for_first=datetime.now(timezone.utc),
            )

            if created_steps:
                first_flow_step = created_steps[0]
                visit.current_service_delivery_point_id = (
                    first_flow_step.service_delivery_point_id
                )
                visit.first_service_delivery_point_id = (
                    first_flow_step.service_delivery_point_id
                )
                self.repository.update_visit(visit)

                if payload.create_queue_ticket:
                    first_queue_ticket = self._create_queue_ticket_for_step(
                        visit_id=visit.id,
                        patient_id=payload.patient_id,
                        flow_step_id=first_flow_step.id,
                        service_delivery_point_id=first_flow_step.service_delivery_point_id,
                        queue_status=self._resolve_queue_status(payload.first_queue_status),
                        queue_position=payload.queue_position,
                    )

            applied_template_payload = template

        else:
            if payload.create_first_flow_step:
                first_flow_step = self.repository.create_first_visit_flow_step(
                    visit_id=visit.id,
                    service_delivery_point_id=resolved_service_point.id,
                    step_order=1,
                    status=self._resolve_flow_step_status(payload.first_step_status),
                    is_current=True,
                    is_required=True,
                    is_skipped=False,
                    routed_by_id=routed_by_id,
                    started_at=datetime.now(timezone.utc),
                    notes=payload.flow_step_notes,
                )

            if payload.create_queue_ticket:
                first_queue_ticket = self._create_queue_ticket_for_step(
                    visit_id=visit.id,
                    patient_id=payload.patient_id,
                    flow_step_id=first_flow_step.id if first_flow_step else None,
                    service_delivery_point_id=resolved_service_point.id,
                    queue_status=self._resolve_queue_status(payload.first_queue_status),
                    queue_position=payload.queue_position,
                )

        self.db.commit()

        detailed_visit = self.repository.get_detailed_visit_by_id(visit.id)

        return {
            "success": True,
            "message": "Visit initiated successfully.",
            "visit": detailed_visit,
            "first_flow_step": first_flow_step,
            "first_queue_ticket": first_queue_ticket,
            "applied_template": applied_template_payload,
            "inherited_from_appointment": inherited_from_appointment,
            "fast_tracked": bool(
                payload.fast_track
                and priority in {VisitPriority.URGENT, VisitPriority.EMERGENCY}
            ),
        }

    # ============================================================
    # REROUTING
    # ============================================================

    def reroute_visit(
        self,
        visit_id: int,
        payload: VisitRerouteSchema,
    ):
        """
        Reroute an active visit to a new service delivery point.

        Business rules
        --------------
        - visit must exist
        - target service point must exist
        - a new runtime flow step is appended
        - the visit current service point is updated
        - the prior queue ticket is linked through transferred_from_ticket_id
          when a new queue ticket is created

        Returns
        -------
        dict
            Structured reroute result aligned to VisitRerouteResultSchema.
        """
        visit = self.repository.get_detailed_visit_by_id(visit_id)
        if not visit:
            raise NotFoundError(
                message="Visit not found.",
                detail={"visit_id": visit_id},
            )

        target_service_point = self.repository.get_service_delivery_point_by_id(
            payload.service_delivery_point_id
        )
        if not target_service_point:
            raise NotFoundError(
                message="Target service delivery point not found.",
                detail={"service_delivery_point_id": payload.service_delivery_point_id},
            )

        previous_ticket = self.repository.get_latest_queue_ticket_for_visit(visit_id)

        new_flow_step = self.repository.create_rerouted_flow_step(
            visit_id=visit.id,
            service_delivery_point_id=target_service_point.id,
            routed_by_id=payload.routed_by_id,
            status=VisitFlowStepStatus.PENDING,
            is_required=True,
            notes=payload.reason,
            mark_as_current=payload.mark_as_current,
        )

        new_queue_ticket = None
        if payload.create_queue_ticket:
            new_queue_ticket = self.repository.create_rerouted_queue_ticket(
                visit_id=visit.id,
                visit_flow_step_id=new_flow_step.id,
                patient_id=visit.patient_id,
                service_delivery_point=target_service_point,
                status=self._resolve_queue_status(payload.queue_status),
                queue_position=payload.queue_position,
                transferred_from_ticket_id=previous_ticket.id if previous_ticket else None,
            )

        visit.current_service_delivery_point_id = target_service_point.id
        if visit.status in {VisitStatus.COMPLETED, VisitStatus.CANCELLED}:
            raise BadRequestError(
                message="Completed or cancelled visits cannot be rerouted.",
                detail={"visit_id": visit.id},
            )

        if visit.status == VisitStatus.INITIATED:
            visit.status = VisitStatus.WAITING

        self.repository.update_visit(visit)
        self.db.commit()

        detailed_visit = self.repository.get_detailed_visit_by_id(visit.id)

        return {
            "success": True,
            "message": "Visit rerouted successfully.",
            "visit": detailed_visit,
            "new_flow_step": new_flow_step,
            "new_queue_ticket": new_queue_ticket,
        }

    # ============================================================
    # READ
    # ============================================================

    def get_visit(self, visit_id: int):
        """
        Return a single visit by ID.
        """
        visit = self.repository.get_visit_by_id(visit_id)
        if not visit:
            raise NotFoundError(
                message="Visit not found.",
                detail={"visit_id": visit_id},
            )
        return visit

    def get_detailed_visit(self, visit_id: int):
        """
        Return a detailed visit by ID.
        """
        visit = self.repository.get_detailed_visit_by_id(visit_id)
        if not visit:
            raise NotFoundError(
                message="Visit not found.",
                detail={"visit_id": visit_id},
            )
        return visit

    def list_visits(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        patient_id: Optional[int] = None,
        appointment_id: Optional[int] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        service_delivery_point_id: Optional[int] = None,
    ):
        """
        Return paginated visits.
        """
        normalized_status = self._resolve_visit_status(status) if status else None
        normalized_priority = self._resolve_visit_priority(priority) if priority else None

        return self.repository.list_visits(
            skip=skip,
            limit=limit,
            patient_id=patient_id,
            appointment_id=appointment_id,
            status=normalized_status,
            priority=normalized_priority,
            service_delivery_point_id=service_delivery_point_id,
        )

    # ============================================================
    # UPDATE
    # ============================================================

    def update_visit(
        self,
        visit_id: int,
        payload: VisitUpdateSchema,
    ):
        """
        Update mutable visit fields.
        """
        visit = self.get_visit(visit_id)

        if payload.appointment_id is not None:
            appointment = self.repository.get_appointment_by_id(payload.appointment_id)
            if not appointment:
                raise NotFoundError(
                    message="Appointment not found.",
                    detail={"appointment_id": payload.appointment_id},
                )
            if appointment.patient_id != visit.patient_id:
                raise BadRequestError(
                    message="Appointment does not belong to the visit patient.",
                    detail={
                        "appointment_id": payload.appointment_id,
                        "patient_id": visit.patient_id,
                    },
                )
            visit.appointment_id = payload.appointment_id

        if payload.first_service_delivery_point_id is not None:
            sdp = self.repository.get_service_delivery_point_by_id(
                payload.first_service_delivery_point_id
            )
            if not sdp:
                raise NotFoundError(
                    message="First service delivery point not found.",
                    detail={
                        "service_delivery_point_id": payload.first_service_delivery_point_id
                    },
                )
            visit.first_service_delivery_point_id = payload.first_service_delivery_point_id

        if payload.current_service_delivery_point_id is not None:
            sdp = self.repository.get_service_delivery_point_by_id(
                payload.current_service_delivery_point_id
            )
            if not sdp:
                raise NotFoundError(
                    message="Current service delivery point not found.",
                    detail={
                        "service_delivery_point_id": payload.current_service_delivery_point_id
                    },
                )
            visit.current_service_delivery_point_id = payload.current_service_delivery_point_id

        if payload.visit_reason is not None:
            visit.visit_reason = payload.visit_reason

        if payload.referred_from is not None:
            visit.referred_from = payload.referred_from

        if payload.priority is not None:
            visit.priority = self._resolve_visit_priority(payload.priority)

        if payload.status is not None:
            visit.status = self._resolve_visit_status(payload.status)

        if payload.check_in_time is not None:
            visit.check_in_time = payload.check_in_time

        if payload.check_out_time is not None:
            visit.check_out_time = payload.check_out_time

        updated = self.repository.update_visit(visit)
        self.db.commit()
        return self.repository.get_detailed_visit_by_id(updated.id)

    # ============================================================
    # HELPERS
    # ============================================================

    def _create_queue_ticket_for_step(
        self,
        *,
        visit_id: int,
        patient_id: int,
        flow_step_id: Optional[int],
        service_delivery_point_id: int,
        queue_status: QueueStatus,
        queue_position: Optional[int] = None,
    ):
        service_point = self.repository.get_service_delivery_point_by_id(
            service_delivery_point_id
        )
        if not service_point:
            raise NotFoundError(
                message="Service delivery point not found.",
                detail={"service_delivery_point_id": service_delivery_point_id},
            )

        effective_position = queue_position or self.repository.get_next_queue_position(
            service_delivery_point_id=service_delivery_point_id
        )

        queue_number = self.repository.generate_queue_number_for_service_point(
            service_delivery_point=service_point,
            sequence=effective_position,
            when=datetime.now(timezone.utc),
        )

        return self.repository.create_queue_ticket(
            visit_id=visit_id,
            visit_flow_step_id=flow_step_id,
            patient_id=patient_id,
            service_delivery_point_id=service_delivery_point_id,
            queue_number=queue_number,
            queue_position=effective_position,
            status=queue_status,
            transferred_from_ticket_id=None,
        )

    def _resolve_visit_priority(
        self,
        priority: Optional[str | VisitPriority],
        *,
        fast_track: bool = False,
    ) -> VisitPriority:
        """
        Normalize visit priority to VisitPriority enum.
        """
        if isinstance(priority, VisitPriority):
            return priority

        if priority is None:
            return VisitPriority.URGENT if fast_track else VisitPriority.NORMAL

        normalized = str(priority).strip().upper()
        try:
            return VisitPriority[normalized]
        except KeyError:
            raise BadRequestError(
                message=f"Unsupported visit priority: {priority}",
                detail={"priority": priority},
            )

    def _resolve_visit_status(
        self,
        status: Optional[str | VisitStatus],
    ) -> VisitStatus:
        """
        Normalize visit status to VisitStatus enum.
        """
        if isinstance(status, VisitStatus):
            return status

        if status is None:
            return VisitStatus.INITIATED

        normalized = str(status).strip().upper()
        try:
            return VisitStatus[normalized]
        except KeyError:
            raise BadRequestError(
                message=f"Unsupported visit status: {status}",
                detail={"status": status},
            )

    def _resolve_flow_step_status(
        self,
        status: Optional[str | VisitFlowStepStatus],
    ) -> VisitFlowStepStatus:
        """
        Normalize flow-step status to VisitFlowStepStatus enum.
        """
        if isinstance(status, VisitFlowStepStatus):
            return status

        if status is None:
            return VisitFlowStepStatus.PENDING

        normalized = str(status).strip().upper()
        try:
            return VisitFlowStepStatus[normalized]
        except KeyError:
            raise BadRequestError(
                message=f"Unsupported visit flow step status: {status}",
                detail={"status": status},
            )

    def _resolve_queue_status(
        self,
        status: Optional[str | QueueStatus],
    ) -> QueueStatus:
        """
        Normalize queue status to QueueStatus enum.
        """
        if isinstance(status, QueueStatus):
            return status

        if status is None:
            return QueueStatus.WAITING

        normalized = str(status).strip().upper()
        try:
            return QueueStatus[normalized]
        except KeyError:
            raise BadRequestError(
                message=f"Unsupported queue status: {status}",
                detail={"status": status},
            )

    def _resolve_initial_visit_status(
        self,
        payload: VisitInitiateSchema,
    ) -> VisitStatus:
        """
        Resolve the initial visit status from the initiation payload.
        """
        if payload.status:
            return self._resolve_visit_status(payload.status)

        if payload.mark_visit_waiting:
            return VisitStatus.WAITING

        return VisitStatus.INITIATED