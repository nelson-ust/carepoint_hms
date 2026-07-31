# app/schemas/interoperability_schemas.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- Partner directory ----------

class PartnerTenantSchema(BaseModel):
    id: int
    name: str
    code: str


# ---------- Cross-tenant patient lookup ----------

class PatientLookupResultSchema(BaseModel):
    found: bool
    holding_tenant_id: int
    patient_global_id: str
    display_name: Optional[str] = None
    sex: Optional[str] = None
    date_of_birth: Optional[str] = None


# ---------- Data-exchange requests ----------

class DataRequestCreateSchema(BaseModel):
    holding_tenant_id: int = Field(..., description="Hospital that holds the patient's records.")
    patient_global_id: str = Field(..., min_length=1, description="Global patient ID to request.")
    patient_display_name: Optional[str] = None
    purpose: str = Field(..., min_length=3, description="Why the records are needed (clinical purpose).")
    scope: str = "FULL_RECORD"


class DataRequestApproveSchema(BaseModel):
    consent_confirmed: bool = Field(..., description="Confirm the patient has consented to this share.")
    consent_reference: str = Field(..., min_length=1, description="Reference to the recorded patient consent.")
    access_expiry_days: int = Field(30, ge=1, le=365)


class DataRequestDenySchema(BaseModel):
    reason: str = Field(..., min_length=1)


class DataRequestReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_no: str
    requesting_tenant_id: int
    holding_tenant_id: int
    patient_global_id: str
    patient_display_name: Optional[str] = None
    purpose: str
    scope: str
    status: str
    requested_by_user_id: Optional[int] = None
    requested_at: Optional[datetime] = None
    consent_confirmed: bool = False
    consent_reference: Optional[str] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    denied_reason: Optional[str] = None
    payload_generated_at: Optional[datetime] = None
    retrieved_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    # convenience display fields (populated by the service)
    requesting_tenant_name: Optional[str] = None
    holding_tenant_name: Optional[str] = None


class DataRequestPayloadSchema(BaseModel):
    id: int
    request_no: str
    status: str
    patient_global_id: str
    payload: Optional[dict] = None
