# app/schemas/insurance_claim_schemas.py
from __future__ import annotations

"""
Pydantic schemas for the Insurance Claims module.

Covers:
- ``ClaimBatch``           — submission batch
- ``InsuranceClaim``       — header + items
- ``ClaimAuthorization``   — pre-auth
- ``ClaimAdjudication``    — insurer's decision
- ``ClaimPayment``         — receipts against approved amount
- ``ClaimAppeal``          — appeal of (partial) rejection
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================
# SHARED VALIDATORS
# ============================================================


_CLAIM_BATCH_STATUSES = {
    "DRAFT", "SUBMITTED", "ACKNOWLEDGED", "PARTIALLY_ADJUDICATED",
    "ADJUDICATED", "PAID", "REJECTED",
}
_CLAIM_STATUSES = {
    "DRAFT", "PENDING_AUTH", "AUTHORIZED", "SUBMITTED", "UNDER_REVIEW",
    "APPROVED", "PARTIALLY_APPROVED", "REJECTED", "PAID", "APPEALED", "CLOSED",
}
_AUTH_STATUSES = {
    "REQUESTED", "PENDING", "APPROVED", "PARTIALLY_APPROVED",
    "DECLINED", "EXPIRED", "CANCELLED",
}
_ADJUDICATION_OUTCOMES = {"APPROVED", "PARTIALLY_APPROVED", "DENIED", "PENDING"}
_APPEAL_STATUSES = {
    "DRAFT", "SUBMITTED", "UNDER_REVIEW", "UPHELD", "OVERTURNED",
    "PARTIALLY_OVERTURNED", "WITHDRAWN",
}


def _normalize(allowed: set[str], v: str) -> str:
    n = v.strip().upper()
    if n not in allowed:
        raise ValueError(f"Value must be one of {sorted(allowed)}.")
    return n


# ============================================================
# CLAIM BATCH
# ============================================================


class ClaimBatchCreateSchema(BaseModel):
    insurance_provider_id: int
    facility_id: Optional[int] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    notes: Optional[str] = None


class ClaimBatchSubmitSchema(BaseModel):
    submitted_by_staff_id: Optional[int] = None
    notes: Optional[str] = None


class ClaimBatchAcknowledgeSchema(BaseModel):
    acknowledged_at: Optional[datetime] = None
    notes: Optional[str] = None


class ClaimBatchReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_no: str
    insurance_provider_id: int
    facility_id: Optional[int] = None
    submitted_by_staff_id: Optional[int] = None
    status: str
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    submitted_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    total_claims: int = 0
    total_billed_amount: Decimal = Decimal("0")
    total_approved_amount: Decimal = Decimal("0")
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class ClaimBatchListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Claim batches fetched successfully."
    items: list[ClaimBatchReadSchema]
    count: int
    meta: dict


class ClaimBatchActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    batch: ClaimBatchReadSchema


# ============================================================
# INSURANCE CLAIM
# ============================================================


class InsuranceClaimItemCreateSchema(BaseModel):
    invoice_item_id: Optional[int] = None
    billable_service_id: Optional[int] = None
    service_date: Optional[date] = None
    procedure_code: Optional[str] = Field(None, max_length=100)
    diagnosis_code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")


class InsuranceClaimCreateSchema(BaseModel):
    """Create a new claim header. Provide ``items`` to create line details."""

    patient_id: int
    patient_insurance_id: int
    insurance_provider_id: int
    visit_id: Optional[int] = None
    invoice_id: Optional[int] = None
    facility_id: Optional[int] = None
    batch_id: Optional[int] = None
    service_date: Optional[date] = None
    diagnosis_codes: Optional[dict[str, Any]] = None
    primary_diagnosis_text: Optional[str] = None
    notes: Optional[str] = None
    items: list[InsuranceClaimItemCreateSchema] = Field(default_factory=list)


class InsuranceClaimSubmitSchema(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)


class InsuranceClaimItemReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    invoice_item_id: Optional[int] = None
    billable_service_id: Optional[int] = None
    service_date: Optional[date] = None
    procedure_code: Optional[str] = None
    diagnosis_code: Optional[str] = None
    description: Optional[str] = None
    quantity: Decimal
    unit_price: Decimal
    billed_amount: Decimal
    approved_amount: Decimal
    rejected_amount: Decimal


class InsuranceClaimReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_no: str
    batch_id: Optional[int] = None
    patient_id: int
    patient_insurance_id: int
    insurance_provider_id: int
    visit_id: Optional[int] = None
    invoice_id: Optional[int] = None
    facility_id: Optional[int] = None
    status: str
    service_date: Optional[date] = None
    diagnosis_codes: Optional[dict[str, Any]] = None
    primary_diagnosis_text: Optional[str] = None
    billed_amount: Decimal
    approved_amount: Decimal
    rejected_amount: Decimal
    patient_responsibility_amount: Decimal
    paid_amount: Decimal
    submitted_at: Optional[datetime] = None
    notes: Optional[str] = None
    items: list[InsuranceClaimItemReadSchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class InsuranceClaimListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Insurance claims fetched successfully."
    items: list[InsuranceClaimReadSchema]
    count: int
    meta: dict


class InsuranceClaimActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    claim: InsuranceClaimReadSchema


# ============================================================
# AUTHORIZATION
# ============================================================


class ClaimAuthorizationCreateSchema(BaseModel):
    patient_insurance_id: int
    requested_service: str = Field(..., min_length=1, max_length=255)
    requested_amount: Optional[Decimal] = None
    claim_id: Optional[int] = None
    requested_at: Optional[datetime] = None
    decision_reason: Optional[str] = None


class ClaimAuthorizationDecisionSchema(BaseModel):
    decision: str = Field(..., description="APPROVED / PARTIALLY_APPROVED / DECLINED")
    authorization_no: Optional[str] = Field(None, max_length=150)
    approved_amount: Optional[Decimal] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    decision_reason: Optional[str] = None

    @field_validator("decision")
    @classmethod
    def normalize_decision(cls, v: str) -> str:
        return _normalize(_AUTH_STATUSES, v)


class ClaimAuthorizationReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: Optional[int] = None
    patient_insurance_id: int
    authorization_no: Optional[str] = None
    requested_service: str
    requested_amount: Optional[Decimal] = None
    approved_amount: Optional[Decimal] = None
    status: str
    requested_at: datetime
    decided_at: Optional[datetime] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    decision_reason: Optional[str] = None


class ClaimAuthorizationActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    authorization: ClaimAuthorizationReadSchema


# ============================================================
# ADJUDICATION
# ============================================================


class ClaimAdjudicationCreateSchema(BaseModel):
    claim_id: int
    outcome: str
    approved_amount: Decimal = Decimal("0")
    rejected_amount: Decimal = Decimal("0")
    adjudication_no: Optional[str] = Field(None, max_length=150)
    rejection_codes: Optional[dict[str, Any]] = None
    explanation_of_benefit: Optional[str] = None
    adjudicated_at: Optional[datetime] = None

    @field_validator("outcome")
    @classmethod
    def normalize_outcome(cls, v: str) -> str:
        return _normalize(_ADJUDICATION_OUTCOMES, v)


class ClaimAdjudicationReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    adjudication_no: Optional[str] = None
    outcome: str
    approved_amount: Decimal
    rejected_amount: Decimal
    rejection_codes: Optional[dict[str, Any]] = None
    explanation_of_benefit: Optional[str] = None
    adjudicated_at: datetime


class ClaimAdjudicationActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    adjudication: ClaimAdjudicationReadSchema


# ============================================================
# PAYMENT
# ============================================================


class ClaimPaymentCreateSchema(BaseModel):
    claim_id: int
    payment_reference: str = Field(..., min_length=1, max_length=150)
    amount: Decimal = Field(..., gt=Decimal("0"))
    currency: Optional[str] = Field(None, max_length=10)
    paid_at: Optional[datetime] = None
    payment_method: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class ClaimPaymentReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    payment_reference: str
    amount: Decimal
    currency: Optional[str] = None
    paid_at: datetime
    payment_method: Optional[str] = None
    notes: Optional[str] = None


class ClaimPaymentActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    payment: ClaimPaymentReadSchema


# ============================================================
# APPEAL
# ============================================================


class ClaimAppealCreateSchema(BaseModel):
    claim_id: int
    appeal_text: str = Field(..., min_length=1)
    submitted_by_staff_id: Optional[int] = None
    additional_evidence_url: Optional[str] = None
    additional_amount_requested: Optional[Decimal] = None


class ClaimAppealDecisionSchema(BaseModel):
    decision: str = Field(..., description="UPHELD / OVERTURNED / PARTIALLY_OVERTURNED / WITHDRAWN")
    decision_text: Optional[str] = None
    additional_amount_approved: Optional[Decimal] = None

    @field_validator("decision")
    @classmethod
    def normalize_decision(cls, v: str) -> str:
        return _normalize(_APPEAL_STATUSES, v)


class ClaimAppealReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    appeal_no: str
    status: str
    submitted_by_staff_id: Optional[int] = None
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    decision_text: Optional[str] = None
    appeal_text: str
    additional_evidence_url: Optional[str] = None
    additional_amount_requested: Optional[Decimal] = None
    additional_amount_approved: Optional[Decimal] = None


class ClaimAppealActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    appeal: ClaimAppealReadSchema
