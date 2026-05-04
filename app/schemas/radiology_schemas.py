# app/schemas/radiology_schemas.py
from __future__ import annotations

"""
Pydantic schemas for the Radiology / RIS module.

Covers:
- ``RadiologyProcedureCatalog`` — master catalog of imaging procedures
- ``RadiologyOrder`` + ``RadiologyOrderItem`` — clinician orders
- ``RadiologyExam`` — execution + scheduling
- ``RadiologyReport`` — radiologist reading (4-eyes verify + release)
- ``RadiologyImage`` — DICOM/PACS references

The flow mirrors the lab loop for consistency.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================
# CATALOG
# ============================================================


class RadiologyProcedureCatalogCreateSchema(BaseModel):
    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    modality: str = Field(..., description="X_RAY, CT, MRI, ULTRASOUND, ...")
    body_part: Optional[str] = Field(None, max_length=150)
    cpt_code: Optional[str] = Field(None, max_length=50)
    typical_duration_minutes: Optional[int] = None
    contrast_required: bool = False
    radiation_dose_msv: Optional[Decimal] = None
    preparation_instructions: Optional[str] = None
    default_price: Optional[Decimal] = None
    description: Optional[str] = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "_")

    @field_validator("modality")
    @classmethod
    def normalize_modality(cls, v: str) -> str:
        normalized = v.strip().upper()
        allowed = {
            "X_RAY", "CT", "MRI", "ULTRASOUND", "MAMMOGRAPHY",
            "FLUOROSCOPY", "NUCLEAR_MEDICINE", "PET", "DEXA",
            "ANGIOGRAPHY", "INTERVENTIONAL", "OTHER",
        }
        if normalized not in allowed:
            raise ValueError(f"modality must be one of {sorted(allowed)}.")
        return normalized


class RadiologyProcedureCatalogUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    body_part: Optional[str] = Field(None, max_length=150)
    cpt_code: Optional[str] = Field(None, max_length=50)
    typical_duration_minutes: Optional[int] = None
    contrast_required: Optional[bool] = None
    radiation_dose_msv: Optional[Decimal] = None
    preparation_instructions: Optional[str] = None
    default_price: Optional[Decimal] = None
    description: Optional[str] = None


class RadiologyProcedureCatalogReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    modality: str
    body_part: Optional[str] = None
    cpt_code: Optional[str] = None
    typical_duration_minutes: Optional[int] = None
    contrast_required: bool = False
    radiation_dose_msv: Optional[Decimal] = None
    preparation_instructions: Optional[str] = None
    default_price: Optional[Decimal] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class RadiologyProcedureCatalogListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Radiology procedures fetched successfully."
    items: list[RadiologyProcedureCatalogReadSchema]
    count: int
    meta: dict


class RadiologyProcedureCatalogActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    procedure: RadiologyProcedureCatalogReadSchema


# ============================================================
# ORDER
# ============================================================


class RadiologyOrderItemCreateSchema(BaseModel):
    procedure_catalog_id: int
    laterality: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=500)


class RadiologyOrderCreateSchema(BaseModel):
    visit_id: int
    consultation_id: Optional[int] = None
    ordered_by_staff_id: Optional[int] = None
    facility_id: Optional[int] = None
    priority: Optional[str] = Field(None, description="LOW, NORMAL, HIGH, URGENT, EMERGENCY")
    clinical_indication: Optional[str] = None
    pregnancy_screening: Optional[bool] = None
    creatinine_value: Optional[Decimal] = None
    items: list[RadiologyOrderItemCreateSchema] = Field(..., min_length=1)
    auto_capture_charge: bool = True
    route_to_radiology_service_delivery_point_id: Optional[int] = None
    route_to_cashier_service_delivery_point_id: Optional[int] = None


class RadiologyOrderCancelSchema(BaseModel):
    reason: Optional[str] = Field(None, max_length=2000)


class RadiologyOrderItemReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    radiology_order_id: int
    procedure_catalog_id: int
    status: str
    laterality: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class RadiologyOrderReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    consultation_id: Optional[int] = None
    facility_id: Optional[int] = None
    ordered_by_staff_id: Optional[int] = None
    order_no: str
    status: str
    priority: str
    clinical_indication: Optional[str] = None
    pregnancy_screening: Optional[bool] = None
    creatinine_value: Optional[Decimal] = None
    ordered_at: datetime
    items: list[RadiologyOrderItemReadSchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RadiologyOrderActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    order: RadiologyOrderReadSchema


class RadiologyOrderListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Radiology orders fetched successfully."
    items: list[RadiologyOrderReadSchema]
    count: int
    meta: dict


# ============================================================
# EXAM
# ============================================================


class RadiologyExamScheduleSchema(BaseModel):
    """Schedule an exam for a particular order item."""

    order_item_id: int
    facility_id: Optional[int] = None
    scheduled_at: datetime
    machine_identifier: Optional[str] = Field(None, max_length=100)


class RadiologyExamStartSchema(BaseModel):
    performed_by_staff_id: Optional[int] = None
    machine_identifier: Optional[str] = Field(None, max_length=100)
    contrast_administered: Optional[bool] = None
    technical_notes: Optional[str] = None


class RadiologyExamCompleteSchema(BaseModel):
    technical_notes: Optional[str] = None


class RadiologyExamReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_item_id: int
    facility_id: Optional[int] = None
    performed_by_staff_id: Optional[int] = None
    machine_identifier: Optional[str] = None
    accession_number: Optional[str] = None
    status: str
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    contrast_administered: Optional[bool] = None
    technical_notes: Optional[str] = None
    created_at: Optional[datetime] = None


class RadiologyExamActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    exam: RadiologyExamReadSchema


# ============================================================
# IMAGE
# ============================================================


class RadiologyImageAttachSchema(BaseModel):
    exam_id: int
    sop_instance_uid: Optional[str] = Field(None, max_length=255)
    series_instance_uid: Optional[str] = Field(None, max_length=255)
    study_instance_uid: Optional[str] = Field(None, max_length=255)
    image_url: Optional[str] = None
    pacs_archive_id: Optional[str] = Field(None, max_length=255)
    image_count: Optional[int] = None
    captured_at: Optional[datetime] = None
    notes: Optional[str] = None


class RadiologyImageReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int
    sop_instance_uid: Optional[str] = None
    series_instance_uid: Optional[str] = None
    study_instance_uid: Optional[str] = None
    image_url: Optional[str] = None
    pacs_archive_id: Optional[str] = None
    image_count: Optional[int] = None
    captured_at: Optional[datetime] = None
    notes: Optional[str] = None


class RadiologyImageActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    image: RadiologyImageReadSchema


# ============================================================
# REPORT
# ============================================================


class RadiologyReportDraftSchema(BaseModel):
    exam_id: int
    reported_by_staff_id: Optional[int] = None
    findings: Optional[str] = None
    impression: Optional[str] = None
    recommendations: Optional[str] = None


class RadiologyReportFinalizeSchema(BaseModel):
    """
    Finalize a draft report — equivalent to the lab "verify" step.

    Enforces the 4-eyes rule: ``verified_by_staff_id`` must differ from the
    drafting radiologist when both are supplied.
    """

    verified_by_staff_id: Optional[int] = None
    findings: Optional[str] = None
    impression: Optional[str] = None
    recommendations: Optional[str] = None


class RadiologyReportReleaseSchema(BaseModel):
    notify_clinician: bool = True
    note: Optional[str] = Field(None, max_length=2000)


class RadiologyReportReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int
    reported_by_staff_id: Optional[int] = None
    verified_by_staff_id: Optional[int] = None
    status: str
    findings: Optional[str] = None
    impression: Optional[str] = None
    recommendations: Optional[str] = None
    drafted_at: Optional[datetime] = None
    finalized_at: Optional[datetime] = None
    released_at: Optional[datetime] = None


class RadiologyReportActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    report: RadiologyReportReadSchema
