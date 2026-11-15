# app/schemas/mortuary_schemas.py
from __future__ import annotations

"""
Pydantic schemas for the Mortuary / Morgue management module.

Covers:
- ``MortuaryUnit``   — body-storage units (cold chamber / freezer / shelf)
- ``DeceasedRecord`` — deceased persons, both IN_HOSPITAL and BROUGHT_IN
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

UNIT_TYPES = {"COLD_CHAMBER", "FREEZER", "SHELF", "OTHER"}
UNIT_STATUSES = {"AVAILABLE", "PARTIAL", "FULL", "OUT_OF_SERVICE"}
SOURCES = {"IN_HOSPITAL", "BROUGHT_IN"}


# ============================================================
# STORAGE UNITS
# ============================================================


class MortuaryUnitCreateSchema(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=150)
    unit_type: str = "COLD_CHAMBER"
    capacity: int = Field(1, ge=1, le=1000)
    location: Optional[str] = Field(None, max_length=255)
    temperature_c: Optional[Decimal] = None
    notes: Optional[str] = None

    @field_validator("code")
    @classmethod
    def norm_code(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "-")

    @field_validator("unit_type")
    @classmethod
    def norm_type(cls, v: str) -> str:
        n = (v or "").strip().upper()
        if n not in UNIT_TYPES:
            raise ValueError(f"unit_type must be one of {sorted(UNIT_TYPES)}.")
        return n


class MortuaryUnitUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=150)
    unit_type: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=1, le=1000)
    status: Optional[str] = None
    location: Optional[str] = Field(None, max_length=255)
    temperature_c: Optional[Decimal] = None
    notes: Optional[str] = None

    @field_validator("unit_type")
    @classmethod
    def norm_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        n = v.strip().upper()
        if n not in UNIT_TYPES:
            raise ValueError(f"unit_type must be one of {sorted(UNIT_TYPES)}.")
        return n

    @field_validator("status")
    @classmethod
    def norm_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        n = v.strip().upper()
        if n not in UNIT_STATUSES:
            raise ValueError(f"status must be one of {sorted(UNIT_STATUSES)}.")
        return n


class MortuaryUnitReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    unit_type: str
    capacity: int
    status: str
    location: Optional[str] = None
    temperature_c: Optional[Decimal] = None
    notes: Optional[str] = None
    occupied: int = 0
    available_slots: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MortuaryUnitListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Storage units fetched successfully."
    items: list[MortuaryUnitReadSchema]
    count: int
    meta: dict


class MortuaryUnitActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    unit: MortuaryUnitReadSchema


# ============================================================
# DECEASED RECORDS
# ============================================================


class DeceasedRegisterSchema(BaseModel):
    """Register a deceased person — IN_HOSPITAL (from a patient) or BROUGHT_IN."""

    source: str = "IN_HOSPITAL"

    # IN_HOSPITAL linkage (optional but recommended for in-hospital deaths).
    patient_id: Optional[int] = None
    visit_id: Optional[int] = None
    # When depositing an already-recorded in-hospital death, pass its id; the
    # service copies patient/visit/demographics from it and marks it deposited.
    death_record_id: Optional[int] = None

    # Demographics (name required; others optional — copied from patient when linked).
    deceased_name: str = Field(..., min_length=1, max_length=255)
    gender: Optional[str] = Field(None, max_length=20)
    age_years: Optional[int] = Field(None, ge=0, le=150)
    date_of_death: Optional[datetime] = None
    cause_of_death: Optional[str] = None

    # Brought-in context.
    brought_in_by: Optional[str] = Field(None, max_length=255)
    brought_in_contact: Optional[str] = Field(None, max_length=50)
    from_location: Optional[str] = Field(None, max_length=255)

    # Next of kin.
    next_of_kin_name: Optional[str] = Field(None, max_length=255)
    next_of_kin_phone: Optional[str] = Field(None, max_length=50)
    next_of_kin_relationship: Optional[str] = Field(None, max_length=100)

    # Medico-legal.
    is_police_case: bool = False
    police_reference: Optional[str] = Field(None, max_length=100)

    # Optional immediate storage assignment + receiver.
    mortuary_unit_id: Optional[int] = None
    received_by_staff_id: Optional[int] = None
    tag_number: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None

    @field_validator("source")
    @classmethod
    def norm_source(cls, v: str) -> str:
        n = (v or "").strip().upper()
        if n not in SOURCES:
            raise ValueError(f"source must be one of {sorted(SOURCES)}.")
        return n


class DeceasedUpdateSchema(BaseModel):
    deceased_name: Optional[str] = Field(None, max_length=255)
    gender: Optional[str] = Field(None, max_length=20)
    age_years: Optional[int] = Field(None, ge=0, le=150)
    date_of_death: Optional[datetime] = None
    cause_of_death: Optional[str] = None
    brought_in_by: Optional[str] = Field(None, max_length=255)
    brought_in_contact: Optional[str] = Field(None, max_length=50)
    from_location: Optional[str] = Field(None, max_length=255)
    next_of_kin_name: Optional[str] = Field(None, max_length=255)
    next_of_kin_phone: Optional[str] = Field(None, max_length=50)
    next_of_kin_relationship: Optional[str] = Field(None, max_length=100)
    is_police_case: Optional[bool] = None
    police_reference: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class DeceasedAssignStorageSchema(BaseModel):
    mortuary_unit_id: int
    received_by_staff_id: Optional[int] = None


class MortuaryPaymentInlineSchema(BaseModel):
    amount: Decimal
    method: str = "CASH"
    reference: Optional[str] = Field(None, max_length=100)
    payer_name: Optional[str] = Field(None, max_length=255)
    received_by_staff_id: Optional[int] = None
    notes: Optional[str] = None


class DeceasedReleaseSchema(BaseModel):
    released_to_name: str = Field(..., min_length=1, max_length=255)
    released_to_relationship: Optional[str] = Field(None, max_length=100)
    released_to_contact: Optional[str] = Field(None, max_length=50)
    release_authorized_by: Optional[str] = Field(None, max_length=255)
    released_by_staff_id: Optional[int] = None
    released_at: Optional[datetime] = None
    release_notes: Optional[str] = None
    transfer: bool = Field(False, description="If true, record as TRANSFERRED to another facility instead of RELEASED.")
    # --- settlement (billing / finance) ---
    storage_daily_rate: Optional[Decimal] = Field(None, description="If set, accrue a storage charge for the days held before release.")
    payment: Optional[MortuaryPaymentInlineSchema] = Field(None, description="Payment collected at release to settle the bill.")
    waive_outstanding: bool = Field(False, description="Waive any remaining balance (requires an authoriser).")
    waiver_reason: Optional[str] = Field(None, max_length=255)


class DeceasedReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tag_number: str
    source: str
    status: str
    patient_id: Optional[int] = None
    visit_id: Optional[int] = None
    deceased_name: str
    gender: Optional[str] = None
    age_years: Optional[int] = None
    date_of_death: Optional[datetime] = None
    cause_of_death: Optional[str] = None
    brought_in_by: Optional[str] = None
    brought_in_contact: Optional[str] = None
    from_location: Optional[str] = None
    next_of_kin_name: Optional[str] = None
    next_of_kin_phone: Optional[str] = None
    next_of_kin_relationship: Optional[str] = None
    is_police_case: bool = False
    police_reference: Optional[str] = None
    mortuary_unit_id: Optional[int] = None
    mortuary_unit_name: Optional[str] = None
    received_by_staff_id: Optional[int] = None
    registered_at: Optional[datetime] = None
    released_to_name: Optional[str] = None
    released_to_relationship: Optional[str] = None
    released_to_contact: Optional[str] = None
    release_authorized_by: Optional[str] = None
    released_by_staff_id: Optional[int] = None
    released_at: Optional[datetime] = None
    release_notes: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DeceasedListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Deceased records fetched successfully."
    items: list[DeceasedReadSchema]
    count: int
    meta: dict


class DeceasedActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    record: DeceasedReadSchema


class MortuaryStatsResponseSchema(BaseModel):
    success: bool = True
    message: str = "Mortuary statistics computed successfully."
    in_storage: int
    registered: int
    released: int
    in_hospital_total: int
    brought_in_total: int
    police_cases: int
    units_total: int
    capacity_total: int
    occupied_total: int
    by_status: dict[str, int] = Field(default_factory=dict)


# ============================================================
# PATIENT DEATH RECORDS (clinical declaration -> mortuary intake)
# ============================================================


class DeathRecordCreateSchema(BaseModel):
    """Record that a patient has died, against the visit where declared dead."""

    patient_id: int
    visit_id: int
    date_of_death: datetime
    cause_of_death: Optional[str] = None
    place_of_death: Optional[str] = Field("Hospital", max_length=255)
    declared_by_staff_id: Optional[int] = None
    notes: Optional[str] = None

    # Optional immediate mortuary deposit.
    deposit_to_mortuary: bool = False
    mortuary_unit_id: Optional[int] = None
    next_of_kin_name: Optional[str] = Field(None, max_length=255)
    next_of_kin_phone: Optional[str] = Field(None, max_length=50)
    next_of_kin_relationship: Optional[str] = Field(None, max_length=100)
    is_police_case: bool = False
    police_reference: Optional[str] = Field(None, max_length=100)
    tag_number: Optional[str] = Field(None, max_length=50)


class DeathRecordReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    visit_id: int
    patient_name: Optional[str] = None
    hospital_number: Optional[str] = None
    visit_code: Optional[str] = None
    date_of_death: Optional[datetime] = None
    cause_of_death: Optional[str] = None
    place_of_death: Optional[str] = None
    declared_by_staff_id: Optional[int] = None
    notes: Optional[str] = None
    is_deposited: bool = False
    deceased_record_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DeathRecordActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    death: DeathRecordReadSchema
    record: Optional[DeceasedReadSchema] = None  # present when deposited


class DeathRecordListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Death records fetched successfully."
    items: list[DeathRecordReadSchema]
    count: int
    meta: dict


# ============================================================
# STANDARD MORTUARY OPERATIONS (autopsy, embalming, effects, viewings,
# charges/billing, death certificate)
# ============================================================


class AutopsyCreateSchema(BaseModel):
    autopsy_type: str = "CLINICAL"
    requested_by: Optional[str] = Field(None, max_length=255)
    pathologist: Optional[str] = Field(None, max_length=255)
    scheduled_at: Optional[datetime] = None
    consent_by: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class AutopsyUpdateSchema(BaseModel):
    status: Optional[str] = None
    pathologist: Optional[str] = Field(None, max_length=255)
    scheduled_at: Optional[datetime] = None
    performed_at: Optional[datetime] = None
    findings: Optional[str] = None
    cause_of_death_confirmed: Optional[str] = None
    notes: Optional[str] = None


class AutopsyReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    deceased_record_id: int
    autopsy_type: str
    status: str
    requested_by: Optional[str] = None
    pathologist: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    performed_at: Optional[datetime] = None
    findings: Optional[str] = None
    cause_of_death_confirmed: Optional[str] = None
    consent_by: Optional[str] = None
    notes: Optional[str] = None
    deceased_name: Optional[str] = None
    tag_number: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EmbalmingCreateSchema(BaseModel):
    embalmer_name: Optional[str] = Field(None, max_length=255)
    method: Optional[str] = Field(None, max_length=255)
    chemicals_used: Optional[str] = None
    embalmed_at: Optional[datetime] = None
    mark_completed: bool = False
    notes: Optional[str] = None


class EmbalmingReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    deceased_record_id: int
    status: str
    embalmer_name: Optional[str] = None
    method: Optional[str] = None
    chemicals_used: Optional[str] = None
    embalmed_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EffectCreateSchema(BaseModel):
    item: str = Field(..., min_length=1, max_length=255)
    quantity: int = Field(1, ge=1)
    description: Optional[str] = None
    received_from: Optional[str] = Field(None, max_length=255)


class EffectReleaseSchema(BaseModel):
    released_to: str = Field(..., min_length=1, max_length=255)


class EffectReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    deceased_record_id: int
    status: str
    item: str
    quantity: int
    description: Optional[str] = None
    received_from: Optional[str] = None
    received_at: Optional[datetime] = None
    released_to: Optional[str] = None
    released_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ViewingCreateSchema(BaseModel):
    visitor_name: str = Field(..., min_length=1, max_length=255)
    relationship_to_deceased: Optional[str] = Field(None, max_length=100)
    contact: Optional[str] = Field(None, max_length=50)
    viewed_at: Optional[datetime] = None
    authorized_by: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class ViewingReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    deceased_record_id: int
    visitor_name: str
    relationship_to_deceased: Optional[str] = None
    contact: Optional[str] = None
    viewed_at: Optional[datetime] = None
    authorized_by: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class ChargeCreateSchema(BaseModel):
    charge_type: str = "OTHER"
    description: Optional[str] = Field(None, max_length=255)
    quantity: Decimal = Decimal("1")
    unit_amount: Decimal = Decimal("0")
    notes: Optional[str] = None


class ChargeStatusSchema(BaseModel):
    status: str  # PAID or WAIVED


class ChargeReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    deceased_record_id: int
    charge_type: str
    status: str
    description: Optional[str] = None
    quantity: Decimal
    unit_amount: Decimal
    amount: Decimal
    charged_at: Optional[datetime] = None
    notes: Optional[str] = None
    deceased_name: Optional[str] = None
    tag_number: Optional[str] = None
    created_at: Optional[datetime] = None


class CertificateCreateSchema(BaseModel):
    issued_by: Optional[str] = Field(None, max_length=255)
    certifying_doctor: Optional[str] = Field(None, max_length=255)
    cause_of_death: Optional[str] = None
    manner_of_death: Optional[str] = Field(None, max_length=100)
    place_of_death: Optional[str] = Field(None, max_length=255)
    certificate_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class CertificateReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    deceased_record_id: int
    certificate_number: str
    issued_by: Optional[str] = None
    certifying_doctor: Optional[str] = None
    issued_at: Optional[datetime] = None
    cause_of_death: Optional[str] = None
    manner_of_death: Optional[str] = None
    place_of_death: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class SimpleListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Fetched successfully."
    items: list[dict]
    count: int
    meta: dict


class SimpleActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    data: dict


class MortuaryAnalyticsResponseSchema(BaseModel):
    success: bool = True
    message: str = "Mortuary analytics computed successfully."
    summary: dict
    source_split: list[dict]
    status_breakdown: list[dict]
    intake_trend: list[dict]
    unit_utilization: list[dict]
    los_buckets: list[dict]
    long_stay: list[dict]
    autopsy: dict
    billing: dict
    top_causes: list[dict]



class MortuaryPaymentCreateSchema(BaseModel):
    amount: Decimal = Field(..., gt=0)
    method: str = "CASH"
    reference: Optional[str] = Field(None, max_length=100)
    payer_name: Optional[str] = Field(None, max_length=255)
    received_by_staff_id: Optional[int] = None
    notes: Optional[str] = None


class StorageAccrualSchema(BaseModel):
    daily_rate: Decimal = Field(..., ge=0)


class MortuaryPaymentReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    deceased_record_id: int
    amount: Decimal
    method: str
    reference: Optional[str] = None
    payer_name: Optional[str] = None
    received_by_staff_id: Optional[int] = None
    paid_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class MortuaryBillSummarySchema(BaseModel):
    success: bool = True
    message: str = "Billing summary computed."
    deceased_record_id: int
    total_billed: str
    total_paid: str
    waived: str
    outstanding: str
    days_in_storage: int
    charges: list[dict]
    payments: list[dict]
