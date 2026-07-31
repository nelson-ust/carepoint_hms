from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator
from app.core.enums import SalaryAdvanceStatus

class SalaryAdvanceBase(BaseModel):
    amount: float = Field(..., gt=0)
    reason: Optional[str] = None
    repayment_month: date
    account_id: Optional[int] = None

class SalaryAdvanceCreateSchema(SalaryAdvanceBase):
    staff_profile_id: int
    account_id: int = Field(..., description="Chart-of-accounts account to post this advance to.")

class SalaryAdvanceUpdateSchema(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    reason: Optional[str] = None
    repayment_month: Optional[date] = None
    account_id: Optional[int] = None

class SalaryAdvanceSubmitSchema(BaseModel):
    flow_id: Optional[int] = None
    title: str = "Salary Advance Request"
    submit_now: bool = True
    assigned_approver_user_id: Optional[int] = None


class SalaryAdvanceSelfCreateSchema(SalaryAdvanceBase):
    """Self-service create — the staff profile is resolved from the caller."""
    account_id: int = Field(..., description="Chart-of-accounts account to post this advance to.")

class SalaryAdvanceReadSchema(SalaryAdvanceBase):
    id: int
    staff_profile_id: int
    status: SalaryAdvanceStatus
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    approval_request_id: Optional[int] = None
    account_code: Optional[str] = None
    account_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

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
