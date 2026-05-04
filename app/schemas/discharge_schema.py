# app/schemas/discharge_schema.py
from __future__ import annotations

"""
Pydantic schemas for the inpatient discharge workflow.

Discharge process expressed in these schemas
--------------------------------------------
1. The clinician submits :class:`DischargeCreateSchema`.
2. The service captures any outstanding bed-day charges through the
   discharge date (so finance has a complete bill).
3. The service marks the bed AVAILABLE and the admission DISCHARGED.
4. If the admission was the visit's last open clinical event, the visit is
   moved to COMPLETED via the visit-routing helper.
5. A discharge summary record (``Discharge``) is persisted alongside the
   admission for clinical-record continuity.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DischargeCreateSchema(BaseModel):
    """Submit a discharge for an existing admission."""

    admission_id: int
    discharged_by_staff_id: Optional[int] = None
    discharge_date: Optional[datetime] = Field(
        None,
        description="Defaults to now (UTC) if not provided.",
    )
    discharge_condition: Optional[str] = Field(None, max_length=255)
    discharge_summary: Optional[str] = Field(None, max_length=8000)
    follow_up_instruction: Optional[str] = Field(None, max_length=4000)

    capture_final_bed_day_charges: bool = Field(
        default=True,
        description=(
            "If True, captures any outstanding bed-day charges up to the "
            "discharge date before the admission is closed."
        ),
    )
    end_visit_if_only_open_event: bool = Field(
        default=True,
        description=(
            "If True, marks the visit COMPLETED when the discharge closes the "
            "last open clinical event on it."
        ),
    )
    force: bool = Field(
        default=False,
        description=(
            "If True, bypass discharge-readiness checks (open lab orders, "
            "undispensed prescriptions, open theatre cases). Reserved for "
            "supervisors / against-medical-advice discharges."
        ),
    )


class DischargeReadSchema(BaseModel):
    """Discharge record returned by API endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    admission_id: int
    discharged_by_staff_id: Optional[int] = None
    discharge_date: datetime
    discharge_condition: Optional[str] = None
    discharge_summary: Optional[str] = None
    follow_up_instruction: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DischargeActionResponseSchema(BaseModel):
    """Action-style wrapper that also includes the closed admission summary."""

    success: bool = True
    message: str
    discharge: DischargeReadSchema
    admission_id: int
    bed_day_charges_captured: int = 0
    visit_completed: bool = False
