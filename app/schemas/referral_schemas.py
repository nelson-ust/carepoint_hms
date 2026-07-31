# app/schemas/referral_schemas.py
from __future__ import annotations

"""
Pydantic schemas for the patient referral module.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from app.core.enums import ReferralStatus, ReferralPriority


# ============================================================
# REQUESTS
# ============================================================


class ReferralCreateSchema(BaseModel):
    """Create a new patient referral."""

    patient_id: int
    visit_id: Optional[int] = None
    destination_facility: Optional[str] = Field(None, max_length=255, description="Free-text destination; auto-filled from destination_facility_id for internal referrals.")
    destination_facility_id: Optional[int] = Field(None, description="Receiving facility within this tenant (seamless internal referral).")
    reason_for_referral: str
    clinical_summary: Optional[str] = None
    referral_date: datetime = Field(default_factory=datetime.utcnow)
    priority: ReferralPriority = ReferralPriority.NORMAL


class ReferralUpdateSchema(BaseModel):
    """Update an existing referral."""

    destination_facility: Optional[str] = Field(None, max_length=255)
    reason_for_referral: Optional[str] = None
    clinical_summary: Optional[str] = None
    status: Optional[ReferralStatus] = None
    priority: Optional[ReferralPriority] = None


class InterFacilityReferralCreateSchema(BaseModel):
    """Create a referral to another facility in the SaaS platform."""

    target_tenant_id: int
    #: 0 = "unspecified facility" — routing is per-hospital (tenant); the
    #: precise receiving facility is optional detail.
    target_facility_id: int = 0
    patient_global_id: str = Field(..., max_length=100)
    reason_for_referral: str
    clinical_summary: Optional[str] = None
    referral_date: Optional[datetime] = None


class InterFacilityReferralResponseSchema(BaseModel):
    """Accept or decline an inter-facility referral."""

    status: ReferralStatus  # Should be ACCEPTED or DECLINED
    note: Optional[str] = None
    access_expiry_days: Optional[int] = Field(default=30, ge=1, le=365)


# ============================================================
# RESPONSES
# ============================================================


class ReferralReadSchema(BaseModel):
    """Detailed referral record returned by API endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    referral_no: str
    patient_id: int
    visit_id: Optional[int] = None
    referring_staff_id: int
    destination_facility: str
    source_facility_id: Optional[int] = None
    destination_facility_id: Optional[int] = None
    reason_for_referral: str
    clinical_summary: Optional[str] = None
    referral_date: datetime
    status: ReferralStatus
    priority: ReferralPriority
    date_created: datetime
    date_updated: datetime


class InterFacilityReferralReadSchema(BaseModel):
    """Detailed inter-facility referral record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    referral_no: str
    source_tenant_id: int
    source_facility_id: int
    target_tenant_id: int
    target_facility_id: int
    patient_global_id: str
    reason_for_referral: str
    clinical_summary: Optional[str] = None
    status: ReferralStatus
    acceptance_note: Optional[str] = None
    declined_reason: Optional[str] = None
    referral_date: datetime
    responded_at: Optional[datetime] = None
    is_history_access_granted: bool
    access_expires_at: Optional[datetime] = None
    date_created: datetime
    date_updated: datetime


class ReferralListResponseSchema(BaseModel):
    """Paginated referral list."""

    success: bool = True
    message: str = "Referrals fetched successfully."
    items: list[ReferralReadSchema]
    count: int


class InterFacilityReferralListResponseSchema(BaseModel):
    """Paginated inter-facility referral list."""

    success: bool = True
    message: str = "Inter-facility referrals fetched successfully."
    items: list[InterFacilityReferralReadSchema]
    count: int


class ReferralActionResponseSchema(BaseModel):
    """Single-referral action response wrapper."""

    success: bool = True
    message: str
    referral: ReferralReadSchema


class InterFacilityReferralActionResponseSchema(BaseModel):
    """Single-referral action response wrapper."""

    success: bool = True
    message: str
    referral: InterFacilityReferralReadSchema
