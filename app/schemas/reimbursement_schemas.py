from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ReimbursementStatus

class ReimbursementBaseSchema(BaseModel):
    staff_profile_id: int
    expense_date: date
    amount: Decimal = Field(..., max_digits=12, decimal_places=2)
    category: str = Field(..., max_length=100)
    description: str
    receipt_url: Optional[str] = Field(None, max_length=255)

class ReimbursementCreateSchema(ReimbursementBaseSchema):
    pass

class ReimbursementUpdateSchema(BaseModel):
    expense_date: Optional[date] = None
    amount: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    category: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    receipt_url: Optional[str] = Field(None, max_length=255)

class ReimbursementReadSchema(ReimbursementBaseSchema):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: ReimbursementStatus
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    decided_by_user_id: Optional[int] = None
    decision_note: Optional[str] = None

class ReimbursementSubmitSchema(BaseModel):
    flow_id: int
    title: str
    submit_now: bool = True
