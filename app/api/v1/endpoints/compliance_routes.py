# app/api/v1/endpoints/compliance_routes.py
from __future__ import annotations

"""
FastAPI routes for the compliance / governance module (Stage 18).

Routers
-------
- ``/compliance/records``        — compliance record CRUD
- ``/compliance/accreditations`` — accreditation CRUD
- ``/compliance/incidents``      — incident reports (restricted)
- ``/compliance/infection-logs`` — infection control surveillance
- ``/compliance/quality-projects`` — QI projects
- ``/compliance/dashboard``      — aggregate counts

Permission codes
----------------
- ``COMPLIANCE_READ`` / ``COMPLIANCE_MANAGE``
- ``ACCREDITATION_READ`` / ``ACCREDITATION_MANAGE``
- ``INCIDENT_READ`` / ``INCIDENT_MANAGE``  (sensitive)
- ``INFECTION_LOG_READ`` / ``INFECTION_LOG_MANAGE``
- ``QUALITY_PROJECT_READ`` / ``QUALITY_PROJECT_MANAGE``
- ``GOVERNANCE_DASHBOARD``  (rolls up all the above)
"""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.compliance_schemas import (
    AccreditationActionResponseSchema,
    AccreditationCreateSchema,
    AccreditationListResponseSchema,
    AccreditationReadSchema,
    AccreditationUpdateSchema,
    ComplianceRecordActionResponseSchema,
    ComplianceRecordCreateSchema,
    ComplianceRecordListResponseSchema,
    ComplianceRecordReadSchema,
    ComplianceRecordUpdateSchema,
    GovernanceDashboardResponseSchema,
    IncidentReportActionResponseSchema,
    IncidentReportCreateSchema,
    IncidentReportListResponseSchema,
    IncidentReportReadSchema,
    IncidentReportUpdateSchema,
    InfectionControlLogActionResponseSchema,
    InfectionControlLogCreateSchema,
    InfectionControlLogListResponseSchema,
    InfectionControlLogReadSchema,
    QualityImprovementProjectActionResponseSchema,
    QualityImprovementProjectCreateSchema,
    QualityImprovementProjectListResponseSchema,
    QualityImprovementProjectReadSchema,
    QualityImprovementProjectUpdateSchema,
)
from app.services.compliance_service import (
    AccreditationService,
    ComplianceRecordService,
    GovernanceDashboardService,
    IncidentReportService,
    InfectionControlService,
    QualityImprovementProjectService,
)
from app.utils.pagination import paginate_response


from app.core.dependencies import require_plan_feature

# Single router with internal sub-prefixes keeps Swagger tidy and the
# permission boundaries obvious.
router = APIRouter(
    prefix="/compliance", 
    tags=["Compliance & Governance"],
    dependencies=[Depends(require_plan_feature("compliance"))]
)



# --- Service factories -----------------------------------------------------


def get_compliance_service(db: Annotated[Session, Depends(get_db)]) -> ComplianceRecordService:
    return ComplianceRecordService(db)


def get_accreditation_service(db: Annotated[Session, Depends(get_db)]) -> AccreditationService:
    return AccreditationService(db)


def get_incident_service(db: Annotated[Session, Depends(get_db)]) -> IncidentReportService:
    return IncidentReportService(db)


def get_infection_service(db: Annotated[Session, Depends(get_db)]) -> InfectionControlService:
    return InfectionControlService(db)


def get_quality_service(db: Annotated[Session, Depends(get_db)]) -> QualityImprovementProjectService:
    return QualityImprovementProjectService(db)


def get_dashboard_service(db: Annotated[Session, Depends(get_db)]) -> GovernanceDashboardService:
    return GovernanceDashboardService(db)


# --- ORM -> dict helpers ---------------------------------------------------


def _compliance_dict(r) -> dict:
    return {
        "id": r.id,
        "department_id": r.department_id,
        "owner_staff_id": r.owner_staff_id,
        "title": r.title,
        "compliance_area": r.compliance_area,
        "reference_code": r.reference_code,
        "due_date": r.due_date,
        "review_date": r.review_date,
        "status": str(r.status),
        "findings": r.findings,
        "action_plan": r.action_plan,
        "created_at": getattr(r, "created_at", None),
        "updated_at": getattr(r, "updated_at", None),
    }


