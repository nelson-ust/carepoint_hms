# app/schemas/paystack_schemas.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.core.enums import PaystackTransactionStatus


class PaystackTransactionBase(BaseModel):
    amount: Decimal
    currency: str = "NGN"


class PaystackTransactionCreate(PaystackTransactionBase):
    patient_id: int
    membership_card_id: int


class PaystackTransactionInitialize(BaseModel):
    amount: Decimal
    email: str


class PaystackTransactionRead(PaystackTransactionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    access_code: Optional[str] = None
    authorization_url: Optional[str] = None
    status: PaystackTransactionStatus
    paid_at: Optional[datetime] = None
    date_created: datetime
