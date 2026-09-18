# app/schemas/care_plan_schemas.py
from __future__ import annotations

"""Pydantic schemas for the Care Plan engine."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    CareFrequency,
    CarePlanGoalStatus,
    CarePlanGoalType,
    CarePlanInterventionStatus,
    CarePlanReviewOutcome,
    CarePlanStatus,
    CareTaskStatus,
    HomeVisitPriority,
)


# ---- Care Plan ----
class CarePlanCreateSchema(BaseModel):
    patient_id: int
    title: str
    condition: Optional[str] = None
    description: Optional[str] = None
    status: CarePlanStatus = CarePlanStatus.DRAFT
    priority: HomeVisitPriority = HomeVisitPriority.NORMAL
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    lead_staff_id: Optional[int] = None
    review_frequency_days: Optional[int] = Field(default=None, ge=1, le=365)
    next_review_date: Optional[date] = None


class CarePlanUpdateSchema(BaseModel):
    title: Optional[str] = None
    condition: Optional[str] = None
    description: Optional[str] = None
    status: Optional[CarePlanStatus] = None
    priority: Optional[HomeVisitPriority] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    lead_staff_id: Optional[int] = None
    review_frequency_days: Optional[int] = Field(default=None, ge=1, le=365)
    next_review_date: Optional[date] = None


class CarePlanReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    title: str
    condition: Optional[str] = None
    description: Optional[str] = None
    status: str
    priority: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    lead_staff_id: Optional[int] = None
    review_frequency_days: Optional[int] = None
    next_review_date: Optional[date] = None
    patient_name: Optional[str] = None
    lead_staff_name: Optional[str] = None
    goal_count: Optional[int] = None
    open_task_count: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---- Goal ----
class CarePlanGoalCreateSchema(BaseModel):
    description: str
    goal_type: CarePlanGoalType = CarePlanGoalType.SHORT_TERM
    target_date: Optional[date] = None
    baseline_value: Optional[str] = None
    target_value: Optional[str] = None
    current_value: Optional[str] = None
    measure_unit: Optional[str] = None
    progress_percent: Optional[int] = Field(default=0, ge=0, le=100)


class CarePlanGoalUpdateSchema(BaseModel):
    description: Optional[str] = None
    goal_type: Optional[CarePlanGoalType] = None
    status: Optional[CarePlanGoalStatus] = None
    target_date: Optional[date] = None
    baseline_value: Optional[str] = None
    target_value: Optional[str] = None
    current_value: Optional[str] = None
    measure_unit: Optional[str] = None
    progress_percent: Optional[int] = Field(default=None, ge=0, le=100)


class CarePlanGoalReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    care_plan_id: int
    description: str
    goal_type: str
    status: str
    target_date: Optional[date] = None
    baseline_value: Optional[str] = None
    target_value: Optional[str] = None
    current_value: Optional[str] = None
    measure_unit: Optional[str] = None
    progress_percent: Optional[int] = None


# ---- Intervention ----
class CarePlanInterventionCreateSchema(BaseModel):
    goal_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    assigned_staff_id: Optional[int] = None
    frequency: CareFrequency = CareFrequency.AS_NEEDED
    frequency_detail: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class CarePlanInterventionUpdateSchema(BaseModel):
    goal_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    assigned_staff_id: Optional[int] = None
    frequency: Optional[CareFrequency] = None
    frequency_detail: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[CarePlanInterventionStatus] = None


class CarePlanInterventionReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    care_plan_id: int
    goal_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    assigned_staff_id: Optional[int] = None
    frequency: str
    frequency_detail: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str


# ---- Task ----
class CareTaskCreateSchema(BaseModel):
    intervention_id: Optional[int] = None
    home_visit_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    assigned_staff_id: Optional[int] = None
    due_at: Optional[datetime] = None


class CareTaskUpdateSchema(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_staff_id: Optional[int] = None
    due_at: Optional[datetime] = None
    status: Optional[CareTaskStatus] = None


class CareTaskCompleteSchema(BaseModel):
    completion_note: Optional[str] = None
    completed_by_staff_id: Optional[int] = None


class CareTaskReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    care_plan_id: int
    intervention_id: Optional[int] = None
    home_visit_id: Optional[int] = None
    patient_id: int
    title: str
    description: Optional[str] = None
    assigned_staff_id: Optional[int] = None
    due_at: Optional[datetime] = None
    status: str
    completed_at: Optional[datetime] = None
    completed_by_staff_id: Optional[int] = None
    completion_note: Optional[str] = None


# ---- Progress note ----
class CarePlanProgressNoteCreateSchema(BaseModel):
    goal_id: Optional[int] = None
    note: str
    progress_value: Optional[str] = None
    recorded_by_staff_id: Optional[int] = None


class CarePlanProgressNoteReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    care_plan_id: int
    goal_id: Optional[int] = None
    note: str
    progress_value: Optional[str] = None
    recorded_by_staff_id: Optional[int] = None
    recorded_at: datetime


# ---- Review ----
class CarePlanReviewCreateSchema(BaseModel):
    reviewed_by_staff_id: Optional[int] = None
    review_date: Optional[date] = None
    summary: Optional[str] = None
    outcome: CarePlanReviewOutcome = CarePlanReviewOutcome.CONTINUE
    next_review_date: Optional[date] = None


class CarePlanReviewReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    care_plan_id: int
    reviewed_by_staff_id: Optional[int] = None
    review_date: date
    summary: Optional[str] = None
    outcome: str
    next_review_date: Optional[date] = None


# ---- Detail + wrappers ----
class CarePlanDetailSchema(CarePlanReadSchema):
    goals: list[CarePlanGoalReadSchema] = []
    interventions: list[CarePlanInterventionReadSchema] = []
    tasks: list[CareTaskReadSchema] = []
    progress_notes: list[CarePlanProgressNoteReadSchema] = []
    reviews: list[CarePlanReviewReadSchema] = []


class CarePlanActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    care_plan: CarePlanReadSchema


class CarePlanListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Care plans fetched successfully."
    items: list[CarePlanReadSchema]
    count: int
    meta: dict


class CareTaskListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Care tasks fetched successfully."
    items: list[CareTaskReadSchema]
    count: int
    meta: dict
