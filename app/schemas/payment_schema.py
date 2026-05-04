# app/schemas/payment_schema.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaymentReceiveSchema(BaseModel):
    invoice_id: int
    amount: Decimal = Field(..., gt=0)
    currency: str = "NGN"
    payment_method: str = "CASH"
    membership_card_id: Optional[int] = None
    received_by_staff_id: Optional[int] = None
    transaction_metadata: Optional[dict[str, Any]] = None
    note: Optional[str] = Field(None, max_length=2000)

    @field_validator("payment_method")
    @classmethod
    def normalize_payment_method(cls, v: str) -> str:
        normalized = v.strip().upper()
        if normalized not in {
            "CASH", "CARD", "BANK_TRANSFER", "MOBILE_MONEY",
            "INSURANCE", "LOYALTY", "WAIVER", "MEMBERSHIP_CARD", "OTHER",
        }:
            raise ValueError("payment_method invalid.")
        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        return v.strip().upper() or "NGN"


class PaymentRefundSchema(BaseModel):
    payment_id: int
    reason: Optional[str] = Field(None, max_length=2000)


class PaymentReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_id: int
    received_by_staff_id: Optional[int] = None
    payment_reference: str
    payment_method: Optional[str] = None
    payment_status: str
    amount: Decimal
    currency: str
    paid_at: Optional[datetime] = None
    transaction_metadata: Optional[dict[str, Any]] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None


class PaymentListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Payments fetched successfully."
    items: list[PaymentReadSchema]
    count: int
    meta: dict


class PaymentActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    payment: PaymentReadSchema
