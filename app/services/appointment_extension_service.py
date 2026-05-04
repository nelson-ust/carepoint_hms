"""
Appointment-extension service.

Sits alongside the existing AppointmentService and adds three things:

* **Reminder jobs** — materialise :class:`AppointmentReminderJob` rows
  at booking time, dispatched by the scheduler when ``fire_at`` is due.
* **Cancellation log** — append-only history of cancel / reschedule /
  no-show actions (per the requirement: "Maintain appointment history").
* **Recurrence series** — expand a parent Appointment + recurrence rule
  into the next N child appointments.

This service is intentionally additive: it does not modify the
existing Appointment model or routes.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.enums import (
    AppointmentRecurrence,
    AppointmentReminderRule,
    NotificationEvent,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    Appointment,
    AppointmentCancellationLog,
    AppointmentRecurrenceRule,
    AppointmentReminderJob,
)


logger = logging.getLogger(__name__)


# Default reminder rules expressed as (rule, minutes-before).
RULE_OFFSETS_MINUTES: dict[AppointmentReminderRule, int] = {
    AppointmentReminderRule.H24_BEFORE: 24 * 60,
    AppointmentReminderRule.H2_BEFORE: 120,
    AppointmentReminderRule.H1_BEFORE: 60,
    AppointmentReminderRule.M30_BEFORE: 30,
    AppointmentReminderRule.M15_BEFORE: 15,
}


class AppointmentExtensionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # REMINDERS
    # ------------------------------------------------------------------

    def schedule_reminders(
        self,
        appointment: Appointment,
        *,
        rules: Iterable[AppointmentReminderRule] = (
            AppointmentReminderRule.H24_BEFORE,
            AppointmentReminderRule.H2_BEFORE,
        ),
        channels: Optional[list[str]] = None,
        custom_offset_minutes: Optional[int] = None,
    ) -> list[AppointmentReminderJob]:
        if appointment.scheduled_start_at is None:
            return []

        out: list[AppointmentReminderJob] = []
        for rule in rules:
            if rule == AppointmentReminderRule.CUSTOM:
                offset = custom_offset_minutes
                if offset is None:
                    continue
            else:
                offset = RULE_OFFSETS_MINUTES.get(rule)
                if offset is None:
                    continue

            fire_at = appointment.scheduled_start_at - timedelta(minutes=int(offset))
            if fire_at <= datetime.now(timezone.utc):
                # Don't schedule reminders that are already in the past.
                continue

            # Idempotency: don't double-create a reminder for the same rule.
            exists = (
                self.db.query(AppointmentReminderJob)
                .filter(
                    AppointmentReminderJob.appointment_id == appointment.id,
                    AppointmentReminderJob.rule == rule,
                    AppointmentReminderJob.is_deleted.is_(False),
                )
                .first()
            )
            if exists is not None:
                out.append(exists)
                continue

            job = AppointmentReminderJob(
                appointment_id=appointment.id,
                rule=rule,
                fire_at=fire_at,
                channels=list(channels or []),
                status="PENDING",
            )
            self.db.add(job)
            out.append(job)
        self.db.commit()
        return out

    def dispatch_due_reminders(self) -> dict:
        """
        Walk PENDING reminder jobs whose ``fire_at`` has passed and
        dispatch them through the unified NotificationDispatcher. Run
        from the scheduler every minute.
        """
        now = datetime.now(timezone.utc)
        due = (
            self.db.query(AppointmentReminderJob)
            .filter(
                AppointmentReminderJob.status == "PENDING",
                AppointmentReminderJob.fire_at <= now,
                AppointmentReminderJob.is_deleted.is_(False),
            )
            .limit(500)
            .all()
        )

        dispatched = 0
        failed = 0
        try:
            from app.models.all_models import Patient, User
            from app.services.notification_dispatcher import NotificationDispatcher

            dispatcher = NotificationDispatcher(self.db)
        except Exception:
            dispatcher = None

        for job in due:
            try:
                appt = (
                    self.db.query(Appointment)
                    .filter(Appointment.id == job.appointment_id)
                    .first()
                )
                if appt is None:
                    job.status = "SKIPPED"
                    job.last_error = "appointment missing"
                    continue
                if dispatcher is None:
                    job.status = "FAILED"
                    job.last_error = "notification dispatcher unavailable"
                    failed += 1
                    continue

                # Resolve recipient — patient.user when present.
                user = None
                patient = (
                    self.db.query(Patient)
                    .filter(Patient.id == appt.patient_id)
                    .first()
                )
                if patient and getattr(patient, "user_id", None):
                    user = (
                        self.db.query(User)
                        .filter(User.id == patient.user_id, User.is_deleted.is_(False))
                        .first()
                    )
                if user is None:
                    job.status = "SKIPPED"
                    job.last_error = "no recipient resolvable"
                    continue

                dispatcher.dispatch(
                    event=NotificationEvent.APPOINTMENT_REMINDER,
                    recipients=[user],
                    subject=f"Reminder: appointment at {appt.scheduled_start_at:%Y-%m-%d %H:%M}",
                    body=(
                        f"This is a reminder of your appointment at "
                        f"{appt.scheduled_start_at:%Y-%m-%d %H:%M}."
                    ),
                    context={"appointment_id": appt.id, "rule": job.rule.value},
                    force_channels=job.channels or None,
                )
                job.status = "SENT"
                job.fired_at = datetime.now(timezone.utc)
                dispatched += 1
            except Exception as exc:
                failed += 1
                job.status = "FAILED"
                job.last_error = str(exc)[:500]

        if due:
            self.db.commit()
        return {"due": len(due), "dispatched": dispatched, "failed": failed}

    # ------------------------------------------------------------------
    # CANCELLATION LOG
    # ------------------------------------------------------------------

    def log_cancellation(
        self,
        *,
        appointment_id: int,
        action: str,
        reason: Optional[str] = None,
        actor_user_id: Optional[int] = None,
        previous_start_at: Optional[datetime] = None,
        new_start_at: Optional[datetime] = None,
    ) -> AppointmentCancellationLog:
        if action.upper() not in {"CANCELLED", "RESCHEDULED", "NO_SHOW"}:
            raise BadRequestError(
                message="action must be CANCELLED, RESCHEDULED or NO_SHOW.",
            )
        rec = AppointmentCancellationLog(
            appointment_id=appointment_id,
            action=action.upper(),
            reason=reason,
            actor_user_id=actor_user_id,
            previous_start_at=previous_start_at,
            new_start_at=new_start_at,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def history(self, appointment_id: int) -> list[AppointmentCancellationLog]:
        return (
            self.db.query(AppointmentCancellationLog)
            .filter(
                AppointmentCancellationLog.appointment_id == appointment_id,
                AppointmentCancellationLog.is_deleted.is_(False),
            )
            .order_by(AppointmentCancellationLog.occurred_at.asc())
            .all()
        )

    # ------------------------------------------------------------------
    # RECURRENCE
    # ------------------------------------------------------------------

    def create_recurrence(
        self,
        *,
        parent_appointment_id: int,
        recurrence: AppointmentRecurrence,
        interval_count: int = 1,
        occurrences: Optional[int] = None,
        until_date: Optional[date] = None,
        weekdays: Optional[list[int]] = None,
    ) -> AppointmentRecurrenceRule:
        if not occurrences and not until_date:
            raise BadRequestError(
                message="Either occurrences or until_date must be provided.",
            )
        rec = AppointmentRecurrenceRule(
            parent_appointment_id=parent_appointment_id,
            recurrence=recurrence,
            interval_count=int(interval_count or 1),
            occurrences=occurrences,
            until_date=until_date,
            weekdays=weekdays,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def expand_recurrence(
        self,
        rule: AppointmentRecurrenceRule,
        *,
        max_create: int = 24,
    ) -> list[Appointment]:
        """
        Expand a recurrence rule into concrete child Appointments.

        We create up to ``max_create`` future occurrences. Re-running is
        safe — existing children are skipped via metadata stamp.
        """
        parent = (
            self.db.query(Appointment)
            .filter(Appointment.id == rule.parent_appointment_id)
            .first()
        )
        if parent is None:
            raise NotFoundError(message="Parent appointment not found.")
        if parent.scheduled_start_at is None:
            return []

        step_days_map = {
            AppointmentRecurrence.DAILY: 1,
            AppointmentRecurrence.WEEKLY: 7,
            AppointmentRecurrence.BIWEEKLY: 14,
            AppointmentRecurrence.MONTHLY: 30,
        }
        step_days = step_days_map.get(rule.recurrence)
        if not step_days or rule.recurrence == AppointmentRecurrence.NONE:
            return []
        step = timedelta(days=step_days * int(rule.interval_count or 1))

        max_n = int(rule.occurrences or max_create)
        cursor = parent.scheduled_start_at
        duration = (
            (parent.scheduled_end_at - parent.scheduled_start_at)
            if parent.scheduled_end_at
            else timedelta(minutes=30)
        )
        out: list[Appointment] = []
        for _ in range(max_n):
            cursor = cursor + step
            if rule.until_date and cursor.date() > rule.until_date:
                break
            # Skip if a child at this slot already exists (idempotency
            # via metadata pointer).
            child = (
                self.db.query(Appointment)
                .filter(
                    Appointment.patient_id == parent.patient_id,
                    Appointment.staff_profile_id == parent.staff_profile_id,
                    Appointment.scheduled_start_at == cursor,
                    Appointment.is_deleted.is_(False),
                )
                .first()
            )
            if child is not None:
                out.append(child)
                continue
            new = Appointment(
                patient_id=parent.patient_id,
                staff_profile_id=parent.staff_profile_id,
                service_delivery_point_id=parent.service_delivery_point_id,
                scheduled_start_at=cursor,
                scheduled_end_at=cursor + duration,
                reason=parent.reason,
                appointment_code=f"{parent.appointment_code}-R{cursor:%Y%m%d}",
                status=parent.status,
            )
            self.db.add(new)
            out.append(new)
        self.db.commit()
        return out
