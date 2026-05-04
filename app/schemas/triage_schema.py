# app/schemas/triage_schema.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TriageCreateSchema(BaseModel):
    visit_id: int
    chief_complaint: Optional[str] = Field(None, max_length=2000)
    triage_note: Optional[str] = Field(None, max_length=4000)
    priority: str = Field(default="NORMAL")
    assessed_by_staff_id: Optional[int] = None
    update_visit_priority: bool = Field(default=True, description="Mirror priority back to the Visit record.")

    @field_validator("priority")
    @classmethod
    def normalize_priority(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"LOW", "NORMAL", "HIGH", "URGENT", "EMERGENCY"}:
            raise ValueError("priority must be one of LOW, NORMAL, HIGH, URGENT, EMERGENCY.")
        return normalized


class TriageUpdateSchema(BaseModel):
    chief_complaint: Optional[str] = Field(None, max_length=2000)
    triage_note: Optional[str] = Field(None, max_length=4000)
    priority: Optional[str] = None
    update_visit_priority: bool = True

    @field_validator("priority")
    @classmethod
    def normalize_priority(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        if normalized not in {"LOW", "NORMAL", "HIGH", "URGENT", "EMERGENCY"}:
            raise ValueError("priority must be one of LOW, NORMAL, HIGH, URGENT, EMERGENCY.")
        return normalized


class TriageReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    assessed_by_staff_id: Optional[int] = None
    chief_complaint: Optional[str] = None
    triage_note: Optional[str] = None
    priority: str
    assessed_at: datetime
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TriageListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Triage assessments fetched successfully."
    items: list[TriageReadSchema]
    count: int
    meta: dict


class TriageActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    triage: TriageReadSchema
