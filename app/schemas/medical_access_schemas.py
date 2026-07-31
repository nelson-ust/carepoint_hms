# app/schemas/medical_access_schemas.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AccessRequestCreateSchema(BaseModel):
    holding_tenant_code: str = Field(..., min_length=1, max_length=100,
                                     description="Public code of the patient's primary hospital.")
    patient_global_id: str = Field(..., min_length=1, max_length=100)
    reason: str = Field(..., min_length=3, max_length=2000)
    scope: str = Field("MEDICAL_HISTORY", description="MEDICAL_HISTORY or BASELINE_DIAGNOSTICS.")
    link_expiry_hours: Optional[int] = Field(None, ge=1, le=168)
    requires_patient_approval: bool = True
    requires_hospital_approval: bool = True


class DecisionSchema(BaseModel):
    approve: bool
    reason: Optional[str] = Field(None, max_length=2000)


class PortalDecisionSchema(BaseModel):
    request_no: str
    approve: bool
    reason: Optional[str] = Field(None, max_length=2000)


class DeveloperAccessRequestSchema(BaseModel):
    reason: str = Field(..., min_length=3, max_length=2000)
    scope: str = Field("MEDICAL_HISTORY")
    link_expiry_hours: Optional[int] = Field(None, ge=1, le=168)
