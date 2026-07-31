# app/services/patient_broadcast_service.py
from __future__ import annotations

"""
Service for hospital→patient outbound messaging ("broadcasts").

A staff member composes a message and addresses it to a single patient, an
explicitly selected group of patients, or every registered patient. For each
targeted patient we persist a lightweight inbox record (read from the patient
portal) and — when the sender opts into EMAIL / SMS — dispatch an external
copy via the notification service.
"""

import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import (
    NotificationChannel,
    NotificationStatus,
    PatientBroadcastAudience,
    PatientBroadcastStatus,
)
from app.models.all_models import Patient
from app.repositories.patient_broadcast_repository import PatientBroadcastRepository
from app.schemas.notification_schema import NotificationAdHocDispatchSchema
from app.schemas.patient_broadcast_schemas import PatientBroadcastCreateSchema
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class PatientBroadcastService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PatientBroadcastRepository(db)
        self.notification_service = NotificationService(db)

    # ── Compose / send ───────────────────────────────────────────────

    def create_broadcast(
        self, payload: PatientBroadcastCreateSchema, *, actor_user_id: Optional[int] = None
    ):
        patients = self.repository.resolve_recipient_patients(
            payload.audience_type, payload.patient_ids
        )
        if not patients:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No matching registered patients were found for this audience."
                ),
            )

        channels = payload.channels or ["IN_APP"]
        wants_email = "EMAIL" in channels
        wants_sms = "SMS" in channels

        broadcast = self.repository.create_broadcast(
            subject=payload.subject,
            body=payload.body,
            audience_type=payload.audience_type,
            channels=channels,
            sent_by_user_id=actor_user_id,
            recipient_count=len(patients),
            status=PatientBroadcastStatus.SENT,
        )
        self.repository.add_recipients(broadcast.id, [p.id for p in patients])

        email_sent = 0
        sms_sent = 0
        email_eligible = 0
        sms_eligible = 0

        if wants_email or wants_sms:
            body_html = self._render_email_html(payload.subject, payload.body) if wants_email else None
            for p in patients:
                if wants_email and getattr(p, "email", None):
                    email_eligible += 1
                    if self._dispatch(
                        p, NotificationChannel.EMAIL, payload.subject, payload.body,
                        body_html=body_html, actor_user_id=actor_user_id,
                    ):
                        email_sent += 1
                if wants_sms and getattr(p, "phone_number", None):
                    sms_eligible += 1
                    if self._dispatch(
                        p, NotificationChannel.SMS, payload.subject, payload.body,
                        body_html=None, actor_user_id=actor_user_id,
                    ):
                        sms_sent += 1

        broadcast.email_sent_count = email_sent
        broadcast.sms_sent_count = sms_sent

        # PARTIAL when an external channel was requested but some eligible
        # deliveries failed; otherwise SENT (the in-app inbox always succeeds).
        failed_external = (email_eligible - email_sent) + (sms_eligible - sms_sent)
        if (wants_email or wants_sms) and failed_external > 0:
            broadcast.status = PatientBroadcastStatus.PARTIAL

        self.db.add(broadcast)
        self.db.commit()
        self.db.refresh(broadcast)

        sender_name = None
        if actor_user_id:
            sender_name = self.repository.get_sender_names([actor_user_id]).get(actor_user_id)
        return broadcast, sender_name

    def _dispatch(
        self,
        patient: Patient,
        channel: NotificationChannel,
        subject: Optional[str],
        body: str,
        *,
        body_html: Optional[str],
        actor_user_id: Optional[int],
    ) -> bool:
        """Best-effort external delivery to one patient. Returns True on SENT."""
        try:
            notification = self.notification_service.dispatch_ad_hoc(
                NotificationAdHocDispatchSchema(
                    channel=channel.value,
                    subject=subject or "Message from your hospital",
                    body=body,
                    body_html=body_html,
                    patient_id=patient.id,
                ),
                actor_user_id=actor_user_id,
                raise_on_failure=False,
            )
            return getattr(notification, "status", None) == NotificationStatus.SENT
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "Broadcast %s delivery to patient %s failed: %s",
                channel, patient.id, exc,
            )
            return False

    def _render_email_html(self, subject: Optional[str], body: str) -> Optional[str]:
        """Render a branded HTML email body, falling back to plain text."""
        try:
            from app.core.multitenancy import get_current_tenant
            from app.utils.email_utils import render_branded_email

            tenant = get_current_tenant()
            hospital = tenant.name if tenant else None
            paragraphs = [line for line in (body or "").split("\n\n") if line.strip()] or [body]
            return render_branded_email(
                title=subject or (f"A message from {hospital}" if hospital else "A message from your hospital"),
                body_paragraphs=paragraphs,
                brand_name=hospital,
                footer_note="You are receiving this message because you are registered as a patient with us.",
                preheader=(subject or (body or "")[:120]),
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to render branded broadcast email: %s", exc)
            return None

    # ── Staff history ────────────────────────────────────────────────

    def list_broadcasts(self, *, skip: int = 0, limit: int = 20):
        rows, total = self.repository.list_broadcasts(skip=skip, limit=limit)
        sender_names = self.repository.get_sender_names(
            [b.sent_by_user_id for b in rows if b.sent_by_user_id]
        )
        read_counts = self.repository.read_counts_for([b.id for b in rows])
        return rows, total, sender_names, read_counts

    def audience_preview(self, audience_type: PatientBroadcastAudience, patient_ids) -> int:
        return self.repository.count_recipient_patients(audience_type, patient_ids or [])

    # ── Patient inbox ────────────────────────────────────────────────

    def _patient_for_user(self, user_id: int) -> Patient:
        patient = (
            self.db.query(Patient).filter(Patient.user_id == user_id).first()
        )
        if patient is None:
            raise HTTPException(status_code=404, detail="Patient record not found.")
        return patient

    def list_inbox(self, user_id: int, *, skip: int = 0, limit: int = 20, unread_only: bool = False):
        patient = self._patient_for_user(user_id)
        return self.repository.list_inbox(
            patient.id, skip=skip, limit=limit, unread_only=unread_only
        )

    def count_unread(self, user_id: int) -> int:
        patient = self._patient_for_user(user_id)
        return self.repository.count_unread(patient.id)

    def mark_read(self, user_id: int, recipient_id: int):
        patient = self._patient_for_user(user_id)
        row = self.repository.get_recipient(recipient_id, patient.id)
        if row is None:
            raise HTTPException(status_code=404, detail="Message not found.")
        recipient, broadcast = row
        recipient = self.repository.mark_read(recipient)
        self.db.commit()
        self.db.refresh(recipient)
        return recipient, broadcast

    def mark_all_read(self, user_id: int) -> int:
        patient = self._patient_for_user(user_id)
        updated = self.repository.mark_all_read(patient.id)
        self.db.commit()
        return updated
