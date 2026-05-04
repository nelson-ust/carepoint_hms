# app/schemas/medical_history_schema.py
from __future__ import annotations

"""
Pydantic schemas for the consolidated patient medical history view.

The medical history endpoint exists to give clinicians a single, structured
read-only summary of every clinical event tied to a patient: prior visits,
consultations and diagnoses, lab orders + results, radiology orders +
reports, surgical cases, procedure orders, prescriptions, admissions,
known allergies, and a vital-sign trend.

Schemas here are intentionally *read-only* and use loose typing on the
nested entries (lots of ``Optional`` + ``str`` for enum-like fields) so
the aggregator can stitch records together without forcing every caller
to parse cross-domain enums.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# ============================================================
# DEMOGRAPHIC HEADER
# ============================================================


class PatientHistoryDemographicSchema(BaseModel):
    """Compact demographic + clinical-risk header rendered atop the view."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    hospital_number: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    age_years: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    genotype: Optional[str] = None
    allergies: Optional[str] = None
    patient_type: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    chronic_conditions: Optional[str] = None


# ============================================================
# CLINICAL ENTRY SCHEMAS
# ============================================================


class VisitHistoryEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_code: str
    visit_date: datetime
    status: str
    priority: Optional[str] = None
    visit_reason: Optional[str] = None
    first_service_delivery_point_id: Optional[int] = None
    current_service_delivery_point_id: Optional[int] = None


class ConsultationHistoryEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    clinician_staff_id: Optional[int] = None
    status: str
    subjective_note: Optional[str] = None
    objective_note: Optional[str] = None
    assessment_note: Optional[str] = None
    plan_note: Optional[str] = None
    consultation_started_at: Optional[datetime] = None
    consultation_ended_at: Optional[datetime] = None


class DiagnosisHistoryEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    consultation_id: Optional[int] = None
    diagnosis_code: Optional[str] = None
    diagnosis_text: Optional[str] = None
    diagnosis_type: Optional[str] = None
    is_primary: Optional[bool] = None
    diagnosed_at: Optional[datetime] = None


class LabResultLiteSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    result_status: str
    result_value: Optional[str] = None
    result_text: Optional[str] = None
    unit_of_measure: Optional[str] = None
    reference_range: Optional[str] = None
    interpretation: Optional[str] = None
    released_at: Optional[datetime] = None


class LabOrderItemHistoryEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lab_test_catalog_id: int
    lab_test_name: Optional[str] = None
    status: str
    specimen_id: Optional[str] = None
    sample_collected_at: Optional[datetime] = None
    result: Optional[LabResultLiteSchema] = None


class LabOrderHistoryEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    order_no: str
    status: str
    clinical_note: Optional[str] = None
    ordered_at: datetime
    items: list[LabOrderItemHistoryEntrySchema] = []


class RadiologyReportLiteSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    findings: Optional[str] = None
    impression: Optional[str] = None
    recommendations: Optional[str] = None
    finalized_at: Optional[datetime] = None
    released_at: Optional[datetime] = None


class RadiologyOrderHistoryEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    order_no: str
    status: str
    priority: Optional[str] = None
    clinical_indication: Optional[str] = None
    ordered_at: datetime
    items: list[dict[str, Any]] = []
    reports: list[RadiologyReportLiteSchema] = []


class PrescriptionItemHistoryEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    drug_id: Optional[int] = None
    drug_name: Optional[str] = None
    strength: Optional[str] = None
    dosage_form: Optional[str] = None
    dosage_instruction: Optional[str] = None
    quantity_prescribed: Optional[Decimal] = None
    quantity_dispensed: Optional[Decimal] = None
    status: Optional[str] = None


class PrescriptionHistoryEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    prescription_no: str
    status: str
    note: Optional[str] = None
    prescribed_at: datetime
    items: list[PrescriptionItemHistoryEntrySchema] = []


class ProcedureOrderHistoryEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    status: str
    procedure_catalog_id: Optional[int] = None
    procedure_name: Optional[str] = None
    notes: Optional[str] = None
    ordered_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class SurgicalCaseHistoryEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_no: str
    visit_id: Optional[int] = None
    status: str
    procedure_catalog_id: int
    procedure_name: Optional[str] = None
    is_emergency: bool = False
    asa_class: Optional[str] = None
    anaesthesia_type: Optional[str] = None
    scheduled_start_at: Optional[datetime] = None
    incision_at: Optional[datetime] = None
    closure_at: Optional[datetime] = None
    diagnosis_text: Optional[str] = None
    findings_text: Optional[str] = None


class AdmissionHistoryEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admission_no: str
    visit_id: Optional[int] = None
    ward_id: int
    bed_id: Optional[int] = None
    admission_status: str
    admission_reason: Optional[str] = None
    admitted_at: datetime
    expected_discharge_at: Optional[datetime] = None
    actual_discharge_at: Optional[datetime] = None


class VitalSignHistoryEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    recorded_at: Optional[datetime] = None
    temperature_c: Optional[Decimal] = None
    pulse_bpm: Optional[int] = None
    respiratory_rate: Optional[int] = None
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    spo2_percent: Optional[int] = None
    weight_kg: Optional[Decimal] = None
    height_cm: Optional[Decimal] = None
    bmi: Optional[Decimal] = None
    pain_score: Optional[int] = None
    notes: Optional[str] = None


class TriageHistoryEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    triage_priority: Optional[str] = None
    chief_complaint: Optional[str] = None
    history_of_present_illness: Optional[str] = None
    triage_notes: Optional[str] = None
    assessed_at: Optional[datetime] = None


# ============================================================
# AGGREGATE RESPONSE
# ============================================================


class PatientMedicalHistorySchema(BaseModel):
    """
    Top-level aggregate: a clinician-friendly summary of everything we
    know about this patient.
    """

    model_config = ConfigDict(from_attributes=True)

    patient: PatientHistoryDemographicSchema
    summary: dict[str, int]
    allergies: Optional[str] = None
    visits: list[VisitHistoryEntrySchema] = []
    consultations: list[ConsultationHistoryEntrySchema] = []
    diagnoses: list[DiagnosisHistoryEntrySchema] = []
    lab_orders: list[LabOrderHistoryEntrySchema] = []
    radiology_orders: list[RadiologyOrderHistoryEntrySchema] = []
    prescriptions: list[PrescriptionHistoryEntrySchema] = []
    procedure_orders: list[ProcedureOrderHistoryEntrySchema] = []
    surgical_cases: list[SurgicalCaseHistoryEntrySchema] = []
    admissions: list[AdmissionHistoryEntrySchema] = []
    triage_assessments: list[TriageHistoryEntrySchema] = []
    vital_signs: list[VitalSignHistoryEntrySchema] = []


class PatientMedicalHistoryResponseSchema(BaseModel):
    success: bool = True
    message: str = "Patient medical history fetched successfully."
    history: PatientMedicalHistorySchema
