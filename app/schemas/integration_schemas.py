# app/schemas/integration_schemas.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- Partner management ----------

class PartnerCreateSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    scopes: list[str] = Field(default_factory=lambda: ["READ"], description="READ and/or WRITE.")
    expiry_days: Optional[int] = Field(None, ge=1, le=3650, description="Key validity window; null = no expiry.")
    # Outbound (we call the partner)
    base_url: Optional[str] = Field(None, max_length=500)
    auth_header: str = "X-API-Key"
    auth_secret: Optional[str] = Field(None, description="Secret we send to the partner (stored encrypted).")


class PartnerUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    scopes: Optional[list[str]] = None
    expiry_days: Optional[int] = Field(None, ge=1, le=3650)
    base_url: Optional[str] = Field(None, max_length=500)
    auth_header: Optional[str] = None
    auth_secret: Optional[str] = None


class PartnerReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    key_prefix: str
    scopes: str
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    base_url: Optional[str] = None
    auth_header: str = "X-API-Key"
    has_outbound_secret: bool = False
    created_at: Optional[datetime] = None


class PartnerCreatedSchema(BaseModel):
    partner: PartnerReadSchema
    api_key: str = Field(..., description="Full API key — shown once. Store it securely.")


# ---------- Outbound (CarePoint -> partner) ----------

class OutboundRequestSchema(BaseModel):
    path: str = Field(..., description="Path appended to the partner base_url, e.g. /patients.")
    method: str = "GET"
    params: Optional[dict[str, Any]] = None
    payload: Optional[dict[str, Any]] = None


# ---------- Inbound (partner -> CarePoint) ----------

class PatientUpsertSchema(BaseModel):
    global_patient_id: Optional[str] = None
    hospital_number: Optional[str] = None
    first_name: str
    last_name: str
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    extra: Optional[dict[str, Any]] = Field(None, description="Additional model fields to set if present.")


class DataPushSchema(BaseModel):
    resource_type: str = Field(..., min_length=1, max_length=80)
    external_id: Optional[str] = None
    patient_global_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
