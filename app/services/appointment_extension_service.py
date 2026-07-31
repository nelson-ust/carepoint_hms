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

    # Appointment statuses for which a reminder should no longer fire.
    _CLOSED_STATUSES = {"CANCELLED", "COMPLETED", "MISSED"}

    def schedule_patient_reminders(
        self,
        appointment: Appointment,
        *,
        channels: Optional[list[str]] = None,
    ) -> list[AppointmentReminderJob]:
        """
        Schedule the two standard patient reminders for an appointment:
        one a **day before** and one **3 hours before** the start time.

        The 3-hour reminder uses the CUSTOM rule (offset 180 min) rather than a
        dedicated enum value, so no database enum migration is required for it
        to work. Reminders whose fire time is already in the past (e.g. a
        booking made under 3 hours out) are silently skipped.
        """
        return self.schedule_reminders(
            appointment,
            rules=(
                AppointmentReminderRule.H24_BEFORE,
                AppointmentReminderRule.CUSTOM,
            ),
            custom_offset_minutes=180,
            channels=channels,
        )

    def reschedule_reminders(
        self,
        appointment: Appointment,
        *,
        channels: Optional[list[str]] = None,
    ) -> list[AppointmentReminderJob]:
        """
        Void any still-pending reminder jobs for an appointment and schedule a
        fresh day-before + 3-hours-before pair against its (new) start time.
        Called after a reschedule so reminders track the moved slot.
        """
        pending = (
            self.db.query(AppointmentReminderJob)
            .filter(
                AppointmentReminderJob.appointment_id == appointment.id,
                AppointmentReminderJob.status == "PENDING",
                AppointmentReminderJob.is_deleted.is_(False),
            )
            .all()
        )
        for job in pending:
            job.status = "SKIPPED"
            job.last_error = "superseded by reschedule"
            job.is_deleted = True
        if pending:
            self.db.commit()
        return self.schedule_patient_reminders(appointment, channels=channels)

    @staticmethod
    def _friendly_lead(minutes: int) -> str:
        """Human phrase for how far ahead a reminder is (from the offset)."""
        if minutes >= 23 * 60:
            return "tomorrow"
        if minutes >= 60:
            hours = round(minutes / 60)
            return f"in about {hours} hour{'s' if hours != 1 else ''}"
        return f"in about {max(1, minutes)} minutes"

    def _build_reminder_message(self, appt: Appointment, job: AppointmentReminderJob):
        """Return (subject, body) for a patient appointment reminder."""
        start = appt.scheduled_start_at
        # Offset in minutes between the appointment and when this reminder fires.
        try:
            offset_min = int(round((start - job.fire_at).total_seconds() / 60.0))
        except Exception:
            offset_min = 0
        lead = self._friendly_lead(offset_min)

        patient = getattr(appt, "patient", None)
        first_name = (getattr(patient, "first_name", None) or "there").strip() or "there"

        when_date = f"{start:%A, %d %B %Y}"
        when_time = f"{start:%I:%M %p}".lstrip("0")

        # Optional context lines.
        clinician = None
        sp = getattr(appt, "staff_profile", None)
        if sp is not None:
            u = getattr(sp, "user", None)
            if u is not None:
                clinician = f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
        sdp = getattr(getattr(appt, "service_delivery_point", None), "name", None)
        facility = getattr(getattr(appt, "facility", None), "name", None)

        details = [f"Date: {when_date}", f"Time: {when_time}"]
        if clinician:
            details.append(f"With: {clinician}")
        if sdp:
            details.append(f"Location: {sdp}")
        if facility:
            details.append(f"Facility: {facility}")

        subject = f"Appointment reminder — {when_date} at {when_time}"
        body = (
            f"Dear {first_name},\n\n"
            f"This is a friendly reminder that you have an appointment {lead}.\n\n"
            + "\n".join(details)
            + "\n\nPlease arrive a few minutes early. If you need to reschedule or "
            "cancel, kindly contact the hospital ahead of time.\n\n"
            "We look forward to seeing you."
        )
        return subject, body

    def dispatch_due_reminders(self) -> dict:
        """
        Walk PENDING reminder jobs whose ``fire_at`` has passed and dispatch
        them through the unified NotificationDispatcher. Run from the scheduler
        on a short interval.

        Delivery reaches the patient even when they have no portal user account:
        the recipient carries the patient's own email and phone so email/SMS go
        out regardless, while in-app/push are used when a linked user exists.
        Reminders for appointments that are no longer open (cancelled/completed/
        missed) are skipped rather than sent.
        """
        from sqlalchemy.orm import joinedload

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
        skipped = 0
        try:
            from app.services.notification_dispatcher import NotificationDispatcher

            dispatcher = NotificationDispatcher(self.db)
        except Exception:
            dispatcher = None

        for job in due:
            try:
                appt = (
                    self.db.query(Appointment)
                    .options(
                        joinedload(Appointment.patient),
                        joinedload(Appointment.staff_profile),
                        joinedload(Appointment.service_delivery_point),
                    )
                    .filter(Appointment.id == job.appointment_id)
                    .first()
                )
                if appt is None:
                    job.status = "SKIPPED"
                    job.last_error = "appointment missing"
                    skipped += 1
                    continue

                # Don't remind for appointments that are no longer open.
                if str(getattr(appt, "status", "")).upper() in self._CLOSED_STATUSES:
                    job.status = "SKIPPED"
                    job.last_error = f"appointment {appt.status}"
                    skipped += 1
                    continue

                if dispatcher is None:
                    job.status = "FAILED"
                    job.last_error = "notification dispatcher unavailable"
                    failed += 1
                    continue

                patient = getattr(appt, "patient", None)
                email = getattr(patient, "email", None) if patient else None
                phone = getattr(patient, "phone_number", None) if patient else None
                user_id = getattr(patient, "user_id", None) if patient else None

                if not email and not phone and not user_id:
                    job.status = "SKIPPED"
                    job.last_error = "patient has no contact details"
                    skipped += 1
                    continue

                # A dict recipient lets the dispatcher deliver via the patient's
                # own email/phone; user_id (when present) enables in-app/push,
                # and patient_id lets any in-app row surface in the portal feed.
                recipient = {
                    "user_id": user_id,
                    "patient_id": getattr(patient, "id", None),
                    "email_address": email,
                    "sms_address": phone,
                    "whatsapp_address": phone,
                }

                subject, body = self._build_reminder_message(appt, job)
                dispatcher.dispatch(
                    event=NotificationEvent.APPOINTMENT_REMINDER,
                    recipients=[recipient],
                    subject=subject,
                    body=body,
                    context={
                        "appointment_id": appt.id,
                        "appointment_code": appt.appointment_code,
                        "rule": job.rule.value if job.rule else None,
                        "scheduled_start_at": appt.scheduled_start_at.isoformat()
                        if appt.scheduled_start_at
                        else None,
                    },
                    force_channels=(job.channels or None),
                    # The portal's own on-load generator owns the in-app reminder
                    # row, so exclude in_app here to avoid a duplicate in the
                    # patient's portal feed; the scheduler still sends email/SMS.
                    exclude_channels=["in_app"],
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
        return {
            "due": len(due),
            "dispatched": dispatched,
            "skipped": skipped,
            "failed": failed,
        }

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
