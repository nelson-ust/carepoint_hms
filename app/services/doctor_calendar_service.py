"""
Doctor calendar / availability / slot service.

Surface-area:

* CRUD on weekly :class:`DoctorAvailabilityTemplate` rows.
* CRUD on :class:`DoctorTimeOff` (leave / holiday / unavailable).
* Materialise :class:`AppointmentSlot` rows forward from the templates,
  applying any time-off blocks.
* Calendar views (daily / weekly / monthly) for a doctor or filtered by
  facility / department / specialty.
* Workload counters (booked / open / blocked per doctor per day).

Slot generation is idempotent: re-running it for the same window simply
fills in any new templates without duplicating existing slots.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.enums import (
    AppointmentSlotStatus,
    DoctorAvailabilityType,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    Appointment,
    AppointmentSlot,
    DoctorAvailabilityTemplate,
    DoctorTimeOff,
    StaffProfile,
)


logger = logging.getLogger(__name__)


class DoctorCalendarService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # AVAILABILITY TEMPLATES
    # ------------------------------------------------------------------

    def list_templates(
        self,
        *,
        staff_profile_id: Optional[int] = None,
        only_active: bool = False,
    ) -> list[DoctorAvailabilityTemplate]:
        q = self.db.query(DoctorAvailabilityTemplate).filter(
            DoctorAvailabilityTemplate.is_deleted.is_(False)
        )
        if staff_profile_id is not None:
            q = q.filter(DoctorAvailabilityTemplate.staff_profile_id == staff_profile_id)
        if only_active:
            q = q.filter(DoctorAvailabilityTemplate.is_active.is_(True))
        return q.order_by(
            DoctorAvailabilityTemplate.staff_profile_id,
            DoctorAvailabilityTemplate.weekday,
            DoctorAvailabilityTemplate.start_time,
        ).all()

    def create_template(
        self,
        *,
        staff_profile_id: int,
        weekday: int,
        start_time: str,
        end_time: str,
        slot_duration_minutes: int = 30,
        max_patients_per_slot: int = 1,
        appointment_type: Optional[str] = None,
        facility_id: Optional[int] = None,
        service_delivery_point_id: Optional[int] = None,
        timezone_name: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> DoctorAvailabilityTemplate:
        if not 0 <= weekday <= 6:
            raise BadRequestError(message="weekday must be 0 (Monday) to 6 (Sunday).")
        self._validate_hhmm(start_time, "start_time")
        self._validate_hhmm(end_time, "end_time")
        if start_time >= end_time:
            raise BadRequestError(message="start_time must be earlier than end_time.")
        if slot_duration_minutes < 5 or slot_duration_minutes > 240:
            raise BadRequestError(message="slot_duration_minutes must be between 5 and 240.")

        rec = DoctorAvailabilityTemplate(
            staff_profile_id=staff_profile_id,
            facility_id=facility_id,
            service_delivery_point_id=service_delivery_point_id,
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
            slot_duration_minutes=slot_duration_minutes,
            max_patients_per_slot=max_patients_per_slot,
            appointment_type=appointment_type,
            timezone=timezone_name,
            notes=notes,
            is_active=True,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def deactivate_template(self, template_id: int) -> DoctorAvailabilityTemplate:
        rec = (
            self.db.query(DoctorAvailabilityTemplate)
            .filter(DoctorAvailabilityTemplate.id == template_id)
            .first()
        )
        if rec is None:
            raise NotFoundError(message="Availability template not found.")
        rec.is_active = False
        self.db.commit()
        return rec

    # ------------------------------------------------------------------
    # TIME OFF
    # ------------------------------------------------------------------

    def add_time_off(
        self,
        *,
        staff_profile_id: int,
        starts_at: datetime,
        ends_at: datetime,
        availability_type: DoctorAvailabilityType = DoctorAvailabilityType.BLOCKED,
        reason: Optional[str] = None,
        approved_by_user_id: Optional[int] = None,
    ) -> DoctorTimeOff:
        if ends_at <= starts_at:
            raise BadRequestError(message="ends_at must be after starts_at.")
        rec = DoctorTimeOff(
            staff_profile_id=staff_profile_id,
            starts_at=starts_at,
            ends_at=ends_at,
            availability_type=availability_type,
            reason=reason,
            approved_by_user_id=approved_by_user_id,
        )
        self.db.add(rec)
        # Block any already-materialised slots in this window.
        affected = (
            self.db.query(AppointmentSlot)
            .filter(
                AppointmentSlot.staff_profile_id == staff_profile_id,
                AppointmentSlot.starts_at >= starts_at,
                AppointmentSlot.ends_at <= ends_at,
                AppointmentSlot.status == AppointmentSlotStatus.OPEN,
            )
            .all()
        )
        for slot in affected:
            slot.status = AppointmentSlotStatus.BLOCKED
            slot.block_reason = reason or "Doctor unavailable"
        self.db.commit()
        self.db.refresh(rec)
        return rec

    # ------------------------------------------------------------------
    # SLOT MATERIALISATION
    # ------------------------------------------------------------------

    def materialise_slots(
        self,
        *,
        staff_profile_id: int,
        from_date: date,
        through_date: date,
    ) -> int:
        if through_date < from_date:
            raise BadRequestError(message="through_date must be on or after from_date.")

        templates = self.list_templates(staff_profile_id=staff_profile_id, only_active=True)
        if not templates:
            return 0

        time_offs = (
            self.db.query(DoctorTimeOff)
            .filter(
                DoctorTimeOff.staff_profile_id == staff_profile_id,
                DoctorTimeOff.is_deleted.is_(False),
                DoctorTimeOff.starts_at <= datetime.combine(through_date, time.max),
                DoctorTimeOff.ends_at >= datetime.combine(from_date, time.min),
            )
            .all()
        )

        created = 0
        cursor = from_date
        while cursor <= through_date:
            weekday = cursor.weekday()
            todays_templates = [t for t in templates if t.weekday == weekday]
            for tpl in todays_templates:
                start_h, start_m = (int(x) for x in tpl.start_time.split(":"))
                end_h, end_m = (int(x) for x in tpl.end_time.split(":"))
                slot_dur = timedelta(minutes=int(tpl.slot_duration_minutes or 30))
                slot_start = datetime.combine(cursor, time(start_h, start_m))
                day_end = datetime.combine(cursor, time(end_h, end_m))
                while slot_start + slot_dur <= day_end:
                    slot_end = slot_start + slot_dur

                    blocked = self._is_blocked(time_offs, slot_start, slot_end)

                    exists = (
                        self.db.query(AppointmentSlot)
                        .filter(
                            AppointmentSlot.staff_profile_id == staff_profile_id,
                            AppointmentSlot.starts_at == slot_start,
                            AppointmentSlot.ends_at == slot_end,
                        )
                        .first()
                    )
                    if exists is not None:
                        # Update blocked-state if the time-off changed.
                        desired = (
                            AppointmentSlotStatus.BLOCKED if blocked
                            else exists.status
                        )
                        if desired != exists.status and exists.status == AppointmentSlotStatus.OPEN:
                            exists.status = AppointmentSlotStatus.BLOCKED
                            exists.block_reason = "Doctor unavailable"
                        slot_start = slot_end
                        continue

                    slot = AppointmentSlot(
                        staff_profile_id=staff_profile_id,
                        facility_id=tpl.facility_id,
                        service_delivery_point_id=tpl.service_delivery_point_id,
                        starts_at=slot_start,
                        ends_at=slot_end,
                        capacity=int(tpl.max_patients_per_slot or 1),
                        booked_count=0,
                        appointment_type=tpl.appointment_type,
                        status=(
                            AppointmentSlotStatus.BLOCKED if blocked
                            else AppointmentSlotStatus.OPEN
                        ),
                        block_reason=("Doctor unavailable" if blocked else None),
                    )
                    self.db.add(slot)
                    created += 1
                    slot_start = slot_end
            cursor += timedelta(days=1)

        self.db.commit()
        return created

    @staticmethod
    def _is_blocked(time_offs, slot_start: datetime, slot_end: datetime) -> bool:
        for off in time_offs:
            if off.availability_type != DoctorAvailabilityType.BLOCKED:
                continue
            if off.ends_at <= slot_start or off.starts_at >= slot_end:
                continue
            return True
        return False

    @staticmethod
    def _validate_hhmm(value: str, field: str) -> None:
        try:
            h, m = value.split(":")
            if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
                raise ValueError
        except Exception:
            raise BadRequestError(message=f"{field} must be in HH:MM 24-hour format.")

    # ------------------------------------------------------------------
    # CALENDAR VIEWS
    # ------------------------------------------------------------------

    def slots_in_range(
        self,
        *,
        staff_profile_id: Optional[int] = None,
        from_dt: datetime,
        to_dt: datetime,
        appointment_type: Optional[str] = None,
        only_open: bool = False,
    ) -> list[AppointmentSlot]:
        q = self.db.query(AppointmentSlot).filter(
            AppointmentSlot.starts_at >= from_dt,
            AppointmentSlot.ends_at <= to_dt,
            AppointmentSlot.is_deleted.is_(False),
        )
        if staff_profile_id is not None:
            q = q.filter(AppointmentSlot.staff_profile_id == staff_profile_id)
        if appointment_type:
            q = q.filter(AppointmentSlot.appointment_type == appointment_type)
        if only_open:
            q = q.filter(AppointmentSlot.status == AppointmentSlotStatus.OPEN)
        return q.order_by(AppointmentSlot.starts_at).all()

    def doctor_workload(
        self,
        *,
        staff_profile_id: int,
        on_date: date,
    ) -> dict:
        from_dt = datetime.combine(on_date, time.min)
        to_dt = datetime.combine(on_date, time.max)
        slots = self.slots_in_range(staff_profile_id=staff_profile_id, from_dt=from_dt, to_dt=to_dt)
        booked = [s for s in slots if s.status == AppointmentSlotStatus.BOOKED]
        open_ = [s for s in slots if s.status == AppointmentSlotStatus.OPEN]
        blocked = [s for s in slots if s.status == AppointmentSlotStatus.BLOCKED]

        # Pending vs completed breakdown via the actual Appointment statuses.
        appt_ids = [s.appointment_id for s in booked if s.appointment_id]
        completed = pending = missed = 0
        if appt_ids:
            for a in self.db.query(Appointment).filter(Appointment.id.in_(appt_ids)).all():
                status = str(getattr(a.status, "value", a.status) or "").upper()
                if status == "COMPLETED":
                    completed += 1
                elif status in {"MISSED", "NO_SHOW"}:
                    missed += 1
                else:
                    pending += 1

        return {
            "staff_profile_id": staff_profile_id,
            "date": on_date.isoformat(),
            "open_slots": len(open_),
            "booked_slots": len(booked),
            "blocked_slots": len(blocked),
            "appointments_pending": pending,
            "appointments_completed": completed,
            "appointments_missed": missed,
        }

    # ------------------------------------------------------------------
    # SLOT BOOKING
    # ------------------------------------------------------------------

    def reserve_slot(self, *, slot_id: int, appointment_id: int) -> AppointmentSlot:
        slot = (
            self.db.query(AppointmentSlot)
            .filter(AppointmentSlot.id == slot_id, AppointmentSlot.is_deleted.is_(False))
            .first()
        )
        if slot is None:
            raise NotFoundError(message="Slot not found.")
        if slot.status not in {AppointmentSlotStatus.OPEN}:
            raise BadRequestError(
                message=f"Slot cannot be booked from status {slot.status}.",
            )
        if slot.booked_count >= slot.capacity:
            raise BadRequestError(message="Slot is full.")
        slot.booked_count += 1
        slot.appointment_id = appointment_id
        if slot.booked_count >= slot.capacity:
            slot.status = AppointmentSlotStatus.BOOKED
        self.db.commit()
        self.db.refresh(slot)
        return slot

    def release_slot(self, *, slot_id: int) -> AppointmentSlot:
        slot = (
            self.db.query(AppointmentSlot)
            .filter(AppointmentSlot.id == slot_id, AppointmentSlot.is_deleted.is_(False))
            .first()
        )
        if slot is None:
            raise NotFoundError(message="Slot not found.")
        slot.booked_count = max(0, (slot.booked_count or 0) - 1)
        slot.appointment_id = None
        if slot.status == AppointmentSlotStatus.BOOKED and slot.booked_count < slot.capacity:
            slot.status = AppointmentSlotStatus.OPEN
        self.db.commit()
        self.db.refresh(slot)
        return slot
