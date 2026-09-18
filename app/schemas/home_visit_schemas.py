# app/schemas/home_visit_schemas.py
from __future__ import annotations

"""Pydantic schemas for the Home Visit module."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import HomeVisitPriority, HomeVisitStatus, HomeVisitType


# ---------------------------------------------------------------------------
# Home Visit
# ---------------------------------------------------------------------------
class HomeVisitCreateSchema(BaseModel):
    patient_id: int
    care_plan_id: Optional[int] = None
    facility_id: Optional[int] = None
    assigned_staff_id: Optional[int] = None
    visit_type: HomeVisitType = HomeVisitType.ROUTINE
    priority: HomeVisitPriority = HomeVisitPriority.NORMAL
    reason: Optional[str] = None
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None
    eta_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None


class HomeVisitUpdateSchema(BaseModel):
    care_plan_id: Optional[int] = None
    facility_id: Optional[int] = None
    visit_type: Optional[HomeVisitType] = None
    priority: Optional[HomeVisitPriority] = None
    reason: Optional[str] = None
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None
    eta_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    recurrence_rule: Optional[str] = None


class HomeVisitAssignSchema(BaseModel):
    assigned_staff_id: int
    eta_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    note: Optional[str] = None


class HomeVisitStatusChangeSchema(BaseModel):
    status: HomeVisitStatus
    note: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    eta_minutes: Optional[int] = Field(default=None, ge=0, le=1440)


class HomeVisitCancelSchema(BaseModel):
    reason: Optional[str] = None


class HomeVisitReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_code: str
    patient_id: int
    facility_id: Optional[int] = None
    care_plan_id: Optional[int] = None
    assigned_staff_id: Optional[int] = None
    requested_by_user_id: Optional[int] = None
    visit_type: str
    status: str
    priority: str
    reason: Optional[str] = None
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None
    eta_minutes: Optional[int] = None
    en_route_at: Optional[datetime] = None
    arrived_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None
    cancellation_reason: Optional[str] = None
    # denormalized (populated by service)
    patient_name: Optional[str] = None
    assigned_staff_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class HomeVisitStatusEventReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    home_visit_id: int
    from_status: Optional[str] = None
    to_status: str
    note: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    changed_by_user_id: Optional[int] = None
    occurred_at: datetime


# ---------------------------------------------------------------------------
# Home Visit Documentation (note)
# ---------------------------------------------------------------------------
class HomeVisitNoteUpsertSchema(BaseModel):
    reason_for_visit: Optional[str] = None
    symptoms: Optional[str] = None
    physical_assessment: Optional[str] = None
    nursing_assessment: Optional[str] = None
    clinical_observations: Optional[str] = None
    assessment_diagnosis: Optional[str] = None
    procedures_performed: Optional[str] = None
    medication_administered: Optional[str] = None
    wound_notes: Optional[str] = None
    patient_education: Optional[str] = None
    care_plan_updates: Optional[str] = None
    follow_up_required: bool = False
    follow_up_notes: Optional[str] = None
    # bedside vitals snapshot
    temperature_celsius: Optional[Decimal] = None
    pulse_rate: Optional[int] = None
    respiratory_rate: Optional[int] = None
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    oxygen_saturation: Optional[Decimal] = None
    blood_glucose: Optional[Decimal] = None
    weight_kg: Optional[Decimal] = None
    pain_score: Optional[int] = Field(default=None, ge=0, le=10)
    checklist: Optional[dict] = None
    attachments: Optional[dict] = None
    signed_by_staff_id: Optional[int] = None
    signature_image_key: Optional[str] = None
    # when true, persisted vitals also create remote-monitoring readings + run alerts
    record_vitals_as_readings: bool = True


class HomeVisitNoteReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    home_visit_id: int
    patient_id: int
    reason_for_visit: Optional[str] = None
    symptoms: Optional[str] = None
    physical_assessment: Optional[str] = None
    nursing_assessment: Optional[str] = None
    clinical_observations: Optional[str] = None
    assessment_diagnosis: Optional[str] = None
    procedures_performed: Optional[str] = None
    medication_administered: Optional[str] = None
    wound_notes: Optional[str] = None
    patient_education: Optional[str] = None
    care_plan_updates: Optional[str] = None
    follow_up_required: bool = False
    follow_up_notes: Optional[str] = None
    temperature_celsius: Optional[Decimal] = None
    pulse_rate: Optional[int] = None
    respiratory_rate: Optional[int] = None
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    oxygen_saturation: Optional[Decimal] = None
    blood_glucose: Optional[Decimal] = None
    weight_kg: Optional[Decimal] = None
    pain_score: Optional[int] = None
    checklist: Optional[dict] = None
    attachments: Optional[dict] = None
    signed_by_staff_id: Optional[int] = None
    signature_image_key: Optional[str] = None
    signed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Response wrappers
# ---------------------------------------------------------------------------
class HomeVisitActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    home_visit: HomeVisitReadSchema


class HomeVisitListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Home visits fetched successfully."
    items: list[HomeVisitReadSchema]
    count: int
    meta: dict


class HomeVisitEventListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Status events fetched successfully."
    items: list[HomeVisitStatusEventReadSchema]
    count: int
    meta: dict


class HomeVisitNoteResponseSchema(BaseModel):
    success: bool = True
    message: str
    note: HomeVisitNoteReadSchema
