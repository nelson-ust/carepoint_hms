from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import LeaveStatus

class LeaveRequestBaseSchema(BaseModel):
    staff_profile_id: int
    leave_type_id: int
    start_date: date
    end_date: date
    days_requested: Decimal = Field(default=Decimal("0.00"), max_digits=6, decimal_places=2)
    reason: Optional[str] = None
    handover_notes: Optional[str] = None
    cover_staff_id: Optional[int] = None

class LeaveRequestCreateSchema(LeaveRequestBaseSchema):
    pass

class LeaveRequestUpdateSchema(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    days_requested: Optional[Decimal] = Field(None, max_digits=6, decimal_places=2)
    reason: Optional[str] = None
    handover_notes: Optional[str] = None
    cover_staff_id: Optional[int] = None

class LeaveRequestReadSchema(LeaveRequestBaseSchema):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: LeaveStatus
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    decided_by_user_id: Optional[int] = None
    decision_note: Optional[str] = None

class LeaveRequestSubmitSchema(BaseModel):
    flow_id: int
    title: str
    submit_now: bool = True
