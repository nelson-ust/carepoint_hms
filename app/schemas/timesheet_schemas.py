from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import TimesheetStatus

# ============================================================
# TIMESHEET ENTRY SCHEMAS
# ============================================================

class TimesheetEntryBaseSchema(BaseModel):
    work_date: date
    regular_hours: Decimal = Field(default=Decimal("0.00"), max_digits=6, decimal_places=2)
    overtime_hours: Decimal = Field(default=Decimal("0.00"), max_digits=6, decimal_places=2)
    night_hours: Decimal = Field(default=Decimal("0.00"), max_digits=6, decimal_places=2)
    weekend_hours: Decimal = Field(default=Decimal("0.00"), max_digits=6, decimal_places=2)
    holiday_hours: Decimal = Field(default=Decimal("0.00"), max_digits=6, decimal_places=2)
    is_absent: bool = False
    is_leave: bool = False
    note: Optional[str] = None


class TimesheetEntryCreateSchema(TimesheetEntryBaseSchema):
    pass


class TimesheetEntryReadSchema(TimesheetEntryBaseSchema):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timesheet_id: int


# ============================================================
# TIMESHEET SCHEMAS
# ============================================================

class TimesheetBaseSchema(BaseModel):
    staff_profile_id: int
    period_start: date
    period_end: date
    notes: Optional[str] = None


class TimesheetCreateSchema(TimesheetBaseSchema):
    entries: List[TimesheetEntryCreateSchema] = Field(default_factory=list)


class TimesheetUpdateSchema(BaseModel):
    notes: Optional[str] = None
    entries: Optional[List[TimesheetEntryCreateSchema]] = None


class TimesheetReadSchema(TimesheetBaseSchema):
    model_config = ConfigDict(from_attributes=True)
    id: int
    total_regular_hours: Decimal
    total_overtime_hours: Decimal
    total_night_hours: Decimal
    total_weekend_hours: Decimal
    total_holiday_hours: Decimal
    absence_days: int
    status: TimesheetStatus
    submitted_at: Optional[datetime] = None
    approved_by_user_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    locked_at: Optional[datetime] = None
    approval_request_id: Optional[int] = None
    entries: List[TimesheetEntryReadSchema] = Field(default_factory=list)

class TimesheetSubmitSchema(BaseModel):
    flow_id: Optional[int] = None
    title: str
    submit_now: bool = True
    assigned_approver_user_id: Optional[int] = None


class TimesheetSelfCreateSchema(BaseModel):
    """Self-service create — the staff profile is resolved from the caller."""
    period_start: date
    period_end: date
    notes: Optional[str] = None
    entries: List[TimesheetEntryCreateSchema] = Field(default_factory=list)