def _accreditation_dict(a) -> dict:
    return {
        "id": a.id,
        "department_id": a.department_id,
        "accreditation_body": a.accreditation_body,
        "accreditation_name": a.accreditation_name,
        "certificate_no": a.certificate_no,
        "issue_date": a.issue_date,
        "expiry_date": a.expiry_date,
        "status": str(a.status),
        "notes": a.notes,
        "created_at": getattr(a, "created_at", None),
    }


def _incident_dict(i) -> dict:
    return {
        "id": i.id,
        "incident_no": i.incident_no,
        "incident_date": i.incident_date,
        "severity": str(i.severity),
        "category": i.category,
        "summary": i.summary,
        "immediate_action_taken": i.immediate_action_taken,
        "follow_up_required": bool(i.follow_up_required),
        "department_id": i.department_id,
        "patient_id": i.patient_id,
        "visit_id": i.visit_id,
        "reported_by_staff_id": i.reported_by_staff_id,
        "created_at": getattr(i, "created_at", None),
    }


def _infection_dict(l) -> dict:
    return {
        "id": l.id,
        "department_id": l.department_id,
        "recorded_by_staff_id": l.recorded_by_staff_id,
        "log_date": l.log_date,
        "infection_type": l.infection_type,
        "affected_area": l.affected_area,
        "details": l.details,
        "action_taken": l.action_taken,
        "outcome": l.outcome,
        "created_at": getattr(l, "created_at", None),
    }


def _quality_dict(p) -> dict:
    return {
        "id": p.id,
        "department_id": p.department_id,
        "project_lead_staff_id": p.project_lead_staff_id,
        "title": p.title,
        "objective": p.objective,
        "problem_statement": p.problem_statement,
        "start_date": p.start_date,
        "end_date": p.end_date,
        "status": str(p.status),
        "outcome_summary": p.outcome_summary,
        "recommendations": p.recommendations,
    }


# ============================================================
# COMPLIANCE RECORDS
# ============================================================


