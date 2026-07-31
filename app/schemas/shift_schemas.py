from __future__ import annotations

from datetime import date, datetime, time
from typing import List, Optional
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
    # Optional "unit" scope — a service delivery point inside the department
    # (ward, clinic, ICU, pharmacy…). Null means the shift is department-wide.
    service_delivery_point_id: Optional[int] = None


class ShiftDefinitionUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=150)
    shift_type: Optional[StaffShiftType] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    break_duration_minutes: Optional[int] = Field(None, ge=0)
    color_hex: Optional[str] = Field(None, max_length=7)
    description: Optional[str] = None
    # Nullable on purpose: send null to make a unit-scoped shift department-wide.
    service_delivery_point_id: Optional[int] = None


class ShiftDefinitionReadSchema(ShiftDefinitionBase):
    id: int
    department_id: int
    service_delivery_point_id: Optional[int] = None
    department_name: Optional[str] = None
    service_delivery_point_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ShiftQuickSetupSchema(BaseModel):
    """
    One-click creation of a standard rotation for a department (optionally a
    single unit within it):

    * ``TWO``   → Day (07:00–19:00) + Night (19:00–07:00)
    * ``THREE`` → Morning (07:00–14:00) + Afternoon (14:00–21:00) +
                  Night (21:00–07:00)
    """

    department_id: int
    service_delivery_point_id: Optional[int] = None
    preset: str = Field(..., pattern="^(TWO|THREE)$")
    # When true, existing definitions for the same scope are cleared first so
    # re-running the setup doesn't pile up duplicates.
    replace_existing: bool = False


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
