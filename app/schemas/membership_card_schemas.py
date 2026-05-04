# app/schemas/membership_card_schemas.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

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

    model_config = ConfigDict(from_attributes=True)


class MembershipCardWithTransactions(MembershipCardRead):
    transactions: list[MembershipCardTransactionRead] = []
