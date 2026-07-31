# app/schemas/membership_card_schemas.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import (
    MembershipCardStatus,
    MembershipCardTransactionType,
    CardFundingRequestStatus,
)


class MembershipCardBase(BaseModel):
    card_number: str = Field(..., description="Unique card identifier")
    status: MembershipCardStatus = Field(default=MembershipCardStatus.ACTIVE)
    expiry_date: Optional[date] = None


class MembershipCardCreate(BaseModel):
    patient_id: int
    # Optional — the service auto-generates a unique number and resolves a
    # default issuing facility when omitted, so the UI only needs a patient.
    card_number: Optional[str] = Field(default=None, description="Auto-generated if omitted")
    issuing_facility_id: Optional[int] = None
    status: MembershipCardStatus = Field(default=MembershipCardStatus.ACTIVE)
    expiry_date: Optional[date] = None
    initial_balance: Decimal = Field(default=Decimal("0.00"), ge=0)


class MembershipCardStatsSchema(BaseModel):
    total: int = 0
    active: int = 0
    inactive: int = 0
    suspended: int = 0
    expired: int = 0
    lost: int = 0
    total_balance: Decimal = Decimal("0.00")


class MembershipCardUpdate(BaseModel):
    status: Optional[MembershipCardStatus] = None
    expiry_date: Optional[date] = None


class MembershipCardTransactionBase(BaseModel):
    amount: Decimal = Field(..., gt=0)
    transaction_type: MembershipCardTransactionType
    payment_source: Optional[str] = None
    payment_reference: Optional[str] = None
    narration: Optional[str] = None


class MembershipCardFund(BaseModel):
    amount: Decimal = Field(..., gt=0)
    payment_source: str = Field(..., description="CASH, BANK_TRANSFER, ONLINE, etc.")
    payment_reference: Optional[str] = None
    narration: Optional[str] = None


class MembershipCardDebit(BaseModel):
    amount: Decimal = Field(..., gt=0)
    invoice_id: Optional[int] = None
    visit_id: Optional[int] = None
    narration: Optional[str] = None


class MembershipCardTransactionRead(MembershipCardTransactionBase):
    id: int
    membership_card_id: int
    patient_id: int
    balance_before: Decimal
    balance_after: Decimal
    facility_id: int
    processed_by_id: int
    transaction_date: datetime
    invoice_id: Optional[int] = None
    visit_id: Optional[int] = None
    payment_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class MembershipCardRead(MembershipCardBase):
    id: int
    patient_id: int
    balance: Decimal
    issuing_facility_id: int
    issued_by_id: int
    date_issued: date
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    global_patient_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_patient_details(cls, data: Any) -> Any:
        # Handle ORM object
        if hasattr(data, "patient") and data.patient:
            patient = data.patient
            if not getattr(data, "patient_name", None):
                first_name = getattr(patient, "first_name", "")
                last_name = getattr(patient, "last_name", "")
                middle_name = getattr(patient, "middle_name", "")
                name_parts = [p for p in [first_name, middle_name, last_name] if p]
                setattr(data, "patient_name", " ".join(name_parts))
            if not getattr(data, "patient_phone", None):
                setattr(data, "patient_phone", getattr(patient, "phone_number", None))
            if not getattr(data, "global_patient_id", None):
                setattr(data, "global_patient_id", getattr(patient, "global_patient_id", None))
        # Handle dictionary (e.g. from JSON)
        elif isinstance(data, dict) and "patient" in data and data["patient"]:
            patient = data["patient"]
            if not data.get("patient_name"):
                if isinstance(patient, dict):
                    first_name = patient.get("first_name", "")
                    last_name = patient.get("last_name", "")
                    middle_name = patient.get("middle_name", "")
                    name_parts = [p for p in [first_name, middle_name, last_name] if p]
                    data["patient_name"] = " ".join(name_parts)
                    data["patient_phone"] = patient.get("phone_number")
                    data["global_patient_id"] = patient.get("global_patient_id")
                else:
                    first_name = getattr(patient, "first_name", "")
                    last_name = getattr(patient, "last_name", "")
                    middle_name = getattr(patient, "middle_name", "")
                    name_parts = [p for p in [first_name, middle_name, last_name] if p]
                    data["patient_name"] = " ".join(name_parts)
                    data["patient_phone"] = getattr(patient, "phone_number", None)
                    data["global_patient_id"] = getattr(patient, "global_patient_id", None)
        return data


class MembershipCardWithTransactions(MembershipCardRead):
    transactions: list[MembershipCardTransactionRead] = []


# ---------------------------------------------------------------------------
# Manual card-funding requests (patient-submitted, staff-approved)
# ---------------------------------------------------------------------------


class CardFundingRequestReview(BaseModel):
    """Staff decision payload for approving/rejecting a manual funding request."""

    note: Optional[str] = Field(default=None, max_length=1000)


class CardFundingRequestRead(BaseModel):
    id: int
    patient_id: int
    membership_card_id: int
    amount: Decimal
    payment_method: str
    payment_reference: Optional[str] = None
    depositor_name: Optional[str] = None
    note: Optional[str] = None

    evidence_file_name: Optional[str] = None
    evidence_file_url: Optional[str] = None
    evidence_content_type: Optional[str] = None

    status: CardFundingRequestStatus
    reviewed_by_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_note: Optional[str] = None
    transaction_id: Optional[int] = None

    date_created: datetime

    # Convenience fields for the staff review queue.
    card_number: Optional[str] = None
    patient_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _enrich(cls, data: Any) -> Any:
        # Only enrich when reading an ORM object.
        if isinstance(data, dict):
            return data
        card = getattr(data, "membership_card", None)
        if card is not None and not getattr(data, "card_number", None):
            try:
                setattr(data, "card_number", getattr(card, "card_number", None))
            except Exception:
                pass
        patient = getattr(data, "patient", None)
        if patient is not None and not getattr(data, "patient_name", None):
            parts = [
                getattr(patient, "first_name", "") or "",
                getattr(patient, "middle_name", "") or "",
                getattr(patient, "last_name", "") or "",
            ]
            try:
                setattr(data, "patient_name", " ".join(p for p in parts if p).strip() or None)
            except Exception:
                pass
        return data
