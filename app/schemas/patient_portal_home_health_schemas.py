# app/schemas/patient_portal_home_health_schemas.py
from __future__ import annotations

"""Patient-facing (portal) Home Health schemas — a patient sees and submits
only their own data. Clinical actions remain staff-only."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.core.enums import MonitoringReadingType


class PortalReadingSubmitSchema(BaseModel):
    """A self-measured reading submitted by the patient from the portal."""

    reading_type: MonitoringReadingType
    primary_value: Optional[Decimal] = None
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    unit: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _check(self):
        if self.reading_type == MonitoringReadingType.BLOOD_PRESSURE:
            if self.systolic is None or self.diastolic is None:
                raise ValueError("Blood pressure needs both systolic and diastolic.")
        elif self.primary_value is None:
            raise ValueError("A value is required.")
        return self


class PortalVisitRequestSchema(BaseModel):
    """A patient's request for a home visit (created as REQUESTED for triage)."""

    reason: str = Field(min_length=3)
    preferred_date: Optional[datetime] = None
    address: Optional[str] = None
    phone_number: Optional[str] = None


class PortalHomeHealthSummarySchema(BaseModel):
    success: bool = True
    has_active_care_plan: bool = False
    care_plan_title: Optional[str] = None
    upcoming_visit_count: int = 0
    next_visit_at: Optional[datetime] = None
    open_task_count: int = 0
    readings_last_7d: int = 0
