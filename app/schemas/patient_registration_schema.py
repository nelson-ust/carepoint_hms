# app/schemas/patient_registration_schema.py
from __future__ import annotations

"""
Schemas for the unified registration + visit initiation flow.

This module exposes a single high-level endpoint that handles both:
- new patient registration -> visit initiation
- returning patient lookup by identifier -> visit initiation
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.patient_schemas import PatientCreateSchema


class ReturningPatientLookupSchema(BaseModel):
    """
    Identifiers used to look up a returning patient. The first match wins,
    in this order: hospital_number, national_identifier, phone_number, email.
    """

    hospital_number: Optional[str] = Field(None, max_length=100)
    national_identifier: Optional[str] = Field(None, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=255)

    @model_validator(mode="after")
    def at_least_one_identifier(self):
        if not any([self.hospital_number, self.national_identifier, self.phone_number, self.email]):
            raise ValueError(
                "Provide at least one of: hospital_number, national_identifier, phone_number, email."
            )
        return self


class VisitFlowOptionsSchema(BaseModel):
    """Optional visit initiation parameters carried through the unified flow."""

    appointment_id: Optional[int] = None
    visit_flow_template_id: Optional[int] = None
    visit_flow_template_code: Optional[str] = Field(
        None, description="Resolves a template by code; falls back to settings.DEFAULT_OPD_VISIT_FLOW_TEMPLATE_CODE."
    )
    first_service_delivery_point_id: Optional[int] = None
    use_appointment_service_point: bool = False
    fast_track: bool = False
    priority: Optional[str] = Field(None, description="LOW, NORMAL, HIGH, URGENT, EMERGENCY.")
    visit_reason: Optional[str] = Field(None, max_length=2000)
    visit_date: Optional[datetime] = None
    referred_from: Optional[str] = Field(None, max_length=150)


class UnifiedAdmissionOptionsSchema(BaseModel):
    """
    Inpatient admission payload for the unified entrypoint.

    When this block is supplied, the unified endpoint additionally creates an
    Admission for the new visit, assigns a ward + bed, marks the bed
    OCCUPIED, and captures the first bed-day charge into the visit's billing
    so finance teams see the inpatient bill immediately.
    """

    ward_id: int = Field(..., description="Ward to admit the patient to.")
    bed_id: Optional[int] = Field(
        None,
        description="Optional bed override. If omitted, the first AVAILABLE bed in the ward is used.",
    )
    admitting_staff_id: Optional[int] = None
    admission_reason: Optional[str] = Field(None, max_length=4000)
    expected_discharge_at: Optional[datetime] = None
    admitted_at: Optional[datetime] = Field(
        None,
        description="If omitted, defaults to the visit_date or now.",
    )
    capture_first_bed_day_charge: bool = Field(
        default=True,
        description="If True, immediately captures one bed-day charge against the visit's billing.",
    )


class UnifiedVisitInitiationSchema(BaseModel):
    """
    Single entrypoint for receptionist UIs.

    Branches
    --------
    - ``existing_patient``: lookup by hospital_number / national_id / phone /
      email and route the patient straight into a visit.
    - ``new_patient``: full inline registration payload.

    Inpatient mode
    --------------
    Supply ``admission`` to additionally admit the patient as part of the
    same call. This is the supported path for direct-admission scenarios
    such as ER → ward, scheduled inpatient procedures, and obstetric
    admissions.
    """

    existing_patient: Optional[ReturningPatientLookupSchema] = None
    new_patient: Optional[PatientCreateSchema] = None
    options: VisitFlowOptionsSchema = Field(default_factory=VisitFlowOptionsSchema)
    admission: Optional[UnifiedAdmissionOptionsSchema] = Field(
        None,
        description=(
            "Optional inpatient admission block. When supplied, a ward + bed "
            "are assigned and the first bed-day charge is captured."
        ),
    )

    @model_validator(mode="after")
    def exactly_one_branch(self):
        # The receptionist either looks up a known patient OR registers a new
        # one — never both, never neither.
        if (self.existing_patient is None) == (self.new_patient is None):
            raise ValueError("Provide exactly one of `existing_patient` or `new_patient`.")
        return self


class UnifiedVisitInitiationResponseSchema(BaseModel):
    """
    Response payload for the unified registration + visit-initiation endpoint.

    The admission-related fields are populated only when the request included
    an ``admission`` block (inpatient mode).
    """

    success: bool = True
    message: str
    is_returning_patient: bool
    patient_id: int
    patient_hospital_number: Optional[str] = None
    visit_id: int
    visit_code: str
    queue_ticket_id: Optional[int] = None
    queue_number: Optional[str] = None
    queue_position: Optional[int] = None
    first_service_delivery_point_id: Optional[int] = None
    visit_flow_template_id: Optional[int] = None

    # Inpatient mode — populated only when the request included an admission block.
    admission_id: Optional[int] = None
    admission_no: Optional[str] = None
    admission_status: Optional[str] = None
    ward_id: Optional[int] = None
    bed_id: Optional[int] = None
    bed_day_charges_captured: int = 0
