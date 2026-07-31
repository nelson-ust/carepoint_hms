# app/schemas/consultation_schema.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ConsultationCreateSchema(BaseModel):
    visit_id: int
    clinician_staff_id: Optional[int] = None
    subjective_note: Optional[str] = Field(None, max_length=8000)
    objective_note: Optional[str] = Field(None, max_length=8000)
    assessment_note: Optional[str] = Field(None, max_length=8000)
    plan_note: Optional[str] = Field(None, max_length=8000)
    recommends_admission: bool = Field(
        default=False,
        description="Doctor recommends the patient be admitted as an inpatient.",
    )
    admission_recommendation_note: Optional[str] = Field(None, max_length=4000)


class ConsultationUpdateSchema(BaseModel):
    subjective_note: Optional[str] = Field(None, max_length=8000)
    objective_note: Optional[str] = Field(None, max_length=8000)
    assessment_note: Optional[str] = Field(None, max_length=8000)
    plan_note: Optional[str] = Field(None, max_length=8000)
    recommends_admission: Optional[bool] = None
    admission_recommendation_note: Optional[str] = Field(None, max_length=4000)


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
    recommends_admission: bool = False
    admission_recommended_at: Optional[datetime] = None
    admission_recommendation_note: Optional[str] = None
    consultation_started_at: Optional[datetime] = None
    consultation_ended_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Clinical Context (Populated via model_validator)
    patient_name: Optional[str] = None
    hospital_number: Optional[str] = None
    clinician_name: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_context(cls, data: Any) -> Any:
        # Resolve Patient Info
        visit = getattr(data, "visit", None)
        patient = getattr(visit, "patient", None) if visit else None
        if patient:
            data.patient_name = f"{patient.first_name} {patient.last_name}"
            data.hospital_number = patient.hospital_number
        
        # Resolve Clinician Info
        staff = getattr(data, "clinician_staff", None)
        user = getattr(staff, "user", None) if staff else None
        if user:
            data.clinician_name = f"{user.first_name} {user.last_name}"
            
        return data


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
