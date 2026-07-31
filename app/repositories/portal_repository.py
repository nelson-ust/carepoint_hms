from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, select
import hashlib
import secrets

from app.core.enums import (
    PortalAccountStatus,
    PortalMessageDirection,
    PortalMessageStatus,
)
from app.models.all_models import (
    Patient,
    PortalAccount,
    PortalAppointmentRequest,
    PortalMessage,
    PortalDocumentShare,
    StaffProfile,
    User,
)
from app.schemas.portal_schemas import (
    PortalAccountCreateSchema,
    PortalAppointmentRequestCreateSchema,
    PortalMessageCreateSchema,
    PortalDocumentShareCreateSchema
)

class PortalRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Account ───────────────────────────────────────────────────────

    def create_account(self, data: PortalAccountCreateSchema, password_hash: str) -> PortalAccount:
        # Create account excluding raw password
        account_data = data.model_dump(exclude={"password"})
        account = PortalAccount(**account_data, password_hash=password_hash)
        self.db.add(account)
        self.db.flush()
        self.db.refresh(account)
        return account

    def get_account_by_username(self, username: str) -> Optional[PortalAccount]:
        return self.db.scalars(
            select(PortalAccount).where(PortalAccount.portal_username == username)
        ).first()

    # ── Appointment Requests ──────────────────────────────────────────

    def create_appointment_request(
        self, patient_id: int, data: PortalAppointmentRequestCreateSchema
    ) -> PortalAppointmentRequest:
        """
        Persist a patient-initiated appointment request.

        The portal signs patients in by OTP, so the caller identifier is the
        patient id. We map the schema's fields onto the ORM columns
        (``requested_date`` → ``requested_for``, ``requested_sdp_id`` →
        ``service_delivery_point_id``, ``requested_clinician_id`` →
        ``preferred_clinician_id``) and best-effort link a portal account when
        one exists for the patient.
        """
        account = self._get_or_create_account(patient_id)

        request = PortalAppointmentRequest(
            patient_id=patient_id,
            account_id=account.id,
            requested_for=data.requested_date,
            service_delivery_point_id=data.requested_sdp_id,
            preferred_clinician_id=data.requested_clinician_id,
            reason=(data.reason or None),
            priority=(data.priority or "NORMAL").strip().upper(),
        )
        self.db.add(request)
        self.db.flush()
        self.db.refresh(request)
        return request

    def _get_or_create_account(self, patient_id: int) -> PortalAccount:
        """
        Return the portal account for a patient, provisioning a lightweight
        shell if none exists.

        The portal authenticates patients by OTP (not password), so this shell
        account exists only to satisfy the appointment/message foreign keys and
        to group a patient's portal activity. Its synthetic password is never
        used to sign in.
        """
        account = self.db.scalars(
            select(PortalAccount).where(PortalAccount.patient_id == patient_id)
        ).first()
        if account is not None:
            return account

        # Leave email/phone unset — those columns are unique, and copying the
        # patient's contact details risks a collision with their real portal
        # account or another patient. This shell is keyed by patient_id only.
        account = PortalAccount(
            patient_id=patient_id,
            portal_username=f"patient-{patient_id}-{secrets.token_hex(3)}",
            password_hash=hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
            status=PortalAccountStatus.ACTIVE,
            is_email_verified=False,
            is_phone_verified=False,
        )
        self.db.add(account)
        self.db.flush()
        return account

    def list_bookable_clinicians(self) -> list[dict]:
        """
        Doctors a patient can optionally request. Returns lightweight
        ``{id, name, specialty}`` rows keyed by the clinician's staff-profile id.
        """
        rows = (
            self.db.query(StaffProfile, User)
            .join(User, User.id == StaffProfile.user_id)
            .filter(
                StaffProfile.is_deleted.is_(False),
                User.is_deleted.is_(False),
            )
            .order_by(User.first_name.asc(), User.last_name.asc())
            .all()
        )
        options: list[dict] = []
        for staff, user in rows:
            full = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username
            title = (staff.job_title or "").strip()
            name = f"Dr. {full}" if not title.lower().startswith("dr") else full
            options.append({"id": staff.id, "name": name, "specialty": staff.specialty})
        return options

    # ── Messaging ─────────────────────────────────────────────────────

    def create_message(
        self,
        patient_id: int,
        data: PortalMessageCreateSchema,
        *,
        direction: PortalMessageDirection = PortalMessageDirection.PATIENT_TO_PROVIDER,
    ) -> PortalMessage:
        """
        Persist a secure message from the patient to the care team.

        The portal signs patients in by OTP, so the caller identifier is the
        patient id; we resolve (or provision) the patient's portal account to
        satisfy the ``portal_message.account_id`` foreign key. Required columns
        that the create payload doesn't carry — ``direction``, ``status`` and
        ``sent_at`` — are set here rather than expected from the client.
        """
        account = self._get_or_create_account(patient_id)
        message = PortalMessage(
            account_id=account.id,
            direction=direction,
            status=PortalMessageStatus.SENT,
            subject=data.subject,
            body=data.body,
            parent_message_id=data.parent_message_id,
            sent_at=datetime.now(timezone.utc),
        )
        self.db.add(message)
        self.db.flush()
        self.db.refresh(message)
        return message

    # ── Staff-facing patient message inbox ────────────────────────────

    def list_patient_messages(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        unread_only: bool = False,
    ) -> tuple[list[tuple[PortalMessage, Patient]], int]:
        """
        List messages sent by patients to the care team, newest first, paired
        with the sending patient so staff can see who wrote in.

        ``unread_only`` restricts to messages the care team hasn't opened yet
        (``read_at`` is NULL).
        """
        base = (
            self.db.query(PortalMessage, Patient)
            .join(PortalAccount, PortalAccount.id == PortalMessage.account_id)
            .join(Patient, Patient.id == PortalAccount.patient_id)
            .filter(
                PortalMessage.is_deleted.is_(False),
                PortalMessage.direction == PortalMessageDirection.PATIENT_TO_PROVIDER,
            )
        )
        if unread_only:
            base = base.filter(PortalMessage.read_at.is_(None))

        total = base.count()
        rows = (
            base.order_by(PortalMessage.sent_at.desc(), PortalMessage.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [(row[0], row[1]) for row in rows], int(total)

    def count_unread_patient_messages(self) -> int:
        """Count patient→provider messages the care team hasn't opened yet."""
        return int(
            self.db.query(func.count(PortalMessage.id))
            .filter(
                PortalMessage.is_deleted.is_(False),
                PortalMessage.direction == PortalMessageDirection.PATIENT_TO_PROVIDER,
                PortalMessage.read_at.is_(None),
            )
            .scalar()
            or 0
        )

    def get_patient_message(self, message_id: int) -> Optional[tuple[PortalMessage, Patient]]:
        row = (
            self.db.query(PortalMessage, Patient)
            .join(PortalAccount, PortalAccount.id == PortalMessage.account_id)
            .join(Patient, Patient.id == PortalAccount.patient_id)
            .filter(
                PortalMessage.id == message_id,
                PortalMessage.is_deleted.is_(False),
                PortalMessage.direction == PortalMessageDirection.PATIENT_TO_PROVIDER,
            )
            .first()
        )
        if row is None:
            return None
        return row[0], row[1]

    def mark_patient_message_read(self, message: PortalMessage) -> PortalMessage:
        """Flip a patient message to READ and stamp ``read_at`` (idempotent)."""
        if message.read_at is None:
            message.read_at = datetime.now(timezone.utc)
        message.status = PortalMessageStatus.READ
        self.db.add(message)
        self.db.flush()
        self.db.refresh(message)
        return message

    # ── Document Sharing ──────────────────────────────────────────────

    def create_document_share(self, account_id: int, data: PortalDocumentShareCreateSchema) -> PortalDocumentShare:
        share = PortalDocumentShare(account_id=account_id, **data.model_dump())
        self.db.add(share)
        self.db.flush()
        self.db.refresh(share)
        return share
