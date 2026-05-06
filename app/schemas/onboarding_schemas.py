from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.enums import OnboardingInvitationStatus, OnboardingDocumentType


# ── Document Schemas ──────────────────────────────────────────────────

class OnboardingDocumentBase(BaseModel):
    document_type: OnboardingDocumentType
    title: str = Field(..., max_length=255)
    description: Optional[str] = None


class OnboardingDocumentReadSchema(OnboardingDocumentBase):
    id: int
    s3_key: Optional[str] = None
    file_url: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# ── Invitation Schemas ────────────────────────────────────────────────

class OnboardingInvitationBase(BaseModel):
    candidate_email: EmailStr
    candidate_phone: Optional[str] = None
    notes: Optional[str] = None
    expiry_days: int = Field(default=7, ge=1, le=30)


class OnboardingInvitationCreateSchema(OnboardingInvitationBase):
    staff_profile_id: int
    # Optional HR presets for salary
    salary_grade_id: Optional[int] = None
    salary_step_id: Optional[int] = None


class OnboardingInvitationUpdateSchema(BaseModel):
    candidate_email: Optional[EmailStr] = None
    candidate_phone: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[OnboardingInvitationStatus] = None


class OnboardingInvitationReadSchema(OnboardingInvitationBase):
    id: int
    staff_profile_id: int
    status: OnboardingInvitationStatus
    sent_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    resend_count: int
    created_by_user_id: Optional[int] = None
    
    documents: List[OnboardingDocumentReadSchema] = []

    model_config = ConfigDict(from_attributes=True)


# ── Sub-component Schemas for Completion ──────────────────────────────

class StaffLicenseOnboardingSchema(BaseModel):
    license_type: str
    license_number: str
    issuing_body: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    notes: Optional[str] = None


class StaffEmergencyContactOnboardingSchema(BaseModel):
    full_name: str
    relationship: str
    phone_number: str
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    is_primary: bool = False


# ── Completion Schema ─────────────────────────────────────────────────

class OnboardingCompletionSchema(BaseModel):
    # Candidate updates their demographics
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    middle_name: Optional[str] = None
    date_of_birth: date
    gender: str
    marital_status: str
    nationality: str
    address_line_1: str
    city: str
    state_region: str
    country: str
    
    # Emergency contact (Standard simplified fields in StaffProfile)
    emergency_contact_name: str
    emergency_contact_phone: str
    
    # Detailed Emergency Contacts (Stored in StaffEmergencyContact table)
    emergency_contacts: List[StaffEmergencyContactOnboardingSchema] = Field(default_factory=list)
    
    # Professional Licenses
    licenses: List[StaffLicenseOnboardingSchema] = Field(default_factory=list)
    
    # Salary Preferences / Info (HR usually sets this, but candidate might confirm)
    # For now, we'll assume the candidate just provides bank info which is in completion.
    bank_name: Optional[str] = None
    bank_account_no: Optional[str] = None
    bank_account_name: Optional[str] = None


# ── Progress Schema ───────────────────────────────────────────────────

class OnboardingProgressSchema(BaseModel):
    status: OnboardingInvitationStatus
    completion_percentage: float
    is_demographics_complete: bool
    uploaded_document_types: List[OnboardingDocumentType]
    missing_document_types: Optional[List[OnboardingDocumentType]] = None
    checklist: Optional[List[dict]] = None
    expires_at: Optional[datetime] = None
    days_remaining: Optional[int] = None
