# app/schemas/whatsapp_schemas.py
"""Request/response schemas for WhatsApp configuration, sending, and inbox."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class WhatsAppConfigUpsertSchema(BaseModel):
    phone_number_id: str = Field(..., max_length=64)
    waba_id: Optional[str] = Field(None, max_length=64)
    display_phone_number: Optional[str] = Field(None, max_length=32)
    business_name: Optional[str] = Field(None, max_length=255)
    # Write-only secrets (never returned).
    access_token: Optional[str] = None
    verify_token: Optional[str] = None
    app_secret: Optional[str] = None
    notify_role_codes: Optional[list[str]] = None
    is_active: Optional[bool] = None


class WhatsAppConfigReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    phone_number_id: str
    waba_id: Optional[str] = None
    display_phone_number: Optional[str] = None
    business_name: Optional[str] = None
    notify_role_codes: list[str] = []
    is_active: bool = True
    has_access_token: bool = False
    has_app_secret: bool = False
    has_verify_token: bool = False
    created_at: Optional[datetime] = None


class SendTextMessageSchema(BaseModel):
    to: str = Field(..., description="Recipient phone in international format.")
    body: str = Field(..., min_length=1, max_length=4096)
    preview_url: bool = False


class SendTemplateMessageSchema(BaseModel):
    to: str
    template_name: str
    language_code: str = "en_US"
    components: Optional[list[dict[str, Any]]] = None


class WhatsAppMessageReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    conversation_id: Optional[int] = None
    wa_message_id: Optional[str] = None
    direction: str
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    message_type: str
    body: Optional[str] = None
    media_id: Optional[str] = None
    media_mime_type: Optional[str] = None
    status: Optional[str] = None
    error_title: Optional[str] = None
    patient_id: Optional[int] = None
    wa_timestamp: Optional[datetime] = None
    created_at: Optional[datetime] = None


class WhatsAppConversationReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    phone_number_id: Optional[str] = None
    wa_id: str
    contact_name: Optional[str] = None
    patient_id: Optional[int] = None
    status: str
    unread_count: int
    last_message_at: Optional[datetime] = None
    last_inbound_at: Optional[datetime] = None
    last_outbound_at: Optional[datetime] = None
