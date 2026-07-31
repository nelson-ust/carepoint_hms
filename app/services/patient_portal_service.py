# app/services/patient_portal_service.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.enums import NotificationChannel, NotificationStatus
from app.core.exceptions import NotFoundError, BadRequestError
from app.models.all_models import Patient, User, MembershipCard, Notification, LabResult, LabOrderItem, LabOrder, Visit, Appointment
from app.repositories.membership_card_repository import MembershipCardRepository
from app.repositories.notification_repository import NotificationRepository
from app.schemas.patient_portal_schemas import (
    PatientPortalDashboard,
    PatientPortalProfile,
    PortalProfileUpdateSchema,
)
from app.schemas.patient_schemas import PatientUpdateSchema
from app.services.patient_service import PatientService
from app.services.membership_card_service import MembershipCardService
from app.services.notification_service import NotificationService


# Event code stamped on the in-app appointment reminders the portal generates,
# so they can be de-duplicated per (appointment, reminder-kind).
APPOINTMENT_REMINDER_EVENT = "appointment.reminder"

# The two patient-facing reminders required: one a day before the appointment
# date, and one three hours before the appointment time.
_REMINDER_WINDOWS = (
    ("DAY_BEFORE", timedelta(days=1)),
    ("THREE_HOURS", timedelta(hours=3)),
)


class PatientPortalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.patient_service = PatientService(db)
        self.membership_card_service = MembershipCardService(db)
        self.notification_service = NotificationService(db)
        self.card_repo = MembershipCardRepository(db)
        self.notification_repo = NotificationRepository(db)

    def get_patient_by_user_id(self, user_id: int) -> Patient:
        patient = self.db.query(Patient).filter(Patient.user_id == user_id).first()
        if not patient:
            raise NotFoundError(message="No patient record linked to this user account.")
        return patient

    def set_profile_photo(self, user_id: int, *, file_name: str, file_url: str,
                          file_key: str | None = None):
        """Persist the patient's uploaded profile photo. Returns (patient,
        previous_local_key) so the caller can clean up the old file."""
        patient = self.get_patient_by_user_id(user_id)
        previous_key = getattr(patient, "photo_file_key", None)
        patient.photo_file_name = file_name
        patient.photo_file_url = file_url
        patient.photo_file_key = file_key
        self.db.add(patient)
        self.db.commit()
        self.db.refresh(patient)
        return patient, previous_key

    def get_dashboard(self, user_id: int) -> PatientPortalDashboard:
        patient = self.get_patient_by_user_id(user_id)

        # Surface any appointment reminders whose time has arrived (a day
        # before and 3 hours before) so the patient sees them on the dashboard.
        self._materialize_due_appointment_reminders(patient)

        # Get active membership card
        cards = self.membership_card_service.list_patient_cards(patient.id)
        card = cards[0] if cards else None
        
        recent_transactions = []
        if card:
            recent_transactions = self.membership_card_service.get_card_transactions(card.id)[:5]
            
        # Get recent released lab results
        recent_lab_results = self.db.query(LabResult).join(
            LabOrderItem, LabResult.lab_order_item_id == LabOrderItem.id
        ).join(
            LabOrder, LabOrderItem.lab_order_id == LabOrder.id
        ).join(
            Visit, LabOrder.visit_id == Visit.id
        ).filter(
            Visit.patient_id == patient.id,
            LabResult.result_status == "RELEASED"
        ).order_by(LabResult.released_at.desc()).limit(5).all()

        unread_notifications = self.notification_repo.count_unread(
            patient_id=patient.id
        )

        # A short preview of the latest unread notifications (appointment
        # reminders, portal messages, etc.) for the dashboard.
        recent_notifications = self.notification_repo.list_notifications(
            patient_id=patient.id,
            skip=0,
            limit=5,
            unread_only=True,
        )[0]

        wallet_balance = getattr(card, "balance", None) or 0

        return PatientPortalDashboard(
            patient=patient,
            card=card,
            wallet_balance=wallet_balance,
            recent_transactions=recent_transactions,
            recent_lab_results=recent_lab_results,
            unread_notifications_count=unread_notifications,
            recent_notifications=recent_notifications,
        )

    def get_profile(self, user_id: int) -> PatientPortalProfile:
        patient = self.get_patient_by_user_id(user_id)
        user = self.db.query(User).get(user_id)
        
        return PatientPortalProfile(
            patient=patient,
            username=user.username,
            email=user.email
        )

    def update_profile(
        self, user_id: int, payload: "PortalProfileUpdateSchema"
    ) -> PatientPortalProfile:
        """
        Let a patient self-update a safe subset of their record from the portal
        (national ID, contact details, emergency contact & next of kin).

        Only the fields explicitly supplied are changed. Validation and the
        demographic audit trail are handled by PatientService.update_patient.
        """
        patient = self.get_patient_by_user_id(user_id)
        data = payload.model_dump(exclude_unset=True)
        if data:
            self.patient_service.update_patient(
                patient.id,
                PatientUpdateSchema(**data),
                changed_by_id=user_id,
                change_source="PORTAL_SELF_UPDATE",
                audit_note="Patient self-service update via portal profile.",
            )
        return self.get_profile(user_id)

    def list_notifications(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 20,
        unread_only: bool = True,
    ) -> List[Notification]:
        """
        Return the patient's notification feed.

        By default only *unread* notifications are returned, so that once a
        patient reads (acknowledges) a notification it clears out of the list.
        Pass ``unread_only=False`` to include already-read history.
        """
        patient = self.get_patient_by_user_id(user_id)
        # Ensure due appointment reminders exist before listing, so a patient
        # who opens the notifications page directly still sees them.
        self._materialize_due_appointment_reminders(patient)
        return self.notification_repo.list_notifications(
            patient_id=patient.id,
            skip=skip,
            limit=limit,
            unread_only=unread_only,
        )[0]

    # ------------------------------------------------------------------
    # APPOINTMENT REMINDERS (in-app, patient-facing)
    # ------------------------------------------------------------------

    def _materialize_due_appointment_reminders(self, patient: Patient) -> None:
        """
        Create the patient's in-app appointment reminders on demand.

        For every still-active, future appointment we create two IN_APP
        notifications *once their time arrives*: one a **day before** the
        appointment date, and one **3 hours before** the appointment time.

        These are stamped with the patient id (so they show in the portal feed)
        and de-duplicated per (appointment, reminder-kind) via ``event_code`` +
        ``payload_metadata``, so opening the dashboard repeatedly never creates
        duplicates. This runs independently of the background reminder
        scheduler (which handles email/SMS), guaranteeing the patient sees the
        reminder in the portal even when no worker is running.
        """
        from app.core.enums import AppointmentStatus
        from app.repositories.appointment_repository import AppointmentRepository

        now = datetime.now(timezone.utc)

        repo = AppointmentRepository(self.db)
        # A single patient's appointment volume is small; pull the lot.
        appointments, _ = repo.list_appointments(patient_id=patient.id, skip=0, limit=500)

        active_statuses = {
            AppointmentStatus.SCHEDULED,
            AppointmentStatus.ARRIVED,
            AppointmentStatus.IN_PROGRESS,
            AppointmentStatus.RESCHEDULED,
        }

        # Reminders already generated for this patient, keyed by (appt_id, kind).
        existing = self.notification_repo.list_by_event(
            patient_id=patient.id, event_code=APPOINTMENT_REMINDER_EVENT
        )
        already: set[tuple[int, str]] = set()
        for n in existing:
            meta = n.payload_metadata or {}
            appt_id, kind = meta.get("appointment_id"), meta.get("kind")
            if appt_id is not None and kind:
                already.add((int(appt_id), str(kind)))

        def _aware(dt: Optional[datetime]) -> Optional[datetime]:
            if dt is not None and dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        created = False
        for appt in appointments:
            if appt.status not in active_statuses:
                continue
            start = _aware(appt.scheduled_start_at)
            if start is None or start <= now:
                continue  # only remind for appointments still in the future

            for kind, lead in _REMINDER_WINDOWS:
                trigger_at = start - lead
                if now < trigger_at:
                    continue  # this reminder's window hasn't opened yet
                if (appt.id, kind) in already:
                    continue  # already generated

                subject, body = self._build_appointment_reminder(appt, kind, start)
                self.notification_repo.create(
                    channel=NotificationChannel.IN_APP,
                    body=body,
                    subject=subject,
                    patient_id=patient.id,
                    status=NotificationStatus.SENT,
                    sent_at=now,
                    event_code=APPOINTMENT_REMINDER_EVENT,
                    payload_metadata={
                        "appointment_id": appt.id,
                        "kind": kind,
                        "appointment_code": getattr(appt, "appointment_code", None),
                        "scheduled_start_at": start.isoformat(),
                    },
                )
                already.add((appt.id, kind))
                created = True

        if created:
            self.db.commit()

    @staticmethod
    def _build_appointment_reminder(
        appt: Appointment, kind: str, start: datetime
    ) -> tuple[str, str]:
        """Return (subject, body) for an appointment reminder notification."""
        when_date = f"{start:%A, %d %B %Y}"
        when_time = f"{start:%I:%M %p}".lstrip("0")
        lead = "tomorrow" if kind == "DAY_BEFORE" else "in about 3 hours"

        details = [f"Date: {when_date}", f"Time: {when_time}"]
        code = getattr(appt, "appointment_code", None)
        if code:
            details.append(f"Reference: {code}")

        subject = "Appointment reminder"
        body = (
            f"This is a reminder that you have an appointment {lead} — "
            f"{when_date} at {when_time}.\n"
            + "\n".join(details)
            + "\n\nPlease arrive a few minutes early. Contact the hospital if "
            "you need to reschedule or cancel."
        )
        return subject, body

    def mark_notification_read(self, user_id: int, notification_id: int) -> Notification:
        """
        Mark a single notification as READ for the logged-in patient.

        The notification must belong to this patient; otherwise a
        :class:`NotFoundError` is raised so one patient can never acknowledge
        (or probe for) another patient's notifications.
        """
        patient = self.get_patient_by_user_id(user_id)
        notification = self.notification_repo.get_by_id(notification_id)
        if notification is None or notification.patient_id != patient.id:
            raise NotFoundError(
                message="Notification not found.",
                detail={"notification_id": notification_id},
            )
        notification = self.notification_repo.mark_read(notification)
        self.db.commit()
        return self.notification_repo.get_required_by_id(notification.id)

    def mark_all_notifications_read(self, user_id: int) -> int:
        """Mark every unread notification for the patient as READ. Returns the count."""
        patient = self.get_patient_by_user_id(user_id)
        updated = self.notification_repo.mark_all_read(patient_id=patient.id)
        self.db.commit()
        return updated

    def get_branding(self) -> "PatientPortalBranding":
        """
        Public hospital branding for the portal: name (from the master Tenant
        record) + logo/colours (from the tenant's TenantSetting). Safe to call
        without an authenticated patient; resolves purely from tenant context.
        """
        from app.core.multitenancy import get_current_tenant
        from app.models.all_models import TenantSetting
        from app.schemas.patient_portal_schemas import PatientPortalBranding

        tenant = get_current_tenant()
        setting = self.db.query(TenantSetting).first()
        return PatientPortalBranding(
            hospital_name=(tenant.name if tenant else None),
            logo_url=(setting.logo_url if setting else None),
            primary_color=(setting.primary_color if setting else None),
            secondary_color=(setting.secondary_color if setting else None),
        )

    def list_appointments(self, user_id: int) -> "PatientPortalAppointments":
        """
        Return every appointment the logged-in patient has ever scheduled,
        grouped so the portal can highlight the *current* (next upcoming) one.

        Upcoming = still-active status (SCHEDULED / ARRIVED / IN_PROGRESS /
        RESCHEDULED) with a start time now or in the future, sorted
        soonest-first. Everything else (elapsed, completed, cancelled, missed)
        is "past", sorted most-recent-first.
        """
        from datetime import datetime, timezone

        from app.core.enums import AppointmentStatus
        from app.repositories.appointment_repository import AppointmentRepository
        from app.schemas.patient_portal_schemas import PatientPortalAppointments

        patient = self.get_patient_by_user_id(user_id)
        repo = AppointmentRepository(self.db)
        # A single patient's lifetime appointment volume is small; pull them all.
        items, total = repo.list_appointments(patient_id=patient.id, skip=0, limit=1000)

        now = datetime.now(timezone.utc)
        active_statuses = {
            AppointmentStatus.SCHEDULED,
            AppointmentStatus.ARRIVED,
            AppointmentStatus.IN_PROGRESS,
            AppointmentStatus.RESCHEDULED,
        }

        def _aware(dt):
            if dt is not None and dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        upcoming: List = []
        past: List = []
        for appt in items:
            start = _aware(appt.scheduled_start_at)
            is_future = start is not None and start >= now
            if appt.status in active_statuses and is_future:
                upcoming.append(appt)
            else:
                past.append(appt)

        # Repository already returns start-ascending; that's correct for
        # "upcoming" (soonest first). Past reads best most-recent-first.
        past.sort(key=lambda a: _aware(a.scheduled_start_at) or now, reverse=True)

        return PatientPortalAppointments(
            total=total,
            upcoming_count=len(upcoming),
            past_count=len(past),
            next_appointment=upcoming[0] if upcoming else None,
            upcoming=upcoming,
            past=past,
        )