@router.get(
    "/records",
    response_model=ComplianceRecordListResponseSchema,
    summary="List compliance records",
)
def list_compliance_records(
    _: Annotated[User, Depends(require_permission("COMPLIANCE_READ"))],
    service: Annotated[ComplianceRecordService, Depends(get_compliance_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    department_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    compliance_area: Optional[str] = Query(None),
):
    items, total = service.list_records(
        skip=skip, limit=limit,
        department_id=department_id, status=status_filter, compliance_area=compliance_area,
    )
    return paginate_response(
        items=[_compliance_dict(r) for r in items],
        total=total, skip=skip, limit=limit,
        message="Compliance records fetched successfully.",
    )


@router.post(
    "/records",
    response_model=ComplianceRecordActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a compliance record",
)
def create_compliance_record(
    payload: ComplianceRecordCreateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("COMPLIANCE_MANAGE"))],
    service: Annotated[ComplianceRecordService, Depends(get_compliance_service)],
):
    r = service.create(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Compliance record created.", "record": _compliance_dict(r)}


@router.get(
    "/records/{record_id}",
    response_model=ComplianceRecordReadSchema,
    summary="Get a compliance record",
)
def get_compliance_record(
    record_id: int,
    _: Annotated[User, Depends(require_permission("COMPLIANCE_READ"))],
    service: Annotated[ComplianceRecordService, Depends(get_compliance_service)],
):
    return _compliance_dict(service.get(record_id))


@router.put(
    "/records/{record_id}",
    response_model=ComplianceRecordActionResponseSchema,
    summary="Update a compliance record",
)
def update_compliance_record(
    record_id: int,
    payload: ComplianceRecordUpdateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("COMPLIANCE_MANAGE"))],
    service: Annotated[ComplianceRecordService, Depends(get_compliance_service)],
):
    r = service.update(record_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Compliance record updated.", "record": _compliance_dict(r)}


@router.delete(
    "/records/{record_id}",
    summary="Soft-delete a compliance record",
)
def soft_delete_compliance_record(
    record_id: int,
    _: Annotated[User, Depends(require_permission("COMPLIANCE_MANAGE"))],
    service: Annotated[ComplianceRecordService, Depends(get_compliance_service)],
):
    r = service.soft_delete(record_id)
    return {"success": True, "message": "Compliance record removed.", "record_id": r.id}


# ============================================================
# ACCREDITATIONS
# ============================================================


@router.get(
    "/accreditations",
    response_model=AccreditationListResponseSchema,
    summary="List accreditations",
)
def list_accreditations(
    _: Annotated[User, Depends(require_permission("ACCREDITATION_READ"))],
    service: Annotated[AccreditationService, Depends(get_accreditation_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    department_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    items, total = service.list_accreditations(
        skip=skip, limit=limit, department_id=department_id, status=status_filter,
    )
    return paginate_response(
        items=[_accreditation_dict(a) for a in items],
        total=total, skip=skip, limit=limit,
        message="Accreditations fetched successfully.",
    )


@router.post(
    "/accreditations",
    response_model=AccreditationActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record an accreditation",
)
def create_accreditation(
    payload: AccreditationCreateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("ACCREDITATION_MANAGE"))],
    service: Annotated[AccreditationService, Depends(get_accreditation_service)],
):
    a = service.create(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Accreditation recorded.", "accreditation": _accreditation_dict(a)}


@router.get(
    "/accreditations/{accreditation_id}",
    response_model=AccreditationReadSchema,
    summary="Get an accreditation",
)
def get_accreditation(
    accreditation_id: int,
    _: Annotated[User, Depends(require_permission("ACCREDITATION_READ"))],
    service: Annotated[AccreditationService, Depends(get_accreditation_service)],
):
    return _accreditation_dict(service.get(accreditation_id))


@router.put(
    "/accreditations/{accreditation_id}",
    response_model=AccreditationActionResponseSchema,
    summary="Update an accreditation",
)
def update_accreditation(
    accreditation_id: int,
    payload: AccreditationUpdateSchema,
    _: Annotated[User, Depends(require_permission("ACCREDITATION_MANAGE"))],
    service: Annotated[AccreditationService, Depends(get_accreditation_service)],
):
    a = service.update(accreditation_id, payload)
    return {"success": True, "message": "Accreditation updated.", "accreditation": _accreditation_dict(a)}


@router.delete(
    "/accreditations/{accreditation_id}",
    summary="Soft-delete an accreditation",
)
def soft_delete_accreditation(
    accreditation_id: int,
    _: Annotated[User, Depends(require_permission("ACCREDITATION_MANAGE"))],
    service: Annotated[AccreditationService, Depends(get_accreditation_service)],
):
    a = service.soft_delete(accreditation_id)
    return {"success": True, "message": "Accreditation removed.", "accreditation_id": a.id}


# ============================================================
# INCIDENT REPORTS (sensitive)
# ============================================================


@router.get(
    "/incidents",
    response_model=IncidentReportListResponseSchema,
    summary="List incident reports",
)
def list_incidents(
    _: Annotated[User, Depends(require_permission("INCIDENT_READ"))],
    service: Annotated[IncidentReportService, Depends(get_incident_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    department_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None, description="LOW, MEDIUM, HIGH, CRITICAL"),
    from_dt: Optional[datetime] = Query(None),
    to_dt: Optional[datetime] = Query(None),
    follow_up_required: Optional[bool] = Query(None),
):
    items, total = service.list_incidents(
        skip=skip, limit=limit,
        department_id=department_id, severity=severity,
        from_dt=from_dt, to_dt=to_dt, follow_up_required=follow_up_required,
    )
    return paginate_response(
        items=[_incident_dict(i) for i in items],
        total=total, skip=skip, limit=limit,
        message="Incident reports fetched successfully.",
    )


@router.post(
    "/incidents",
    response_model=IncidentReportActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="File an incident report",
)
def file_incident(
    payload: IncidentReportCreateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("INCIDENT_MANAGE"))],
    service: Annotated[IncidentReportService, Depends(get_incident_service)],
):
    i = service.file_incident(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Incident filed.", "incident": _incident_dict(i)}


@router.get(
    "/incidents/{incident_id}",
    response_model=IncidentReportReadSchema,
    summary="Get an incident report",
)
def get_incident(
    incident_id: int,
    _: Annotated[User, Depends(require_permission("INCIDENT_READ"))],
    service: Annotated[IncidentReportService, Depends(get_incident_service)],
):
    return _incident_dict(service.get(incident_id))


@router.put(
    "/incidents/{incident_id}",
    response_model=IncidentReportActionResponseSchema,
    summary="Update an incident report",
)
def update_incident(
    incident_id: int,
    payload: IncidentReportUpdateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("INCIDENT_MANAGE"))],
    service: Annotated[IncidentReportService, Depends(get_incident_service)],
):
    i = service.update(incident_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Incident updated.", "incident": _incident_dict(i)}


# ============================================================
# INFECTION CONTROL
# ============================================================


@router.get(
    "/infection-logs",
    response_model=InfectionControlLogListResponseSchema,
    summary="List infection control logs",
)
def list_infection_logs(
    _: Annotated[User, Depends(require_permission("INFECTION_LOG_READ"))],
    service: Annotated[InfectionControlService, Depends(get_infection_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    department_id: Optional[int] = Query(None),
    infection_type: Optional[str] = Query(None),
):
    items, total = service.list_logs(
        skip=skip, limit=limit, department_id=department_id, infection_type=infection_type,
    )
    return paginate_response(
        items=[_infection_dict(l) for l in items],
        total=total, skip=skip, limit=limit,
        message="Infection control logs fetched successfully.",
    )


@router.post(
    "/infection-logs",
    response_model=InfectionControlLogActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add an infection control log",
)
def create_infection_log(
    payload: InfectionControlLogCreateSchema,
    _: Annotated[User, Depends(require_permission("INFECTION_LOG_MANAGE"))],
    service: Annotated[InfectionControlService, Depends(get_infection_service)],
):
    l = service.create(payload)
    return {"success": True, "message": "Infection control log added.", "log": _infection_dict(l)}


@router.get(
    "/infection-logs/{log_id}",
    response_model=InfectionControlLogReadSchema,
    summary="Get an infection control log",
)
def get_infection_log(
    log_id: int,
    _: Annotated[User, Depends(require_permission("INFECTION_LOG_READ"))],
    service: Annotated[InfectionControlService, Depends(get_infection_service)],
):
    return _infection_dict(service.get(log_id))


# ============================================================
# QUALITY IMPROVEMENT
# ============================================================


@router.get(
    "/quality-projects",
    response_model=QualityImprovementProjectListResponseSchema,
    summary="List quality improvement projects",
)
def list_quality_projects(
    _: Annotated[User, Depends(require_permission("QUALITY_PROJECT_READ"))],
    service: Annotated[QualityImprovementProjectService, Depends(get_quality_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    department_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    items, total = service.list_projects(
        skip=skip, limit=limit, department_id=department_id, status=status_filter,
    )
    return paginate_response(
        items=[_quality_dict(p) for p in items],
        total=total, skip=skip, limit=limit,
        message="Quality projects fetched successfully.",
    )


@router.post(
    "/quality-projects",
    response_model=QualityImprovementProjectActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a quality improvement project",
)
def create_quality_project(
    payload: QualityImprovementProjectCreateSchema,
    _: Annotated[User, Depends(require_permission("QUALITY_PROJECT_MANAGE"))],
    service: Annotated[QualityImprovementProjectService, Depends(get_quality_service)],
):
    p = service.create(payload)
    return {"success": True, "message": "Quality project created.", "project": _quality_dict(p)}


@router.get(
    "/quality-projects/{project_id}",
    response_model=QualityImprovementProjectReadSchema,
    summary="Get a quality improvement project",
)
def get_quality_project(
    project_id: int,
    _: Annotated[User, Depends(require_permission("QUALITY_PROJECT_READ"))],
    service: Annotated[QualityImprovementProjectService, Depends(get_quality_service)],
):
    return _quality_dict(service.get(project_id))


@router.put(
    "/quality-projects/{project_id}",
    response_model=QualityImprovementProjectActionResponseSchema,
    summary="Update a quality improvement project",
)
def update_quality_project(
    project_id: int,
    payload: QualityImprovementProjectUpdateSchema,
    _: Annotated[User, Depends(require_permission("QUALITY_PROJECT_MANAGE"))],
    service: Annotated[QualityImprovementProjectService, Depends(get_quality_service)],
):
    p = service.update(project_id, payload)
    return {"success": True, "message": "Quality project updated.", "project": _quality_dict(p)}


# ============================================================
# DASHBOARD
# ============================================================


@router.get(
    "/dashboard",
    response_model=GovernanceDashboardResponseSchema,
    summary="Aggregate governance dashboard counts",
)
def get_dashboard(
    _: Annotated[User, Depends(require_permission("GOVERNANCE_DASHBOARD"))],
    service: Annotated[GovernanceDashboardService, Depends(get_dashboard_service)],
):
    return {
        "success": True,
        "message": "Governance dashboard fetched successfully.",
        **service.snapshot(),
    }
