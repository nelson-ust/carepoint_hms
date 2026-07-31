from __future__ import annotations
import logging
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.portal_repository import PortalRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.permission_repository import PermissionRepository
from app.repositories.notification_repository import NotificationRepository
from app.core.enums import NotificationChannel, NotificationStatus
from app.schemas.portal_schemas import (
    PortalAccountCreateSchema,
    PortalAppointmentRequestCreateSchema,
    PortalMessageCreateSchema,
    PortalDocumentShareCreateSchema
)
from app.core.security import get_password_hash, validate_password_strength

logger = logging.getLogger(__name__)

# Permission that gates the staff patient-message inbox — also the audience
# that gets notified when a patient writes in.
PORTAL_MESSAGE_PERMISSION = "PORTAL_MESSAGE_READ"
# Event code stamped on the staff notification raised for a new patient message.
PORTAL_MESSAGE_EVENT = "portal.message.received"


class PortalService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = PortalRepository(db)
        self.patient_repository = PatientRepository(db)
        self.permission_repository = PermissionRepository(db)
        self.notification_repository = NotificationRepository(db)

    def register_portal_account(self, data: PortalAccountCreateSchema):
        # 1. Ensure patient exists
        patient = self.patient_repository.get_by_id(data.patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
            
        # 2. Check if account already exists
        existing = self.repository.get_account_by_username(data.portal_username)
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
            
        # 3. Validate password strength
        validate_password_strength(data.password)
        
        # 4. Hash password and create
        pwd_hash = get_password_hash(data.password)
        account = self.repository.create_account(data, pwd_hash)
        self.db.commit()
        return account

    def request_appointment(self, patient_id: int, data: PortalAppointmentRequestCreateSchema):
        """
        Handle a patient-initiated appointment request from the portal.

        Previously this only recorded a ``PortalAppointmentRequest`` (a triage
        row) and never produced an actual ``Appointment`` — so the booking was
        invisible to the hospital and the "we'll confirm your time" response was
        effectively a dead end. We now also create a real appointment and link
        it back to the request (``converted_appointment_id`` + ``SCHEDULED``),
        so the booking shows up in the Appointments registry immediately.
        """
        from app.core.enums import PortalAppointmentRequestStatus
        from app.schemas.appointment_schemas import AppointmentCreateSchema
        from app.services.appointment_service import AppointmentService

        # 1. Record the patient's request (kept as triage/audit history).
        request = self.repository.create_appointment_request(patient_id, data)

        # 2. Book a real appointment from the requested details. Existence and
        #    double-booking checks run inside book_appointment; a genuine slot
        #    conflict (only possible when a specific clinician was chosen) raises
        #    a clear error instead of a false success.
        appointment = AppointmentService(self.db).book_appointment(
            AppointmentCreateSchema(
                patient_id=patient_id,
                scheduled_start_at=data.requested_date,
                staff_profile_id=data.requested_clinician_id,
                service_delivery_point_id=data.requested_sdp_id,
                reason=data.reason,
            ),
            actor_user_id=None,
        )

        # 3. Link the request to the created appointment and mark it scheduled.
        request.converted_appointment_id = appointment.id
        request.status = PortalAppointmentRequestStatus.SCHEDULED
        self.db.commit()
        self.db.refresh(request)
        return request

    def list_bookable_clinicians(self) -> list[dict]:
        """Doctors a patient can optionally request during booking."""
        return self.repository.list_bookable_clinicians()

    def send_message(self, patient_id: int, data: PortalMessageCreateSchema):
        # The portal is patient-keyed (OTP login), so the path identifier is the
        # patient id; the repository resolves the patient's portal account.
        message = self.repository.create_message(patient_id, data)
        # Raise an in-app notification for the designated care-team members so
        # the message shows up on their dashboard/notification bell.
        self._notify_staff_of_new_message(patient_id, message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def _notify_staff_of_new_message(self, patient_id: int, message) -> None:
        """
        Create an in-app notification for every staff member allowed to read
        patient messages (holders of ``PORTAL_MESSAGE_READ`` + superusers).

        Best-effort: a notification failure must never block the patient's
        message from being saved, so problems are logged and swallowed.
        """
        try:
            patient = self.patient_repository.get_by_id(patient_id)
            patient_name = None
            if patient is not None:
                patient_name = (
                    f"{getattr(patient, 'first_name', '') or ''} "
                    f"{getattr(patient, 'last_name', '') or ''}"
                ).strip() or None

            recipient_ids = self.permission_repository.get_user_ids_for_permission(
                PORTAL_MESSAGE_PERMISSION
            )
            if not recipient_ids:
                return

            who = patient_name or f"Patient #{patient_id}"
            subject = f"New message from {who}"
            snippet = (getattr(message, "subject", None) or getattr(message, "body", "") or "").strip()
            if len(snippet) > 140:
                snippet = snippet[:137] + "…"
            body = f"{who} sent a message via the patient portal.\n\n{snippet}".strip()

            for uid in recipient_ids:
                self.notification_repository.create(
                    channel=NotificationChannel.IN_APP,
                    body=body,
                    subject=subject,
                    user_id=uid,
                    status=NotificationStatus.SENT,
                    event_code=PORTAL_MESSAGE_EVENT,
                    payload_metadata={
                        "message_id": getattr(message, "id", None),
                        "patient_id": patient_id,
                    },
                )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to notify staff of new portal message: %s", exc)

    # ── Staff-facing patient message inbox ────────────────────────────

    def list_patient_messages(
        self, *, skip: int = 0, limit: int = 20, unread_only: bool = False
    ):
        return self.repository.list_patient_messages(
            skip=skip, limit=limit, unread_only=unread_only
        )

    def count_unread_patient_messages(self) -> int:
        return self.repository.count_unread_patient_messages()

    def get_patient_message(self, message_id: int):
        return self.repository.get_patient_message(message_id)

    def mark_patient_message_read(self, message_id: int):
        row = self.repository.get_patient_message(message_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Message not found.")
        message, patient = row
        message = self.repository.mark_patient_message_read(message)
        self.db.commit()
        self.db.refresh(message)
        return message, patient

    def share_document(self, account_id: int, data: PortalDocumentShareCreateSchema):
        share = self.repository.create_document_share(account_id, data)
        self.db.commit()
        return share
