# app/schemas/consultation_schema.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConsultationCreateSchema(BaseModel):
    visit_id: int
    clinician_staff_id: Optional[int] = None
    subjective_note: Optional[str] = Field(None, max_length=8000)
    objective_note: Optional[str] = Field(None, max_length=8000)
    assessment_note: Optional[str] = Field(None, max_length=8000)
    plan_note: Optional[str] = Field(None, max_length=8000)


class ConsultationUpdateSchema(BaseModel):
    subjective_note: Optional[str] = Field(None, max_length=8000)
    objective_note: Optional[str] = Field(None, max_length=8000)
    assessment_note: Optional[str] = Field(None, max_length=8000)
    plan_note: Optional[str] = Field(None, max_length=8000)


class ConsultationFinalizeSchema(BaseModel):
    """Finalize consultation. Optional next-step routing instructions."""

    next_service_delivery_point_id: Optional[int] = Field(
        None, description="Next routing target (lab/pharmacy/cashier/discharge)."
    )
    end_visit: bool = Field(default=False, description="When True, mark the visit completed instead of routing.")
    closing_note: Optional[str] = Field(None, max_length=2000)


class ConsultationReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    clinician_staff_id: Optional[int] = None
    status: str
    subjective_note: Optional[str] = None
    objective_note: Optional[str] = None
    assessment_note: Optional[str] = None
    plan_note: Optional[str] = None
    consultation_started_at: Optional[datetime] = None
    consultation_ended_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ConsultationListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Consultations fetched successfully."
    items: list[ConsultationReadSchema]
    count: int
    meta: dict


class ConsultationActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    consultation: ConsultationReadSchema
