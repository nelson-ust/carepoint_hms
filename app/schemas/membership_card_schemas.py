# app/schemas/membership_card_schemas.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import MembershipCardStatus, MembershipCardTransactionType


class MembershipCardBase(BaseModel):
    card_number: str = Field(..., description="Unique card identifier")
    status: MembershipCardStatus = Field(default=MembershipCardStatus.ACTIVE)
    expiry_date: Optional[date] = None


class MembershipCardCreate(MembershipCardBase):
    patient_id: int
    issuing_facility_id: int
    initial_balance: Decimal = Field(default=Decimal("0.00"), ge=0)


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
                else:
                    first_name = getattr(patient, "first_name", "")
                    last_name = getattr(patient, "last_name", "")
                    middle_name = getattr(patient, "middle_name", "")
                    name_parts = [p for p in [first_name, middle_name, last_name] if p]
                    data["patient_name"] = " ".join(name_parts)
                    data["patient_phone"] = getattr(patient, "phone_number", None)
        return data


class MembershipCardWithTransactions(MembershipCardRead):
    transactions: list[MembershipCardTransactionRead] = []
