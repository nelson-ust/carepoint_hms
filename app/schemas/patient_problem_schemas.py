# app/schemas/patient_problem_schemas.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ProblemStatus


class PatientProblemBaseSchema(BaseModel):
    condition_name: str = Field(..., min_length=2, max_length=255)
    condition_code: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    status: ProblemStatus = ProblemStatus.ACTIVE
    is_chronic: bool = True
    onset_date: Optional[date] = None
    resolved_date: Optional[date] = None
    severity: Optional[str] = Field(None, max_length=30)
    notes: Optional[str] = None


class PatientProblemCreateSchema(PatientProblemBaseSchema):
    pass


class PatientProblemUpdateSchema(BaseModel):
    condition_name: Optional[str] = Field(None, min_length=2, max_length=255)
    condition_code: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    status: Optional[ProblemStatus] = None
    is_chronic: Optional[bool] = None
    onset_date: Optional[date] = None
    resolved_date: Optional[date] = None
    severity: Optional[str] = Field(None, max_length=30)
    notes: Optional[str] = None


class PatientProblemReadSchema(PatientProblemBaseSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    diagnosed_by_user_id: Optional[int] = None
    last_reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---- Clinical trends analytics ----

class TrendPoint(BaseModel):
    date: datetime
    value: float


class MetricTrend(BaseModel):
    key: str
    label: str
    unit: Optional[str] = None
    points: list[TrendPoint] = Field(default_factory=list)
    first_value: Optional[float] = None
    latest_value: Optional[float] = None
    delta: Optional[float] = None
    #: improving | worsening | stable | insufficient_data | trend_only
    assessment: str = "insufficient_data"
    #: up | down | flat | None (raw numeric direction, for metrics without a
    #: clinical "better" direction such as weight)
    direction: Optional[str] = None


class ClinicalTrendsResponse(BaseModel):
    patient_id: int
    metrics: list[MetricTrend] = Field(default_factory=list)
    #: quick roll-up for the clinician banner
    improving: int = 0
    worsening: int = 0
    stable: int = 0
