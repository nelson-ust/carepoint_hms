# app/schemas/admission_schemas.py
from __future__ import annotations

"""
Pydantic schemas for the inpatient admission workflow.

Scope
-----
This module defines the request and response shapes used by:

- ``app/services/admission_service.py``  — admission lifecycle orchestration
- ``app/api/v1/endpoints/admission_routes.py`` — FastAPI endpoints
- ``app/services/patient_registration_service.py`` — unified
  registration + visit + admission flow

Lifecycle reflected by the schemas
----------------------------------
PENDING -> ADMITTED -> (TRANSFERRED, ADMITTED, ...) -> DISCHARGED
                                                   `-> CANCELLED
                                                   `-> DECEASED

Each request schema includes only the fields that are valid in the
corresponding state transition. Read schemas mirror the ``Admission`` ORM
columns plus a few derived fields (e.g., ``length_of_stay_days``).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================
# REQUEST SCHEMAS
# ============================================================


class AdmissionCreateSchema(BaseModel):
    """
    Schema used to create an admission row.

    Notes
    -----
    - ``visit_id`` is optional but strongly recommended; it ties the inpatient
      stay to its outpatient encounter for billing roll-up.
    - ``ward_id`` and ``bed_id`` may be supplied at admit time. When
      ``bed_id`` is supplied, it must belong to ``ward_id``.
    - ``capture_first_bed_day_charge`` defaults to True so the first night's
      bed-day fee is captured into the visit's open billing immediately.
    """

    patient_id: int
    visit_id: Optional[int] = None
    ward_id: int
    bed_id: Optional[int] = Field(
        None,
        description="If omitted, the admission service auto-picks the first AVAILABLE bed in the ward.",
    )
    admitting_staff_id: Optional[int] = None

    admission_reason: Optional[str] = Field(None, max_length=4000)
    admitted_at: Optional[datetime] = Field(
        None,
        description="Defaults to now if not supplied.",
    )
    expected_discharge_at: Optional[datetime] = None

    is_emergency: bool = Field(
        default=False,
        description=(
            "Emergency admission. When True the visit bypasses the "
            "doctor-recommendation requirement (life-threatening / ER cases). "
            "Audited."
        ),
    )

    capture_first_bed_day_charge: bool = Field(
        default=True,
        description="If True, immediately captures one bed-day charge against the visit's billing.",
    )


class AdmissionFromVisitConvertSchema(BaseModel):
    """
    Convert an in-progress ER / OPD visit into an inpatient admission in
    one call. Reuses the same visit (so the OPD bill rolls forward into
    the inpatient bill) and books a bed.
    """

    visit_id: int = Field(..., description="The ER / OPD visit being converted.")
    ward_id: int
    bed_id: Optional[int] = Field(
        None,
        description=(
            "If omitted, the admission service auto-picks the first AVAILABLE bed."
        ),
    )
    admitting_staff_id: Optional[int] = None
    admission_reason: Optional[str] = Field(None, max_length=4000)
    expected_discharge_at: Optional[datetime] = None
    is_emergency: bool = Field(
        default=False,
        description="Emergency admission; bypasses the doctor-recommendation requirement.",
    )
    capture_first_bed_day_charge: bool = True
    route_to_service_delivery_point_id: Optional[int] = Field(
        None,
        description=(
            "If supplied, route the visit to this SDP (typically the ward / "
            "inpatient SDP) so the visit-flow timeline reflects the move."
        ),
    )


class AdmissionTransferBedSchema(BaseModel):
    """
    Move an admitted patient to a new bed (potentially in a different ward).

    The service marks the old bed AVAILABLE and the new bed OCCUPIED.
    A ``BED_TRANSFER`` security event is emitted with the old/new IDs.
    """

    new_bed_id: int
    new_ward_id: Optional[int] = Field(
        None,
        description="If omitted, the service infers the ward from the bed.",
    )
    reason: Optional[str] = Field(None, max_length=2000)


class AdmissionStatusUpdateSchema(BaseModel):
    """
    Mark an admission as CANCELLED or DECEASED.
    Use ``DischargeCreateSchema`` for the normal discharged path.
    """

    new_status: str = Field(..., description="One of CANCELLED, DECEASED.")
    reason: Optional[str] = Field(None, max_length=2000)

    @field_validator("new_status")
    @classmethod
    def normalize_status(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"CANCELLED", "DECEASED"}:
            raise ValueError("new_status must be one of CANCELLED, DECEASED.")
        return normalized


class AdmissionBedDayCaptureSchema(BaseModel):
    """
    Capture all uncaptured bed-day charges for an admission up to a date.

    Used by:
    - The nightly bed-day rollover job.
    - Cashier "settle inpatient bill" flows that need an up-to-the-minute view.
    """

    through_date: date = Field(
        ...,
        description="Inclusive end-date for which bed-day charges should be captured.",
    )


# ============================================================
# RESPONSE SCHEMAS
# ============================================================


class AdmissionReadSchema(BaseModel):
    """Detailed admission record returned by API endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    admission_no: str
    patient_id: int
    visit_id: Optional[int] = None
    ward_id: Optional[int] = None
    bed_id: Optional[int] = None
    admitted_by_staff_id: Optional[int] = None
    admission_status: str
    admission_reason: Optional[str] = None
    admitted_at: Optional[datetime] = None
    expected_discharge_at: Optional[datetime] = None
    actual_discharge_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AdmissionListResponseSchema(BaseModel):
    """Paginated admission list response."""

    success: bool = True
    message: str = "Admissions fetched successfully."
    items: list[AdmissionReadSchema]
    count: int
    meta: dict


class AdmissionActionResponseSchema(BaseModel):
    """Wraps the affected admission for action endpoints."""

    success: bool = True
    message: str
    admission: AdmissionReadSchema


class AdmissionBedDayCaptureResponseSchema(BaseModel):
    """
    Returned when the bed-day rollover runs.

    ``charges_captured`` is the count of NEW billing items this run inserted
    (existing ones are skipped due to the source-reference idempotency key).
    """

    success: bool = True
    message: str = "Bed-day charges captured successfully."
    admission_id: int
    charges_captured: int
    total_amount_captured: Decimal
    captured_through: date
