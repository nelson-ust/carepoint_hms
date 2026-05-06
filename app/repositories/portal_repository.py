from __future__ import annotations
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.all_models import (
    PortalAccount, 
    PortalAppointmentRequest, 
    PortalMessage, 
    PortalDocumentShare
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

    def create_appointment_request(self, account_id: int, data: PortalAppointmentRequestCreateSchema) -> PortalAppointmentRequest:
        request = PortalAppointmentRequest(account_id=account_id, **data.model_dump())
        self.db.add(request)
        self.db.flush()
        self.db.refresh(request)
        return request

    # ── Messaging ─────────────────────────────────────────────────────

    def create_message(self, account_id: int, data: PortalMessageCreateSchema, sender_type: str = "PATIENT") -> PortalMessage:
        message = PortalMessage(account_id=account_id, sender_type=sender_type, **data.model_dump())
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
