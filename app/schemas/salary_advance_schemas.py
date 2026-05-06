from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from app.core.enums import SalaryAdvanceStatus

class SalaryAdvanceBase(BaseModel):
    amount: float = Field(..., gt=0)
    reason: Optional[str] = None
    repayment_month: date

class SalaryAdvanceCreateSchema(SalaryAdvanceBase):
    staff_profile_id: int

class SalaryAdvanceUpdateSchema(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    reason: Optional[str] = None
    repayment_month: Optional[date] = None

class SalaryAdvanceSubmitSchema(BaseModel):
    flow_id: int
    title: str = "Salary Advance Request"
    submit_now: bool = True

class SalaryAdvanceReadSchema(SalaryAdvanceBase):
    id: int
    staff_profile_id: int
    status: SalaryAdvanceStatus
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    approval_request_id: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)
