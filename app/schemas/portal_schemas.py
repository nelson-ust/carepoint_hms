from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from app.core.enums import PortalAccountStatus, TwoFactorType, TwoFactorPurpose

# ── Portal Account Schemas ───────────────────────────────────────────

class PortalAccountBase(BaseModel):
    portal_username: str
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    status: PortalAccountStatus = PortalAccountStatus.PENDING_VERIFICATION

class PortalAccountCreateSchema(PortalAccountBase):
    patient_id: int
    password: str

class PortalAccountReadSchema(PortalAccountBase):
    id: int
    patient_id: int
    is_email_verified: bool
    is_phone_verified: bool
    last_login_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

# ── Portal Appointment Request Schemas ──────────────────────────────

class PortalAppointmentRequestCreateSchema(BaseModel):
    requested_date: datetime
    requested_sdp_id: Optional[int] = None
    requested_clinician_id: Optional[int] = None
    reason: str
    priority: str = "NORMAL"

class PortalAppointmentRequestReadSchema(BaseModel):
    id: int
    account_id: int
    requested_date: datetime
    reason: str
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ── Portal Message Schemas ──────────────────────────────────────────

class PortalMessageCreateSchema(BaseModel):
    subject: str
    body: str
    parent_message_id: Optional[int] = None

class PortalMessageReadSchema(BaseModel):
    id: int
    subject: str
    body: str
    sender_type: str
    is_read: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ── Portal Document Share Schemas ───────────────────────────────────

class PortalDocumentShareCreateSchema(BaseModel):
    document_title: str
    attachment_id: Optional[int] = None
    share_expiry: Optional[datetime] = None
    note: Optional[str] = None

class PortalDocumentShareReadSchema(BaseModel):
    id: int
    document_title: str
    file_url: Optional[str] = None
    share_expiry: Optional[datetime] = None
    is_revoked: bool
    model_config = ConfigDict(from_attributes=True)
