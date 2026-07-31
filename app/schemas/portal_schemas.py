from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import AliasChoices, BaseModel, Field, ConfigDict, EmailStr, field_validator, model_validator
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
    # Optional doctor (clinician staff profile id) the patient asks to see.
    requested_clinician_id: Optional[int] = None
    reason: str
    priority: str = "NORMAL"


class PortalClinicianOptionSchema(BaseModel):
    """A doctor the patient can optionally request to see."""
    id: int
    name: str
    specialty: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class PortalAppointmentRequestReadSchema(BaseModel):
    id: int
    # Optional account link (portal is patient-keyed).
    account_id: Optional[int] = None
    patient_id: Optional[int] = None
    # The model column is ``requested_for``; expose it as ``requested_date``.
    requested_date: datetime = Field(validation_alias=AliasChoices("requested_date", "requested_for"))
    reason: Optional[str] = None
    priority: Optional[str] = "NORMAL"
    preferred_clinician_id: Optional[int] = None
    status: str
    # Base column is ``date_created``.
    created_at: datetime = Field(validation_alias=AliasChoices("created_at", "date_created"))
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator("status", mode="before")
    @classmethod
    def _status_str(cls, v):
        return getattr(v, "value", v)

# ── Portal Message Schemas ──────────────────────────────────────────

class PortalMessageCreateSchema(BaseModel):
    subject: str
    body: str
    parent_message_id: Optional[int] = None

class PortalMessageReadSchema(BaseModel):
    id: int
    subject: Optional[str] = None
    body: str
    sender_type: str
    is_read: bool = False
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _from_orm(cls, data):
        """
        Map the ``PortalMessage`` ORM row onto the portal's message shape.

        The model stores ``direction`` (not ``sender_type``), tracks read state
        via ``status``/``read_at`` (not an ``is_read`` flag), and its created
        timestamp is the base ``date_created`` column — so translate those here.
        Dicts (e.g. test payloads) pass straight through.
        """
        if isinstance(data, dict):
            return data

        direction = getattr(data, "direction", None)
        status = getattr(data, "status", None)
        status_val = getattr(status, "value", status)
        read_at = getattr(data, "read_at", None)
        created = (
            getattr(data, "date_created", None)
            or getattr(data, "sent_at", None)
            or getattr(data, "created_at", None)
        )
        return {
            "id": getattr(data, "id", None),
            "subject": getattr(data, "subject", None),
            "body": getattr(data, "body", ""),
            "sender_type": getattr(direction, "value", direction),
            "is_read": read_at is not None
            or status_val in {"READ", "REPLIED", "ARCHIVED"},
            "created_at": created,
        }

# ── Staff-facing patient message inbox ──────────────────────────────

class StaffPatientMessageRead(BaseModel):
    """A patient→provider message as shown in the staff dashboard inbox."""

    id: int
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    hospital_number: Optional[str] = None
    subject: Optional[str] = None
    body: str
    is_read: bool = False
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_row(cls, message, patient) -> "StaffPatientMessageRead":
        status_val = getattr(getattr(message, "status", None), "value", getattr(message, "status", None))
        full_name = None
        if patient is not None:
            full_name = f"{getattr(patient, 'first_name', '') or ''} {getattr(patient, 'last_name', '') or ''}".strip() or None
        return cls(
            id=message.id,
            patient_id=getattr(patient, "id", None),
            patient_name=full_name,
            hospital_number=getattr(patient, "hospital_number", None),
            subject=getattr(message, "subject", None),
            body=getattr(message, "body", "") or "",
            is_read=getattr(message, "read_at", None) is not None
            or status_val in {"READ", "REPLIED", "ARCHIVED"},
            sent_at=getattr(message, "sent_at", None),
            created_at=getattr(message, "date_created", None) or getattr(message, "sent_at", None),
        )


class StaffPatientMessageListResponse(BaseModel):
    success: bool = True
    message: str = "Patient messages fetched successfully."
    items: List[StaffPatientMessageRead]
    count: int
    meta: dict


class StaffPatientMessageUnreadCountResponse(BaseModel):
    success: bool = True
    count: int = 0


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
