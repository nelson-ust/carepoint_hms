# app/api/v1/endpoints/patient_portal_home_health_routes.py
from __future__ import annotations

"""
Patient-facing Home Health endpoints (portal).

A patient can see their own home visits, care plan and monitoring trends,
submit self-measured readings (which run through the same early-warning
engine), and request a home visit. All data is strictly scoped to the
authenticated patient; clinical actions (results, dispensing, alert triage)
remain staff-only.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_plan_feature
from app.core.enums import CarePlanStatus, HomeVisitStatus, HomeVisitType
from app.models.all_models import User
from app.schemas.care_plan_schemas import (
    CarePlanDetailSchema,
    CarePlanGoalReadSchema,
    CarePlanInterventionReadSchema,
    CarePlanProgressNoteReadSchema,
    CarePlanReadSchema,
    CarePlanReviewReadSchema,
    CareTaskReadSchema,
)
from app.schemas.home_visit_schemas import HomeVisitListResponseSchema
from app.schemas.patient_portal_home_health_schemas import (
    PortalHomeHealthSummarySchema,
    PortalReadingSubmitSchema,
    PortalVisitRequestSchema,
)
from app.schemas.remote_monitoring_schemas import MonitoringReadingListResponseSchema
from app.services.care_plan_service import CarePlanService
from app.services.home_visit_service import HomeVisitService
from app.services.patient_portal_service import PatientPortalService
from app.services.remote_monitoring_service import RemoteMonitoringService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/portal/home-health",
    tags=["Patient Portal - Home Health"],
    dependencies=[Depends(require_plan_feature("patient_portal"))],
)


def _patient_id(db: Session, user: User) -> int:
    return PatientPortalService(db).get_patient_by_user_id(user.id).id


@router.get("/summary", response_model=PortalHomeHealthSummarySchema, summary="My home-health summary")
def summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    pid = _patient_id(db, current_user)
    hv = HomeVisitService(db)
    cp = CarePlanService(db)
    rm = RemoteMonitoringService(db)

    visits, _ = hv.list(patient_id=pid, limit=100)
    upcoming = [v for v in visits if str(v.status) not in ("COMPLETED", "CANCELLED", "MISSED") and v.scheduled_start_at]
    upcoming.sort(key=lambda v: v.scheduled_start_at)
    plans, _ = cp.list(patient_id=pid, status="ACTIVE", limit=1)
    plan = plans[0] if plans else None
    open_tasks = getattr(plan, "open_task_count", 0) if plan else 0
    since = datetime.now(timezone.utc) - timedelta(days=7)
    readings, r_total = rm.list_readings(patient_id=pid, from_dt=since, limit=200)
    return {
        "success": True,
        "has_active_care_plan": plan is not None,
        "care_plan_title": getattr(plan, "title", None) if plan else None,
        "upcoming_visit_count": len(upcoming),
        "next_visit_at": upcoming[0].scheduled_start_at if upcoming else None,
        "open_task_count": open_tasks or 0,
        "readings_last_7d": r_total,
    }


@router.get("/visits", response_model=HomeVisitListResponseSchema, summary="My home visits")
def my_visits(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    pid = _patient_id(db, current_user)
    items, total = HomeVisitService(db).list(patient_id=pid, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit, message="Your home visits.")


@router.get("/care-plan", summary="My active care plan")
def my_care_plan(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    pid = _patient_id(db, current_user)
    svc = CarePlanService(db)
    plans, _ = svc.list(patient_id=pid, status="ACTIVE", limit=1)
    if not plans:
        return {"success": True, "care_plan": None, "message": "No active care plan."}
    detail = svc.get_detail(plans[0].id)
    base = CarePlanReadSchema.model_validate(detail["plan"]).model_dump()
    plan = CarePlanDetailSchema(
        **base,
        goals=[CarePlanGoalReadSchema.model_validate(x) for x in detail["goals"]],
        interventions=[CarePlanInterventionReadSchema.model_validate(x) for x in detail["interventions"]],
        tasks=[CareTaskReadSchema.model_validate(x) for x in detail["tasks"]],
        progress_notes=[CarePlanProgressNoteReadSchema.model_validate(x) for x in detail["progress_notes"]],
        reviews=[CarePlanReviewReadSchema.model_validate(x) for x in detail["reviews"]],
    )
    return {"success": True, "care_plan": plan}


@router.get("/readings", response_model=MonitoringReadingListResponseSchema, summary="My monitoring readings")
def my_readings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
    reading_type: Optional[str] = Query(None),
):
    pid = _patient_id(db, current_user)
    items, total = RemoteMonitoringService(db).list_readings(patient_id=pid, reading_type=reading_type, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit, message="Your readings.")


@router.post("/readings", summary="Submit a self-measured reading")
def submit_reading(
    payload: PortalReadingSubmitSchema,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    from app.schemas.remote_monitoring_schemas import MonitoringReadingCreateSchema

    pid = _patient_id(db, current_user)
    create = MonitoringReadingCreateSchema(
        patient_id=pid,
        reading_type=payload.reading_type,
        source="PATIENT_APP",
        primary_value=payload.primary_value,
        systolic=payload.systolic,
        diastolic=payload.diastolic,
        unit=payload.unit,
        notes=payload.notes,
    )
    reading, alert = RemoteMonitoringService(db).record_reading(create, actor_user_id=current_user.id)
    return {
        "success": True,
        "message": "Reading submitted." + (" Your care team has been notified." if alert else ""),
        "reading_id": reading.id,
        "flagged": alert is not None,
    }


@router.post("/visit-requests", summary="Request a home visit")
def request_visit(
    payload: PortalVisitRequestSchema,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    from app.schemas.home_visit_schemas import HomeVisitCreateSchema

    pid = _patient_id(db, current_user)
    create = HomeVisitCreateSchema(
        patient_id=pid,
        visit_type=HomeVisitType.ROUTINE,
        reason=payload.reason,
        scheduled_start_at=payload.preferred_date,
        address=payload.address,
    )
    visit = HomeVisitService(db).create(create, actor_user_id=current_user.id)
    return {
        "success": True,
        "message": "Your home visit request has been received. The care team will confirm shortly.",
        "visit_code": visit.visit_code,
        "status": str(visit.status),
    }
