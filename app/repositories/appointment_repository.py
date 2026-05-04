# app/repositories/appointment_repository.py
from __future__ import annotations

"""
Repository for the appointment scheduling module (Stage 7).

Responsibilities
----------------
- generate human-readable appointment codes
- create/update/list/lookup appointments
- detect double-bookings against a clinician or service-delivery-point
- power the receptionist arrival board

The repository never commits — service-layer code owns transaction boundaries.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.enums import AppointmentStatus
from app.core.exceptions import NotFoundError
from app.models.all_models import Appointment, Patient, ServiceDeliveryPoint, StaffProfile
from app.utils.helpers import generate_uuid_str


# Statuses that still hold a slot. Cancelled, rescheduled, and missed
# appointments don't conflict with new bookings.
ACTIVE_APPOINTMENT_STATUSES = (
    AppointmentStatus.SCHEDULED,
    AppointmentStatus.ARRIVED,
    AppointmentStatus.IN_PROGRESS,
)


class AppointmentRepository:
    """Persistence layer for ``Appointment``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ============================================================
    # LOOKUPS
    # ============================================================

    def get_by_id(self, appointment_id: int) -> Optional[Appointment]:
        """Single appointment with patient + SDP eagerly loaded."""
        return (
            self.db.query(Appointment)
            .options(
                joinedload(Appointment.patient),
                joinedload(Appointment.service_delivery_point),
                joinedload(Appointment.staff_profile),
            )
            .filter(
                Appointment.id == appointment_id,
                Appointment.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, appointment_id: int) -> Appointment:
        """Service-layer ergonomic: 404 if missing."""
        a = self.get_by_id(appointment_id)
        if not a:
            raise NotFoundError(
                message="Appointment not found.",
                detail={"appointment_id": appointment_id},
            )
        return a

    def get_by_code(self, code: str) -> Optional[Appointment]:
        return (
            self.db.query(Appointment)
            .filter(
                Appointment.appointment_code == code.strip(),
                Appointment.is_deleted.is_(False),
            )
            .first()
        )

    def get_patient(self, patient_id: int) -> Optional[Patient]:
        return (
            self.db.query(Patient)
            .filter(Patient.id == patient_id, Patient.is_deleted.is_(False))
            .first()
        )

    def get_service_point(self, sdp_id: int) -> Optional[ServiceDeliveryPoint]:
        return (
            self.db.query(ServiceDeliveryPoint)
            .filter(
                ServiceDeliveryPoint.id == sdp_id,
                ServiceDeliveryPoint.is_deleted.is_(False),
            )
            .first()
        )

    def get_staff(self, staff_id: int) -> Optional[StaffProfile]:
        return (
            self.db.query(StaffProfile)
            .filter(
                StaffProfile.id == staff_id,
                StaffProfile.is_deleted.is_(False),
            )
            .first()
        )

    # ============================================================
    # LISTINGS
    # ============================================================

    def list_appointments(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        patient_id: Optional[int] = None,
        staff_profile_id: Optional[int] = None,
        service_delivery_point_id: Optional[int] = None,
        facility_id: Optional[int] = None,
        status: Optional[AppointmentStatus] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
    ) -> tuple[list[Appointment], int]:
        """Paginated list with the most common filters."""
        query = (
            self.db.query(Appointment)
            .options(joinedload(Appointment.patient))
            .filter(Appointment.is_deleted.is_(False))
        )

        if patient_id is not None:
            query = query.filter(Appointment.patient_id == patient_id)
        if staff_profile_id is not None:
            query = query.filter(Appointment.staff_profile_id == staff_profile_id)
        if service_delivery_point_id is not None:
            query = query.filter(Appointment.service_delivery_point_id == service_delivery_point_id)
        if facility_id is not None:
            query = query.filter(Appointment.facility_id == facility_id)
        if status is not None:
            query = query.filter(Appointment.status == status)
        if from_dt is not None:
            query = query.filter(Appointment.scheduled_start_at >= from_dt)
        if to_dt is not None:
            query = query.filter(Appointment.scheduled_start_at < to_dt)

        total = query.with_entities(func.count(Appointment.id)).scalar() or 0
        items = (
            query.order_by(Appointment.scheduled_start_at.asc(), Appointment.id.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def arrival_board(
        self,
        *,
        for_date: datetime,
        service_delivery_point_id: Optional[int] = None,
        facility_id: Optional[int] = None,
    ) -> list[Appointment]:
        """
        Appointments scheduled for ``for_date`` (UTC day-window) that are
        still active. Powers the front-desk arrival board.
        """
        day_start = for_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        query = (
            self.db.query(Appointment)
            .options(joinedload(Appointment.patient))
            .filter(
                Appointment.is_deleted.is_(False),
                Appointment.scheduled_start_at >= day_start,
                Appointment.scheduled_start_at < day_end,
                Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            )
        )
        if service_delivery_point_id is not None:
            query = query.filter(Appointment.service_delivery_point_id == service_delivery_point_id)
        if facility_id is not None:
            query = query.filter(Appointment.facility_id == facility_id)
        return query.order_by(Appointment.scheduled_start_at.asc()).all()

    # ============================================================
    # CREATE / UPDATE
    # ============================================================

    def generate_appointment_code(self) -> str:
        """Deterministic code: ``APT-YYYYMMDD-XXXXXXXX``."""
        return f"APT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create_appointment(
        self,
        *,
        patient_id: int,
        facility_id: Optional[int],
        service_delivery_point_id: Optional[int],
        staff_profile_id: Optional[int],
        scheduled_start_at: datetime,
        scheduled_end_at: Optional[datetime],
        reason: Optional[str],
        status: AppointmentStatus = AppointmentStatus.SCHEDULED,
    ) -> Appointment:
        appointment = Appointment(
            patient_id=patient_id,
            facility_id=facility_id,
            service_delivery_point_id=service_delivery_point_id,
            staff_profile_id=staff_profile_id,
            appointment_code=self.generate_appointment_code(),
            scheduled_start_at=scheduled_start_at,
            scheduled_end_at=scheduled_end_at,
            reason=reason,
            status=status,
        )
        self.db.add(appointment)
        self.db.flush()
        self.db.refresh(appointment)
        return appointment

    def save(self, appointment: Appointment) -> Appointment:
        self.db.add(appointment)
        self.db.flush()
        self.db.refresh(appointment)
        return appointment

    # ============================================================
    # DOUBLE-BOOKING DETECTION
    # ============================================================

    def find_conflicts(
        self,
        *,
        scheduled_start_at: datetime,
        scheduled_end_at: Optional[datetime],
        staff_profile_id: Optional[int] = None,
        service_delivery_point_id: Optional[int] = None,
        exclude_appointment_id: Optional[int] = None,
    ) -> list[Appointment]:
        """
        Return appointments that overlap with the requested window for the
        same clinician or service-delivery-point.

        Semantics: an appointment with no end_at is treated as a 30-minute
        block so we still detect contention.
        """
        if staff_profile_id is None and service_delivery_point_id is None:
            return []

        end = scheduled_end_at or (scheduled_start_at + timedelta(minutes=30))

        query = self.db.query(Appointment).filter(
            Appointment.is_deleted.is_(False),
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
        )

        if exclude_appointment_id is not None:
            query = query.filter(Appointment.id != exclude_appointment_id)

        clauses = []
        if staff_profile_id is not None:
            clauses.append(Appointment.staff_profile_id == staff_profile_id)
        if service_delivery_point_id is not None:
            clauses.append(Appointment.service_delivery_point_id == service_delivery_point_id)
        # Either-or contention check.
        query = query.filter(or_(*clauses))

        # Overlap test: A.start < end AND coalesce(A.end, A.start + 30m) > start.
        query = query.filter(
            and_(
                Appointment.scheduled_start_at < end,
                func.coalesce(
                    Appointment.scheduled_end_at,
                    Appointment.scheduled_start_at + timedelta(minutes=30),
                )
                > scheduled_start_at,
            )
        )
        return query.all()
