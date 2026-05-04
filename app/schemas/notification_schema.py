# app/schemas/notification_schema.py
from __future__ import annotations

"""
Pydantic schemas for the notifications module (Stage 17).

Covers:
- ``NotificationTemplate`` — reusable email/SMS/WhatsApp/in-app templates
  with simple ``{name}`` placeholder substitution
- ``Notification`` — individual notification rows with retry / status tracking
- ``Message``       — direct user-to-user messages (light internal messaging)

Lifecycle reflected by these schemas:
    PENDING -> SENT -> DELIVERED -> READ
                   \\-> FAILED
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ============================================================
# TEMPLATE SCHEMAS
# ============================================================


class NotificationTemplateCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    code: str = Field(..., min_length=1, max_length=100)
    channel: str = Field(..., description="IN_APP, EMAIL, SMS, WHATSAPP")
    subject_template: Optional[str] = Field(None, max_length=255)
    body_template: str = Field(..., min_length=1)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        # Codes are uppercase + underscore-separated for stable lookups.
        return v.strip().upper().replace(" ", "_")

    @field_validator("channel")
    @classmethod
    def normalize_channel(cls, v: str) -> str:
        normalized = v.strip().upper()
        if normalized not in {"IN_APP", "EMAIL", "SMS", "WHATSAPP"}:
            raise ValueError("channel must be one of IN_APP, EMAIL, SMS, WHATSAPP.")
        return normalized


class NotificationTemplateUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    subject_template: Optional[str] = Field(None, max_length=255)
    body_template: Optional[str] = Field(None, min_length=1)


class NotificationTemplateReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    channel: str
    subject_template: Optional[str] = None
    body_template: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NotificationTemplateListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Notification templates fetched successfully."
    items: list[NotificationTemplateReadSchema]
    count: int
    meta: dict


class NotificationTemplateActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    template: NotificationTemplateReadSchema


# ============================================================
# NOTIFICATION SCHEMAS
# ============================================================


class NotificationDispatchSchema(BaseModel):
    """
    Dispatch a notification using a template + context.

    ``template_code`` is preferred over ``template_id`` when stable
    integration keys are needed.
    """

    template_code: Optional[str] = None
    template_id: Optional[int] = None
    user_id: Optional[int] = None
    patient_id: Optional[int] = None
    recipient_address: Optional[str] = Field(
        None,
        max_length=255,
        description=(
            "Email address / phone number / WhatsApp ID. If omitted, falls "
            "back to user.email / user.phone_number / patient.email."
        ),
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Variables substituted into the subject / body template.",
    )
    scheduled_at: Optional[datetime] = Field(
        None,
        description="If set, the notification is queued for future dispatch.",
    )
    channel_override: Optional[str] = Field(
        None,
        description="Optional: send through a different channel than the template's default.",
    )

    @model_validator(mode="after")
    def template_required(self):
        # Either template_code or template_id must resolve a template; we don't
        # support free-form template body in the dispatch payload.
        if self.template_code is None and self.template_id is None:
            raise ValueError("Either template_code or template_id must be supplied.")
        return self


class NotificationAdHocDispatchSchema(BaseModel):
    """
    Send an ad-hoc notification without using a template.

    Useful for one-off operational alerts. The audit trail still records the
    delivery, but no template row is materialised.
    """

    channel: str = Field(..., description="IN_APP, EMAIL, SMS, WHATSAPP")
    subject: Optional[str] = Field(None, max_length=255)
    body: str = Field(..., min_length=1)
    user_id: Optional[int] = None
    patient_id: Optional[int] = None
    recipient_address: Optional[str] = Field(None, max_length=255)
    scheduled_at: Optional[datetime] = None

    @field_validator("channel")
    @classmethod
    def normalize_channel(cls, v: str) -> str:
        normalized = v.strip().upper()
        if normalized not in {"IN_APP", "EMAIL", "SMS", "WHATSAPP"}:
            raise ValueError("channel must be one of IN_APP, EMAIL, SMS, WHATSAPP.")
        return normalized


class NotificationReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    patient_id: Optional[int] = None
    template_id: Optional[int] = None
    channel: str
    status: str
    recipient_address: Optional[str] = None
    subject: Optional[str] = None
    body: str
    payload_metadata: Optional[dict[str, Any]] = None
    scheduled_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NotificationListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Notifications fetched successfully."
    items: list[NotificationReadSchema]
    count: int
    meta: dict


class NotificationActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    notification: NotificationReadSchema


class NotificationRetryResponseSchema(BaseModel):
    """Response for the bulk retry operation."""

    success: bool = True
    message: str = "Retry attempted."
    retried: int = 0
    failed: int = 0
    sent: int = 0


# ============================================================
# DIRECT MESSAGE SCHEMAS
# ============================================================


class MessageCreateSchema(BaseModel):
    """Internal direct-message between system users."""

    recipient_user_id: int
    subject: Optional[str] = Field(None, max_length=255)
    body: str = Field(..., min_length=1)


class MessageReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_user_id: Optional[int] = None
    recipient_user_id: Optional[int] = None
    subject: Optional[str] = None
    body: str
    status: str
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class MessageListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Messages fetched successfully."
    items: list[MessageReadSchema]
    count: int
    meta: dict


class MessageActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    direct_message: MessageReadSchema
