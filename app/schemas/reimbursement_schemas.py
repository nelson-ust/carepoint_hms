from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import ReimbursementStatus

class ReimbursementBaseSchema(BaseModel):
    staff_profile_id: int
    expense_date: date
    amount: Decimal = Field(..., max_digits=12, decimal_places=2)
    category: str = Field(..., max_length=100)
    description: str
    receipt_url: Optional[str] = Field(None, max_length=255)
    account_id: Optional[int] = None

class ReimbursementCreateSchema(ReimbursementBaseSchema):
    account_id: int = Field(..., description="Chart-of-accounts account to post this claim to.")

class ReimbursementUpdateSchema(BaseModel):
    expense_date: Optional[date] = None
    amount: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    category: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    receipt_url: Optional[str] = Field(None, max_length=255)
    account_id: Optional[int] = None

class ReimbursementReadSchema(ReimbursementBaseSchema):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: ReimbursementStatus
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    decided_by_user_id: Optional[int] = None
    decision_note: Optional[str] = None
    approval_request_id: Optional[int] = None
    #: Presigned, time-limited URL for VIEWING the receipt (private bucket).
    receipt_display_url: Optional[str] = None
    account_code: Optional[str] = None
    account_name: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _resolve_account(cls, data):
        acct = getattr(data, "account", None)
        if acct is not None:
            try:
                data.account_code = acct.code
                data.account_name = acct.name
            except Exception:
                pass
        return data

class ReimbursementSubmitSchema(BaseModel):
    flow_id: Optional[int] = None
    title: str
    submit_now: bool = True
    assigned_approver_user_id: Optional[int] = None


class ReimbursementSelfCreateSchema(BaseModel):
    """Self-service create — the staff profile is resolved from the caller."""
    expense_date: date
    amount: Decimal = Field(..., max_digits=12, decimal_places=2)
    category: str = Field(..., max_length=100)
    description: str
    receipt_url: Optional[str] = Field(None, max_length=255)
    account_id: int = Field(..., description="Chart-of-accounts account to post this claim to.")
