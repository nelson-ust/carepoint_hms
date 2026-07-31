# app/schemas/patient_broadcast_schemas.py
from __future__ import annotations

"""
Schemas for hospital→patient outbound messaging ("broadcasts").

A broadcast is composed by hospital staff and addressed to a single patient,
an explicitly selected group of patients, or every registered patient. Each
targeted patient gets an inbox item they can read from the patient portal.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import PatientBroadcastAudience, PatientBroadcastStatus

# Channels a broadcast may use. IN_APP is the always-on portal inbox; the
# others trigger external delivery via the notification service.
_ALLOWED_CHANNELS = {"IN_APP", "EMAIL", "SMS"}


# ── Staff: compose ───────────────────────────────────────────────────

class PatientBroadcastCreateSchema(BaseModel):
    """Payload for sending a message to one, several, or all patients."""

    audience_type: PatientBroadcastAudience
    # Required for SINGLE (exactly one) and GROUP (one or more); ignored for ALL.
    patient_ids: List[int] = Field(default_factory=list)
    subject: Optional[str] = Field(default=None, max_length=255)
    body: str = Field(..., min_length=1)
    # IN_APP is always applied even if omitted. EMAIL / SMS are opt-in.
    channels: List[str] = Field(default_factory=lambda: ["IN_APP"])

    @field_validator("audience_type", mode="before")
    @classmethod
    def _norm_audience(cls, v):
        if isinstance(v, str):
            return v.strip().upper()
        return v

    @field_validator("channels", mode="before")
    @classmethod
    def _norm_channels(cls, v):
        if v is None:
            return ["IN_APP"]
        if isinstance(v, str):
            v = [v]
        cleaned = []
        for c in v:
            if not c:
                continue
            code = str(c).strip().upper()
            if code not in _ALLOWED_CHANNELS:
                raise ValueError(
                    f"Unsupported channel '{code}'. Allowed: {sorted(_ALLOWED_CHANNELS)}."
                )
            if code not in cleaned:
                cleaned.append(code)
        # IN_APP (the portal inbox) is always implied.
        if "IN_APP" not in cleaned:
            cleaned.insert(0, "IN_APP")
        return cleaned

    @field_validator("subject")
    @classmethod
    def _strip_subject(cls, v):
        if v is None:
            return v
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def _validate_audience_ids(self):
        # De-duplicate ids up front.
        ids = list(dict.fromkeys(self.patient_ids or []))
        if self.audience_type == PatientBroadcastAudience.SINGLE:
            if len(ids) != 1:
                raise ValueError("Select exactly one patient for a single-patient message.")
        elif self.audience_type == PatientBroadcastAudience.GROUP:
            if len(ids) < 1:
                raise ValueError("Select at least one patient for a group message.")
        else:  # ALL
            ids = []
        self.patient_ids = ids
        return self


class AudiencePreviewSchema(BaseModel):
    """Ask the backend how many patients an audience selection will reach."""

    audience_type: PatientBroadcastAudience
    patient_ids: List[int] = Field(default_factory=list)

    @field_validator("audience_type", mode="before")
    @classmethod
    def _norm_audience(cls, v):
        if isinstance(v, str):
            return v.strip().upper()
        return v


class AudiencePreviewResponse(BaseModel):
    audience_type: PatientBroadcastAudience
    recipient_count: int


# ── Staff: read / history ────────────────────────────────────────────

class PatientBroadcastReadSchema(BaseModel):
    id: int
    subject: Optional[str] = None
    body: str
    audience_type: PatientBroadcastAudience
    channels: Optional[List[str]] = None
    recipient_count: int = 0
    read_count: int = 0
    email_sent_count: int = 0
    sms_sent_count: int = 0
    status: PatientBroadcastStatus
    sent_by_user_id: Optional[int] = None
    sent_by_name: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_row(cls, broadcast, *, sent_by_name=None, read_count=0) -> "PatientBroadcastReadSchema":
        return cls(
            id=broadcast.id,
            subject=getattr(broadcast, "subject", None),
            body=getattr(broadcast, "body", "") or "",
            audience_type=broadcast.audience_type,
            channels=getattr(broadcast, "channels", None),
            recipient_count=getattr(broadcast, "recipient_count", 0) or 0,
            read_count=read_count,
            email_sent_count=getattr(broadcast, "email_sent_count", 0) or 0,
            sms_sent_count=getattr(broadcast, "sms_sent_count", 0) or 0,
            status=broadcast.status,
            sent_by_user_id=getattr(broadcast, "sent_by_user_id", None),
            sent_by_name=sent_by_name,
            sent_at=getattr(broadcast, "sent_at", None),
            created_at=getattr(broadcast, "date_created", None) or getattr(broadcast, "sent_at", None),
        )


class PatientBroadcastListResponse(BaseModel):
    success: bool = True
    message: str = "Messages fetched successfully."
    items: List[PatientBroadcastReadSchema]
    count: int
    meta: dict


class PatientBroadcastCreateResponse(BaseModel):
    success: bool = True
    message: str
    broadcast: PatientBroadcastReadSchema


# ── Patient portal: inbox ────────────────────────────────────────────

class PortalInboxMessageRead(BaseModel):
    """A hospital message as shown in the patient portal inbox."""

    # This is the recipient-row id (unique per patient), used for read ops.
    id: int
    broadcast_id: int
    subject: Optional[str] = None
    body: str
    is_read: bool = False
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_row(cls, recipient, broadcast) -> "PortalInboxMessageRead":
        return cls(
            id=recipient.id,
            broadcast_id=broadcast.id,
            subject=getattr(broadcast, "subject", None),
            body=getattr(broadcast, "body", "") or "",
            is_read=getattr(recipient, "read_at", None) is not None,
            sent_at=getattr(broadcast, "sent_at", None)
            or getattr(broadcast, "date_created", None),
            read_at=getattr(recipient, "read_at", None),
        )


class PortalInboxListResponse(BaseModel):
    success: bool = True
    message: str = "Messages fetched successfully."
    items: List[PortalInboxMessageRead]
    count: int
    meta: dict


class PortalInboxUnreadCountResponse(BaseModel):
    success: bool = True
    count: int = 0
