# app/schemas/diagnosis_schema.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DiagnosisCreateSchema(BaseModel):
    visit_id: int
    consultation_id: Optional[int] = None
    diagnosis_name: str = Field(..., min_length=1, max_length=255)
    diagnosis_code: Optional[str] = Field(None, max_length=50, description="ICD-10 / ICD-11 code if available.")
    diagnosis_type: Optional[str] = Field(
        None, max_length=50, description="PROVISIONAL, WORKING, FINAL, DIFFERENTIAL.")
    diagnosis_note: Optional[str] = Field(None, max_length=4000)

    @field_validator("diagnosis_type")
    @classmethod
    def normalize_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return value.strip().upper() or None

    @field_validator("diagnosis_code")
    @classmethod
    def normalize_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return value.strip().upper() or None


class DiagnosisUpdateSchema(BaseModel):
    diagnosis_name: Optional[str] = Field(None, min_length=1, max_length=255)
    diagnosis_code: Optional[str] = Field(None, max_length=50)
    diagnosis_type: Optional[str] = Field(None, max_length=50)
    diagnosis_note: Optional[str] = Field(None, max_length=4000)


class DiagnosisReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    consultation_id: Optional[int] = None
    diagnosis_code: Optional[str] = None
    diagnosis_name: str
    diagnosis_type: Optional[str] = None
    diagnosis_note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DiagnosisListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Diagnoses fetched successfully."
    items: list[DiagnosisReadSchema]
    count: int
    meta: dict


class DiagnosisActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    diagnosis: DiagnosisReadSchema
