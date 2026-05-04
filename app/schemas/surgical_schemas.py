# app/schemas/surgical_schemas.py
from __future__ import annotations

"""
Pydantic schemas for the Surgical / Theatre module.

Covers the full operational surface:
- ``OperatingTheatre``        — physical theatres
- ``SurgicalProcedureCatalog`` — master surgical-procedure list
- ``SurgicalCase``            — booked / scheduled / performed surgeries
- ``SurgicalTeamMember``      — primary surgeon, assistants, anaesthetist, ...
- ``SurgicalConsent``         — patient consent at booking / pre-op
- ``SurgicalSafetyChecklist`` — WHO sign-in / time-out / sign-out
- ``AnaesthesiaRecord``       — anaesthesia agents + monitoring snapshot
- ``TheatreNote``             — intra-op notes
- ``SurgicalInstrumentSet``   — instrument sets used + sterilisation
- ``InstrumentSterilizationLog`` — per-cycle sterilisation audit
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================
# OPERATING THEATRE
# ============================================================


class OperatingTheatreCreateSchema(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=150)
    facility_id: Optional[int] = None
    location_description: Optional[str] = Field(None, max_length=255)
    is_emergency_capable: bool = False
    capabilities: Optional[dict[str, Any]] = None
    notes: Optional[str] = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "_")


class OperatingTheatreUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    location_description: Optional[str] = Field(None, max_length=255)
    is_emergency_capable: Optional[bool] = None
    capabilities: Optional[dict[str, Any]] = None
    notes: Optional[str] = None


class OperatingTheatreStatusSchema(BaseModel):
    new_status: str
    reason: Optional[str] = Field(None, max_length=2000)

    @field_validator("new_status")
    @classmethod
    def normalize_status(cls, v: str) -> str:
        normalized = v.strip().upper()
        allowed = {"AVAILABLE", "OCCUPIED", "CLEANING", "OUT_OF_SERVICE", "UNDER_MAINTENANCE"}
        if normalized not in allowed:
            raise ValueError(f"new_status must be one of {sorted(allowed)}.")
        return normalized


class OperatingTheatreReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    facility_id: Optional[int] = None
    location_description: Optional[str] = None
    status: str
    is_emergency_capable: bool = False
    capabilities: Optional[dict[str, Any]] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class OperatingTheatreListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Operating theatres fetched successfully."
    items: list[OperatingTheatreReadSchema]
    count: int
    meta: dict


class OperatingTheatreActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    theatre: OperatingTheatreReadSchema


# ============================================================
# SURGICAL PROCEDURE CATALOG
# ============================================================


class SurgicalProcedureCatalogCreateSchema(BaseModel):
    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    cpt_code: Optional[str] = Field(None, max_length=50)
    typical_duration_minutes: Optional[int] = None
    requires_blood_products: bool = False
    average_blood_loss_ml: Optional[int] = None
    default_price: Optional[Decimal] = None
    description: Optional[str] = None
    pre_op_instructions: Optional[str] = None
    post_op_instructions: Optional[str] = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "_")


class SurgicalProcedureCatalogReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    cpt_code: Optional[str] = None
    typical_duration_minutes: Optional[int] = None
    requires_blood_products: bool = False
    average_blood_loss_ml: Optional[int] = None
    default_price: Optional[Decimal] = None
    description: Optional[str] = None
    pre_op_instructions: Optional[str] = None
    post_op_instructions: Optional[str] = None


class SurgicalProcedureCatalogListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Surgical procedures fetched successfully."
    items: list[SurgicalProcedureCatalogReadSchema]
    count: int
    meta: dict


class SurgicalProcedureCatalogActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    procedure: SurgicalProcedureCatalogReadSchema


# ============================================================
# SURGICAL CASE
# ============================================================


class SurgicalCaseBookSchema(BaseModel):
    """Book a new surgical case."""

    patient_id: int
    procedure_catalog_id: int
    visit_id: Optional[int] = None
    facility_id: Optional[int] = None
    operating_theatre_id: Optional[int] = None
    is_emergency: bool = False
    asa_class: Optional[str] = Field(None, description="ASA_I..ASA_VI")
    anaesthesia_type: Optional[str] = Field(
        None, description="GENERAL, SPINAL, EPIDURAL, REGIONAL, LOCAL, SEDATION, NONE"
    )
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None
    diagnosis_text: Optional[str] = None
    auto_capture_charge: bool = True

    @field_validator("asa_class")
    @classmethod
    def normalize_asa(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip().upper()
        allowed = {"ASA_I", "ASA_II", "ASA_III", "ASA_IV", "ASA_V", "ASA_VI"}
        if normalized not in allowed:
            raise ValueError(f"asa_class must be one of {sorted(allowed)}.")
        return normalized

    @field_validator("anaesthesia_type")
    @classmethod
    def normalize_anaesthesia(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip().upper()
        allowed = {"GENERAL", "SPINAL", "EPIDURAL", "REGIONAL", "LOCAL", "SEDATION", "NONE"}
        if normalized not in allowed:
            raise ValueError(f"anaesthesia_type must be one of {sorted(allowed)}.")
        return normalized


class SurgicalCaseTransitionSchema(BaseModel):
    """Generic transition payload for status changes (start, end, cancel, etc.)."""

    note: Optional[str] = Field(None, max_length=4000)
    findings: Optional[str] = Field(None, max_length=8000)


class SurgicalCaseReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_no: str
    patient_id: int
    visit_id: Optional[int] = None
    facility_id: Optional[int] = None
    procedure_catalog_id: int
    operating_theatre_id: Optional[int] = None
    status: str
    is_emergency: bool = False
    asa_class: Optional[str] = None
    anaesthesia_type: Optional[str] = None
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None
    pre_op_started_at: Optional[datetime] = None
    incision_at: Optional[datetime] = None
    closure_at: Optional[datetime] = None
    out_of_theatre_at: Optional[datetime] = None
    diagnosis_text: Optional[str] = None
    findings_text: Optional[str] = None
    cancellation_reason: Optional[str] = None
    created_at: Optional[datetime] = None


class SurgicalCaseListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Surgical cases fetched successfully."
    items: list[SurgicalCaseReadSchema]
    count: int
    meta: dict


class SurgicalCaseActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    case: SurgicalCaseReadSchema


# ============================================================
# TEAM MEMBER
# ============================================================


class SurgicalTeamMemberAddSchema(BaseModel):
    surgical_case_id: int
    staff_profile_id: int
    role: str
    is_lead: bool = False
    notes: Optional[str] = None

    @field_validator("role")
    @classmethod
    def normalize_role(cls, v: str) -> str:
        normalized = v.strip().upper()
        allowed = {
            "PRIMARY_SURGEON", "ASSISTANT_SURGEON", "ANAESTHETIST",
            "SCRUB_NURSE", "CIRCULATING_NURSE", "PERFUSIONIST",
            "OBSERVER", "OTHER",
        }
        if normalized not in allowed:
            raise ValueError(f"role must be one of {sorted(allowed)}.")
        return normalized


class SurgicalTeamMemberReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    surgical_case_id: int
    staff_profile_id: int
    role: str
    is_lead: bool = False
    notes: Optional[str] = None


class SurgicalTeamMemberActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    member: SurgicalTeamMemberReadSchema


# ============================================================
# CONSENT
# ============================================================


class SurgicalConsentCreateSchema(BaseModel):
    surgical_case_id: int
    consent_text: str = Field(..., min_length=1)
    consent_signed_by: Optional[str] = Field(None, max_length=200)
    relationship_to_patient: Optional[str] = Field(None, max_length=100)
    witnessed_by_staff_id: Optional[int] = None
    signed_at: Optional[datetime] = None
    signature_image_url: Optional[str] = None


class SurgicalConsentReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    surgical_case_id: int
    consent_text: str
    consent_signed_by: Optional[str] = None
    relationship_to_patient: Optional[str] = None
    witnessed_by_staff_id: Optional[int] = None
    signed_at: datetime
    signature_image_url: Optional[str] = None


class SurgicalConsentActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    consent: SurgicalConsentReadSchema


# ============================================================
# SAFETY CHECKLIST
# ============================================================


class SurgicalChecklistRecordSchema(BaseModel):
    surgical_case_id: int
    phase: str
    items: Optional[dict[str, Any]] = None
    completed_by_staff_id: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("phase")
    @classmethod
    def normalize_phase(cls, v: str) -> str:
        normalized = v.strip().upper()
        allowed = {"SIGN_IN", "TIME_OUT", "SIGN_OUT"}
        if normalized not in allowed:
            raise ValueError(f"phase must be one of {sorted(allowed)}.")
        return normalized


class SurgicalChecklistReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    surgical_case_id: int
    phase: str
    completed_at: datetime
    completed_by_staff_id: Optional[int] = None
    items: Optional[dict[str, Any]] = None
    notes: Optional[str] = None


class SurgicalChecklistActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    checklist: SurgicalChecklistReadSchema


# ============================================================
# ANAESTHESIA
# ============================================================


class AnaesthesiaRecordCreateSchema(BaseModel):
    surgical_case_id: int
    anaesthetist_staff_id: Optional[int] = None
    anaesthesia_type: str
    induction_time: Optional[datetime] = None
    emergence_time: Optional[datetime] = None
    agents: Optional[dict[str, Any]] = None
    monitoring_intervals: Optional[dict[str, Any]] = None
    complications: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("anaesthesia_type")
    @classmethod
    def normalize_anaesthesia(cls, v: str) -> str:
        normalized = v.strip().upper()
        allowed = {"GENERAL", "SPINAL", "EPIDURAL", "REGIONAL", "LOCAL", "SEDATION", "NONE"}
        if normalized not in allowed:
            raise ValueError(f"anaesthesia_type must be one of {sorted(allowed)}.")
        return normalized


class AnaesthesiaRecordReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    surgical_case_id: int
    anaesthetist_staff_id: Optional[int] = None
    anaesthesia_type: str
    induction_time: Optional[datetime] = None
    emergence_time: Optional[datetime] = None
    agents: Optional[dict[str, Any]] = None
    monitoring_intervals: Optional[dict[str, Any]] = None
    complications: Optional[str] = None
    notes: Optional[str] = None


class AnaesthesiaRecordActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    record: AnaesthesiaRecordReadSchema


# ============================================================
# THEATRE NOTE
# ============================================================


class TheatreNoteCreateSchema(BaseModel):
    surgical_case_id: int
    note: str = Field(..., min_length=1)
    note_type: Optional[str] = Field(None, max_length=50)
    author_staff_id: Optional[int] = None
    captured_at: Optional[datetime] = None


class TheatreNoteReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    surgical_case_id: int
    author_staff_id: Optional[int] = None
    note_type: Optional[str] = None
    note: str
    captured_at: datetime


class TheatreNoteActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    theatre_note: TheatreNoteReadSchema


# ============================================================
# INSTRUMENT SET
# ============================================================


class SurgicalInstrumentSetCreateSchema(BaseModel):
    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    facility_id: Optional[int] = None
    contents: Optional[dict[str, Any]] = None
    notes: Optional[str] = None


class SurgicalInstrumentSetAssignSchema(BaseModel):
    surgical_case_id: int


class SurgicalInstrumentSetReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    facility_id: Optional[int] = None
    surgical_case_id: Optional[int] = None
    sterilization_status: str
    last_autoclaved_at: Optional[datetime] = None
    next_required_sterilization_at: Optional[datetime] = None
    contents: Optional[dict[str, Any]] = None
    notes: Optional[str] = None


class InstrumentSterilizationLogCreateSchema(BaseModel):
    instrument_set_id: int
    performed_by_staff_id: Optional[int] = None
    cycle_started_at: datetime
    cycle_ended_at: Optional[datetime] = None
    method: Optional[str] = Field(None, max_length=100)
    machine_identifier: Optional[str] = Field(None, max_length=150)
    indicator_passed: Optional[bool] = None
    notes: Optional[str] = None


class InstrumentSterilizationLogReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    instrument_set_id: int
    performed_by_staff_id: Optional[int] = None
    cycle_started_at: datetime
    cycle_ended_at: Optional[datetime] = None
    method: Optional[str] = None
    machine_identifier: Optional[str] = None
    indicator_passed: Optional[bool] = None
    notes: Optional[str] = None


class SurgicalInstrumentSetActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    instrument_set: SurgicalInstrumentSetReadSchema


class InstrumentSterilizationLogActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    log: InstrumentSterilizationLogReadSchema
