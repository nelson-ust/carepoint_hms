from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

# ── Patient Identifier Schemas ────────────────────────────────────────

class PatientIdentifierBase(BaseModel):
    identifier_type: str = Field(..., description="Type of ID: NATIONAL_ID, PASSPORT, etc.")
    identifier_value: str = Field(..., description="The ID number")
    issuing_authority: Optional[str] = None
    is_primary: bool = False
    is_active: bool = True
    note: Optional[str] = None

class PatientIdentifierCreateSchema(PatientIdentifierBase):
    pass

class PatientIdentifierReadSchema(PatientIdentifierBase):
    id: int
    patient_id: int
    model_config = ConfigDict(from_attributes=True)

# ── Patient Attachment Schemas ────────────────────────────────────────

class PatientAttachmentBase(BaseModel):
    attachment_type: str = Field(..., description="Type: PHOTO, ID_DOCUMENT, REFERRAL, etc.")
    title: Optional[str] = None
    file_name: str
    file_key: Optional[str] = None
    file_url: Optional[str] = None
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    is_primary: bool = False
    note: Optional[str] = None

class PatientAttachmentCreateSchema(PatientAttachmentBase):
    pass

class PatientAttachmentReadSchema(PatientAttachmentBase):
    id: int
    patient_id: int
    uploaded_by_id: Optional[int] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ── Patient Consent Schemas ───────────────────────────────────────────

class PatientConsentBase(BaseModel):
    consent_type: str
    consent_status: str = Field(..., description="GRANTED, DECLINED, WITHDRAWN, EXPIRED")
    consent_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    note: Optional[str] = None

class PatientConsentCreateSchema(PatientConsentBase):
    document_file_name: Optional[str] = None
    document_file_key: Optional[str] = None
    document_file_url: Optional[str] = None

class PatientConsentReadSchema(PatientConsentBase):
    id: int
    patient_id: int
    recorded_by_id: Optional[int] = None
    document_file_name: Optional[str] = None
    document_file_url: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ── Insurance Master Data Schemas ─────────────────────────────────────

class InsuranceProviderBase(BaseModel):
    name: str
    code: str
    provider_type: str = Field(..., description="HMO, PRIVATE, GOVERNMENT, etc.")
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = True

class InsuranceProviderCreateSchema(InsuranceProviderBase):
    pass

class InsuranceProviderReadSchema(InsuranceProviderBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class PatientInsuranceBase(BaseModel):
    insurance_provider_id: int
    policy_number: str
    member_name: Optional[str] = None
    relationship_to_member: str = "SELF"
    plan_name: Optional[str] = None
    start_date: Optional[date] = None
    expiry_date: Optional[date] = None
    is_active: bool = True

class PatientInsuranceCreateSchema(PatientInsuranceBase):
    pass

class PatientInsuranceReadSchema(PatientInsuranceBase):
    id: int
    patient_id: int
    provider_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
