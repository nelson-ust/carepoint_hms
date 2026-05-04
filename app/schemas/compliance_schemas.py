# app/schemas/compliance_schemas.py
from __future__ import annotations

"""
Pydantic schemas for the compliance / governance module (Stage 18).

Covers:
- ``ComplianceRecord`` — periodic compliance obligations with due dates
- ``Accreditation``    — facility / departmental accreditation with expiry
- ``IncidentReport``   — patient safety + operational incidents
- ``InfectionControlLog`` — surveillance log
- ``QualityImprovementProject`` — improvement initiatives

Access notes
------------
Incidents may carry sensitive identifiers. Access is gated to staff with
``INCIDENT_READ`` (read) and ``INCIDENT_MANAGE`` (write) at the route layer.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================
# COMPLIANCE RECORD
# ============================================================


class ComplianceRecordCreateSchema(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    department_id: Optional[int] = None
    owner_staff_id: Optional[int] = None
    compliance_area: Optional[str] = Field(None, max_length=150)
    reference_code: Optional[str] = Field(None, max_length=100)
    due_date: Optional[date] = None
    review_date: Optional[date] = None
    status: Optional[str] = Field(
        None,
        description="COMPLIANT, NON_COMPLIANT, IN_PROGRESS, EXPIRED. Defaults to IN_PROGRESS.",
    )
    findings: Optional[str] = None
    action_plan: Optional[str] = None

    @field_validator("status")
    @classmethod
    def normalize_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip().upper()
        allowed = {"COMPLIANT", "NON_COMPLIANT", "IN_PROGRESS", "EXPIRED"}
        if normalized not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}.")
        return normalized


class ComplianceRecordUpdateSchema(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    owner_staff_id: Optional[int] = None
    compliance_area: Optional[str] = Field(None, max_length=150)
    reference_code: Optional[str] = Field(None, max_length=100)
    due_date: Optional[date] = None
    review_date: Optional[date] = None
    status: Optional[str] = None
    findings: Optional[str] = None
    action_plan: Optional[str] = None

    @field_validator("status")
    @classmethod
    def normalize_status(cls, v: Optional[str]) -> Optional[str]:
        return ComplianceRecordCreateSchema.normalize_status.__func__(cls, v)


class ComplianceRecordReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department_id: Optional[int] = None
    owner_staff_id: Optional[int] = None
    title: str
    compliance_area: Optional[str] = None
    reference_code: Optional[str] = None
    due_date: Optional[date] = None
    review_date: Optional[date] = None
    status: str
    findings: Optional[str] = None
    action_plan: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ComplianceRecordListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Compliance records fetched successfully."
    items: list[ComplianceRecordReadSchema]
    count: int
    meta: dict


class ComplianceRecordActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    record: ComplianceRecordReadSchema


# ============================================================
# ACCREDITATION
# ============================================================


class AccreditationCreateSchema(BaseModel):
    accreditation_body: str = Field(..., min_length=1, max_length=255)
    accreditation_name: str = Field(..., min_length=1, max_length=255)
    department_id: Optional[int] = None
    certificate_no: Optional[str] = Field(None, max_length=100)
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    status: Optional[str] = Field(
        None, description="ACTIVE, PENDING, EXPIRED, REVOKED. Defaults to PENDING."
    )
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def normalize_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip().upper()
        allowed = {"ACTIVE", "PENDING", "EXPIRED", "REVOKED"}
        if normalized not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}.")
        return normalized


class AccreditationUpdateSchema(BaseModel):
    certificate_no: Optional[str] = Field(None, max_length=100)
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def normalize_status(cls, v: Optional[str]) -> Optional[str]:
        return AccreditationCreateSchema.normalize_status.__func__(cls, v)


class AccreditationReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department_id: Optional[int] = None
    accreditation_body: str
    accreditation_name: str
    certificate_no: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    status: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class AccreditationListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Accreditation records fetched successfully."
    items: list[AccreditationReadSchema]
    count: int
    meta: dict


class AccreditationActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    accreditation: AccreditationReadSchema


# ============================================================
# INCIDENT REPORT
# ============================================================


class IncidentReportCreateSchema(BaseModel):
    summary: str = Field(..., min_length=1)
    incident_date: Optional[datetime] = None
    severity: str = Field("MEDIUM", description="LOW, MEDIUM, HIGH, CRITICAL.")
    category: Optional[str] = Field(None, max_length=150)
    department_id: Optional[int] = None
    patient_id: Optional[int] = None
    visit_id: Optional[int] = None
    reported_by_staff_id: Optional[int] = None
    immediate_action_taken: Optional[str] = None
    follow_up_required: bool = False

    @field_validator("severity")
    @classmethod
    def normalize_severity(cls, v: str) -> str:
        normalized = v.strip().upper()
        allowed = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError(f"severity must be one of {sorted(allowed)}.")
        return normalized


class IncidentReportUpdateSchema(BaseModel):
    """Limited update — incident facts shouldn't be rewritten freely."""

    severity: Optional[str] = None
    category: Optional[str] = Field(None, max_length=150)
    immediate_action_taken: Optional[str] = None
    follow_up_required: Optional[bool] = None

    @field_validator("severity")
    @classmethod
    def normalize_severity(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return IncidentReportCreateSchema.normalize_severity.__func__(cls, v)


class IncidentReportReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_no: str
    incident_date: datetime
    severity: str
    category: Optional[str] = None
    summary: str
    immediate_action_taken: Optional[str] = None
    follow_up_required: bool = False
    department_id: Optional[int] = None
    patient_id: Optional[int] = None
    visit_id: Optional[int] = None
    reported_by_staff_id: Optional[int] = None
    created_at: Optional[datetime] = None


class IncidentReportListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Incident reports fetched successfully."
    items: list[IncidentReportReadSchema]
    count: int
    meta: dict


class IncidentReportActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    incident: IncidentReportReadSchema


# ============================================================
# INFECTION CONTROL LOG
# ============================================================


class InfectionControlLogCreateSchema(BaseModel):
    log_date: datetime
    details: str = Field(..., min_length=1)
    department_id: Optional[int] = None
    recorded_by_staff_id: Optional[int] = None
    infection_type: Optional[str] = Field(None, max_length=150)
    affected_area: Optional[str] = Field(None, max_length=150)
    action_taken: Optional[str] = None
    outcome: Optional[str] = None


class InfectionControlLogReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department_id: Optional[int] = None
    recorded_by_staff_id: Optional[int] = None
    log_date: datetime
    infection_type: Optional[str] = None
    affected_area: Optional[str] = None
    details: str
    action_taken: Optional[str] = None
    outcome: Optional[str] = None
    created_at: Optional[datetime] = None


class InfectionControlLogListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Infection control logs fetched successfully."
    items: list[InfectionControlLogReadSchema]
    count: int
    meta: dict


class InfectionControlLogActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    log: InfectionControlLogReadSchema


# ============================================================
# QUALITY IMPROVEMENT PROJECT
# ============================================================


class QualityImprovementProjectCreateSchema(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    department_id: Optional[int] = None
    project_lead_staff_id: Optional[int] = None
    objective: Optional[str] = None
    problem_statement: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = Field(
        None, description="PLANNED, ACTIVE, ON_HOLD, COMPLETED, CANCELLED."
    )
    outcome_summary: Optional[str] = None
    recommendations: Optional[str] = None

    @field_validator("status")
    @classmethod
    def normalize_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip().upper()
        allowed = {"PLANNED", "ACTIVE", "ON_HOLD", "COMPLETED", "CANCELLED"}
        if normalized not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}.")
        return normalized


class QualityImprovementProjectUpdateSchema(BaseModel):
    objective: Optional[str] = None
    problem_statement: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    outcome_summary: Optional[str] = None
    recommendations: Optional[str] = None

    @field_validator("status")
    @classmethod
    def normalize_status(cls, v: Optional[str]) -> Optional[str]:
        return QualityImprovementProjectCreateSchema.normalize_status.__func__(cls, v)


class QualityImprovementProjectReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department_id: Optional[int] = None
    project_lead_staff_id: Optional[int] = None
    title: str
    objective: Optional[str] = None
    problem_statement: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str
    outcome_summary: Optional[str] = None
    recommendations: Optional[str] = None


class QualityImprovementProjectListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Quality projects fetched successfully."
    items: list[QualityImprovementProjectReadSchema]
    count: int
    meta: dict


class QualityImprovementProjectActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    project: QualityImprovementProjectReadSchema


# ============================================================
# DASHBOARD
# ============================================================


class GovernanceDashboardResponseSchema(BaseModel):
    """Aggregate counts for the governance dashboard."""

    success: bool = True
    message: str = "Governance dashboard fetched successfully."
    compliance_due_soon: int = 0
    compliance_overdue: int = 0
    accreditations_expiring_soon: int = 0
    accreditations_expired: int = 0
    incidents_open_critical: int = 0
    incidents_open_high: int = 0
    quality_projects_active: int = 0
