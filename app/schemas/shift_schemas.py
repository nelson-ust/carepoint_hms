from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

from app.core.enums import StaffShiftType, ShiftStatus


# ── Shift Definition ─────────────────────────────────────────────────

class ShiftDefinitionBase(BaseModel):
    name: str = Field(..., max_length=150)
    code: str = Field(..., max_length=50)
    shift_type: StaffShiftType
    start_time: time
    end_time: time
    break_duration_minutes: int = Field(default=0, ge=0)
    color_hex: Optional[str] = Field(None, max_length=7)
    description: Optional[str] = None


class ShiftDefinitionCreateSchema(ShiftDefinitionBase):
    department_id: int


class ShiftDefinitionUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=150)
    shift_type: Optional[StaffShiftType] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    break_duration_minutes: Optional[int] = Field(None, ge=0)
    color_hex: Optional[str] = Field(None, max_length=7)
    description: Optional[str] = None


class ShiftDefinitionReadSchema(ShiftDefinitionBase):
    id: int
    department_id: int

    model_config = ConfigDict(from_attributes=True)


# ── Staff Shift Assignment ───────────────────────────────────────────

class StaffShiftAssignmentBase(BaseModel):
    staff_profile_id: int
    shift_definition_id: int
    shift_date: date
    notes: Optional[str] = None


class StaffShiftAssignmentCreateSchema(StaffShiftAssignmentBase):
    pass


class StaffShiftAssignmentUpdateSchema(BaseModel):
    shift_definition_id: Optional[int] = None
    shift_date: Optional[date] = None
    status: Optional[ShiftStatus] = None
    notes: Optional[str] = None


class StaffShiftAssignmentReadSchema(StaffShiftAssignmentBase):
    id: int
    status: ShiftStatus
    check_in_at: Optional[datetime] = None
    check_out_at: Optional[datetime] = None
    assigned_by_user_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# ── Shift Swap Request ───────────────────────────────────────────────

class ShiftSwapRequestCreateSchema(BaseModel):
    requester_assignment_id: int
    target_staff_id: int
    target_assignment_id: Optional[int] = None
    reason: Optional[str] = None


class ShiftSwapRequestReadSchema(BaseModel):
    id: int
    requester_assignment_id: int
    target_assignment_id: Optional[int] = None
    target_staff_id: int
    reason: Optional[str] = None
    status: str
    decided_by_user_id: Optional[int] = None
    decided_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
