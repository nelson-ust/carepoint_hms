# app/services/appointment_service.py
from __future__ import annotations

"""
Service layer for appointment scheduling (Stage 7).

This service composes:

- :class:`AppointmentRepository`         — appointment persistence + conflict detection
- :class:`VisitService`                  — visit initiation on check-in
- :mod:`app.utils.security_event_util`   — audit trail for state transitions
- :class:`NotificationService`           — best-effort reminder dispatch (stage 17)

Lifecycle and business rules
----------------------------
- Booking goes straight to ``SCHEDULED``.
- Reschedule keeps the same row (audit-friendly), rather than creating a new one.
- Cancel and no-show are terminal but don't free the same slot for a re-book
  immediately — that's a deliberate business rule so finance / no-show fees
  remain attached to the original record.
- Check-in transitions to ``ARRIVED`` and (optionally) initiates a Visit so
  the patient is queued at the appointment's service-delivery point.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import AppointmentStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import Appointment
from app.repositories.appointment_repository import AppointmentRepository
from app.schemas.appointment_schemas import (
    AppointmentCancelSchema,
    AppointmentCheckInSchema,
    AppointmentCreateSchema,
    AppointmentNoShowSchema,
    AppointmentRescheduleSchema,
)
from app.schemas.visit_schemas import VisitInitiateSchema
from app.services.visit_service import VisitService
from app.utils.security_event_util import record_security_event


logger = logging.getLogger(__name__)

# Statuses considered open / mutable.
_OPEN_STATUSES = {AppointmentStatus.SCHEDULED, AppointmentStatus.RESCHEDULED}


class AppointmentService:
    """Service layer for appointment operations."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = AppointmentRepository(db)
        # The visit service is needed by check-in; instantiate eagerly to
        # avoid threading a session twice.
        self.visit_service = VisitService(db)

    # ============================================================
    # READ
    # ============================================================

    def get(self, appointment_id: int) -> Appointment:
        """Return one appointment, raising 404 when missing."""
        return self.repository.get_required_by_id(appointment_id)

    def list_appointments(self, **filters):
        """Paginated list. ``filters`` map directly onto repository kwargs."""
        # Translate string status into enum if supplied.
        status = filters.pop("status", None)
        if status is not None:
            try:
                filters["status"] = AppointmentStatus(status.strip().upper())
            except ValueError as exc:
                raise BadRequestError(
                    message="Invalid appointment status filter.",
                    detail={"status": status},
                ) from exc
        return self.repository.list_appointments(**filters)

    def arrival_board(
        self,
        *,
        for_date: datetime,
        service_delivery_point_id: Optional[int] = None,
        facility_id: Optional[int] = None,
    ) -> list[Appointment]:
        """Day-board view used by reception."""
        return self.repository.arrival_board(
            for_date=for_date,
            service_delivery_point_id=service_delivery_point_id,
            facility_id=facility_id,
        )

    def check_availability(
        self,
        *,
        scheduled_start_at: datetime,
        scheduled_end_at: Optional[datetime],
        staff_profile_id: Optional[int],
        service_delivery_point_id: Optional[int],
        exclude_appointment_id: Optional[int] = None,
    ) -> list[Appointment]:
        """
        Return any conflicts. An empty list means the slot is available.
        """
        return self.repository.find_conflicts(
            scheduled_start_at=scheduled_start_at,
            scheduled_end_at=scheduled_end_at,
            staff_profile_id=staff_profile_id,
            service_delivery_point_id=service_delivery_point_id,
            exclude_appointment_id=exclude_appointment_id,
        )

    # ============================================================
    # REMINDERS
    # ============================================================

    def _schedule_patient_reminders(
        self, appointment: "Appointment", *, reschedule: bool = False
    ) -> None:
        """
        Best-effort scheduling of the day-before + 3-hours-before patient
        reminders for an appointment. Never let a reminder-scheduling problem
        break the booking/reschedule itself — failures are swallowed.
        """
        try:
            from app.services.appointment_extension_service import (
                AppointmentExtensionService,
            )

            ext = AppointmentExtensionService(self.db)
            if reschedule:
                ext.reschedule_reminders(appointment)
            else:
                ext.schedule_patient_reminders(appointment)
        except Exception as exc:  # pragma: no cover - non-critical path
            logger.warning(
                "Failed to schedule reminders for appointment %s: %s",
                getattr(appointment, "id", "?"),
                exc,
            )

    # ============================================================
    # CREATE
    # ============================================================

    def book_appointment(
        self,
        payload: AppointmentCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Appointment:
        """
        Book a new appointment.

        Validates patient/SDP/staff existence, runs a double-booking check,
        and emits an audit row.
        """
        if payload.scheduled_end_at and payload.scheduled_end_at <= payload.scheduled_start_at:
            raise BadRequestError(
                message="scheduled_end_at must be after scheduled_start_at.",
            )

        # Existence checks.
        if self.repository.get_patient(payload.patient_id) is None:
            raise NotFoundError(
                message="Patient not found.",
                detail={"patient_id": payload.patient_id},
            )
        if payload.service_delivery_point_id is not None:
            sdp = self.repository.get_service_point(payload.service_delivery_point_id)
            if sdp is None:
                raise NotFoundError(
                    message="Service delivery point not found.",
                    detail={"service_delivery_point_id": payload.service_delivery_point_id},
                )
            if not bool(getattr(sdp, "supports_appointments", True)):
                raise BadRequestError(
                    message="Selected service delivery point does not support appointments.",
                    detail={"service_delivery_point_id": sdp.id},
                )
        if payload.staff_profile_id is not None and self.repository.get_staff(payload.staff_profile_id) is None:
            raise NotFoundError(
                message="Staff profile not found.",
                detail={"staff_profile_id": payload.staff_profile_id},
            )

        # Double-booking detection.
        conflicts = self.repository.find_conflicts(
            scheduled_start_at=payload.scheduled_start_at,
            scheduled_end_at=payload.scheduled_end_at,
            staff_profile_id=payload.staff_profile_id,
            service_delivery_point_id=payload.service_delivery_point_id,
        )
        if conflicts:
            raise BadRequestError(
                message="Slot is unavailable due to existing appointments.",
                detail={
                    "conflict_ids": [c.id for c in conflicts],
                    "conflict_codes": [c.appointment_code for c in conflicts],
                },
            )

        appointment = self.repository.create_appointment(
            patient_id=payload.patient_id,
            facility_id=payload.facility_id,
            service_delivery_point_id=payload.service_delivery_point_id,
            staff_profile_id=payload.staff_profile_id,
            scheduled_start_at=payload.scheduled_start_at,
            scheduled_end_at=payload.scheduled_end_at,
            reason=payload.reason,
        )

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="APPOINTMENT_BOOKED",
            severity="INFO",
            event_detail=f"Appointment {appointment.appointment_code} booked.",
            event_metadata={
                "appointment_id": appointment.id,
                "patient_id": appointment.patient_id,
                "scheduled_start_at": payload.scheduled_start_at.isoformat(),
            },
        )
        self.db.commit()

        # Schedule the patient's day-before + 3-hours-before reminders.
        self._schedule_patient_reminders(appointment)
        return self.repository.get_required_by_id(appointment.id)

    # ============================================================
    # RESCHEDULE / CANCEL / NO-SHOW
    # ============================================================

    def reschedule(
        self,
        appointment_id: int,
        payload: AppointmentRescheduleSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Appointment:
        """Reschedule an open appointment to a new slot."""
        appointment = self.repository.get_required_by_id(appointment_id)
        if appointment.status not in _OPEN_STATUSES:
            raise BadRequestError(
                message="Only open appointments can be rescheduled.",
                detail={"status": str(appointment.status)},
            )

        if (
            payload.new_scheduled_end_at
            and payload.new_scheduled_end_at <= payload.new_scheduled_start_at
        ):
            raise BadRequestError(
                message="new_scheduled_end_at must be after new_scheduled_start_at.",
            )

        # Excluding self so the conflict check doesn't flag the original slot.
        conflicts = self.repository.find_conflicts(
            scheduled_start_at=payload.new_scheduled_start_at,
            scheduled_end_at=payload.new_scheduled_end_at,
            staff_profile_id=appointment.staff_profile_id,
            service_delivery_point_id=appointment.service_delivery_point_id,
            exclude_appointment_id=appointment.id,
        )
        if conflicts:
            raise BadRequestError(
                message="New slot is unavailable due to existing appointments.",
                detail={"conflict_ids": [c.id for c in conflicts]},
            )

        prev_start = appointment.scheduled_start_at
        appointment.scheduled_start_at = payload.new_scheduled_start_at
        appointment.scheduled_end_at = payload.new_scheduled_end_at
        appointment.status = AppointmentStatus.RESCHEDULED
        if payload.reason:
            existing = appointment.reason or ""
            appointment.reason = (
                existing + ("\n\n" if existing else "") + f"[RESCHEDULED] {payload.reason}"
            ).strip()
        self.repository.save(appointment)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="APPOINTMENT_RESCHEDULED",
            severity="INFO",
            event_detail=f"Appointment {appointment.appointment_code} rescheduled.",
            event_metadata={
                "appointment_id": appointment.id,
                "previous_scheduled_start_at": prev_start.isoformat() if prev_start else None,
                "new_scheduled_start_at": payload.new_scheduled_start_at.isoformat(),
            },
        )
        # After reschedule, flip the status back to SCHEDULED so the UI
        # treats it as an open booking again. We keep the [RESCHEDULED]
        # marker in `reason` for traceability.
        appointment.status = AppointmentStatus.SCHEDULED
        self.repository.save(appointment)

        self.db.commit()

        # Re-point the patient's reminders at the new slot.
        self._schedule_patient_reminders(appointment, reschedule=True)
        return self.repository.get_required_by_id(appointment.id)

    def cancel(
        self,
        appointment_id: int,
        payload: AppointmentCancelSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Appointment:
        appointment = self.repository.get_required_by_id(appointment_id)
        if appointment.status in {
            AppointmentStatus.CANCELLED,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.MISSED,
        }:
            raise BadRequestError(
                message="Appointment cannot be cancelled in its current state.",
                detail={"status": str(appointment.status)},
            )
        appointment.status = AppointmentStatus.CANCELLED
        if payload.reason:
            existing = appointment.reason or ""
            appointment.reason = (
                existing + ("\n\n" if existing else "") + f"[CANCELLED] {payload.reason}"
            ).strip()
        self.repository.save(appointment)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="APPOINTMENT_CANCELLED",
            severity="WARNING",
            event_detail=f"Appointment {appointment.appointment_code} cancelled.",
            event_metadata={
                "appointment_id": appointment.id,
                "reason": payload.reason,
            },
        )
        self.db.commit()
        return self.repository.get_required_by_id(appointment.id)

    def mark_no_show(
        self,
        appointment_id: int,
        payload: AppointmentNoShowSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Appointment:
        appointment = self.repository.get_required_by_id(appointment_id)
        if appointment.status not in {AppointmentStatus.SCHEDULED, AppointmentStatus.ARRIVED}:
            raise BadRequestError(
                message="Only scheduled or arrived appointments can be marked missed.",
                detail={"status": str(appointment.status)},
            )
        appointment.status = AppointmentStatus.MISSED
        if payload.note:
            existing = appointment.reason or ""
            appointment.reason = (
                existing + ("\n\n" if existing else "") + f"[MISSED] {payload.note}"
            ).strip()
        self.repository.save(appointment)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="APPOINTMENT_MISSED",
            severity="WARNING",
            event_detail=f"Appointment {appointment.appointment_code} marked missed.",
            event_metadata={"appointment_id": appointment.id},
        )
        self.db.commit()
        return self.repository.get_required_by_id(appointment.id)

    # ============================================================
    # CHECK-IN
    # ============================================================

    def check_in(
        self,
        appointment_id: int,
        payload: AppointmentCheckInSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> dict:
        """
        Mark an appointment ``ARRIVED`` and optionally initiate the visit.

        Returns a dict the route layer can serialize. When ``initiate_visit``
        is True, the visit + first queue ticket are created in the same
        request so the patient is immediately queued at the right SDP.
        """
        appointment = self.repository.get_required_by_id(appointment_id)
        if appointment.status not in _OPEN_STATUSES:
            raise BadRequestError(
                message="Only open appointments can be checked in.",
                detail={"status": str(appointment.status)},
            )

        appointment.status = AppointmentStatus.ARRIVED
        self.repository.save(appointment)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="APPOINTMENT_CHECKED_IN",
            severity="INFO",
            event_detail=f"Appointment {appointment.appointment_code} checked in.",
            event_metadata={
                "appointment_id": appointment.id,
                "patient_id": appointment.patient_id,
            },
        )

        visit = None
        queue_ticket = None
        if payload.initiate_visit:
            try:
                visit_payload = VisitInitiateSchema(
                    patient_id=appointment.patient_id,
                    appointment_id=appointment.id,
                    visit_flow_template_id=payload.visit_flow_template_id,
                    use_appointment_service_point=payload.use_appointment_service_point,
                    fast_track=payload.fast_track,
                    visit_reason=payload.visit_reason,
                    create_first_flow_step=payload.create_first_flow_step,
                    create_queue_ticket=payload.create_queue_ticket,
                )
            except Exception as exc:  # pragma: no cover - defensive
                raise BadRequestError(
                    message="Failed to build visit-initiation payload.",
                    detail={"reason": str(exc)},
                ) from exc

            result = self.visit_service.initiate_visit(visit_payload, routed_by_id=actor_user_id)
            visit = result.get("visit") if isinstance(result, dict) else None
            queue_ticket = result.get("first_queue_ticket") if isinstance(result, dict) else None

        self.db.commit()
        return {
            "appointment": self.repository.get_required_by_id(appointment.id),
            "visit": visit,
            "queue_ticket": queue_ticket,
        }
