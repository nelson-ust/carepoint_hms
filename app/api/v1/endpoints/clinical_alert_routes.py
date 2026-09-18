# app/api/v1/endpoints/clinical_alert_routes.py
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.clinical_alert_schemas import (
    AlertAcknowledgeSchema,
    AlertEscalateSchema,
    AlertResolveSchema,
    AlertSummarySchema,
    ClinicalAlertActionResponseSchema,
    ClinicalAlertCreateSchema,
    ClinicalAlertListResponseSchema,
    EarlyWarningRuleCreateSchema,
    EarlyWarningRuleListResponseSchema,
    EarlyWarningRuleReadSchema,
    EarlyWarningRuleResponseSchema,
    EarlyWarningRuleUpdateSchema,
)
from app.services.clinical_alert_service import ClinicalAlertService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/clinical-alerts",
    tags=["Home Health - Clinical Alerts"],
    dependencies=[Depends(require_plan_feature("clinical"))],
)

_READ = require_permission("CLINICAL_ALERT_READ", "CLINICAL_ALERT_MANAGE")
_MANAGE = require_permission("CLINICAL_ALERT_MANAGE")
_RULE_MANAGE = require_permission("ALERT_RULE_MANAGE", "CLINICAL_ALERT_MANAGE")


def get_service(db: Annotated[Session, Depends(get_db)]) -> ClinicalAlertService:
    return ClinicalAlertService(db)


# ----- Rules (declared before /{alert_id}) -----
@router.get("/rules", response_model=EarlyWarningRuleListResponseSchema, summary="List early-warning rules")
def list_rules(
    _: Annotated[User, Depends(_READ)],
    service: Annotated[ClinicalAlertService, Depends(get_service)],
    reading_type: Optional[str] = Query(None),
    active_only: bool = Query(True),
):
    items = service.list_rules(reading_type=reading_type, active_only=active_only)
    return paginate_response(items=items, total=len(items), skip=0, limit=len(items) or 1, message="Rules fetched successfully.")


@router.post("/rules", response_model=EarlyWarningRuleResponseSchema, status_code=status.HTTP_201_CREATED, summary="Create an early-warning rule")
def create_rule(
    payload: EarlyWarningRuleCreateSchema,
    _: Annotated[User, Depends(_RULE_MANAGE)],
    service: Annotated[ClinicalAlertService, Depends(get_service)],
):
    rule = service.create_rule(payload)
    return {"success": True, "message": "Rule created.", "rule": rule}


@router.patch("/rules/{rule_id}", response_model=EarlyWarningRuleResponseSchema, summary="Update an early-warning rule")
def update_rule(
    rule_id: int,
    payload: EarlyWarningRuleUpdateSchema,
    _: Annotated[User, Depends(_RULE_MANAGE)],
    service: Annotated[ClinicalAlertService, Depends(get_service)],
):
    rule = service.update_rule(rule_id, payload)
    return {"success": True, "message": "Rule updated.", "rule": rule}


# ----- Summary -----
@router.get("/summary", response_model=AlertSummarySchema, summary="Open-alert summary counts")
def alert_summary(
    _: Annotated[User, Depends(_READ)],
    service: Annotated[ClinicalAlertService, Depends(get_service)],
):
    data = service.summary()
    return {"success": True, **data}


# ----- Alerts -----
@router.get("/", response_model=ClinicalAlertListResponseSchema, summary="List clinical alerts")
def list_alerts(
    _: Annotated[User, Depends(_READ)],
    service: Annotated[ClinicalAlertService, Depends(get_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    patient_id: Optional[int] = Query(None),
    assigned_to_staff_id: Optional[int] = Query(None),
    open_only: bool = Query(False),
):
    items, total = service.list(
        status=status_filter, severity=severity, alert_type=alert_type, patient_id=patient_id,
        assigned_to_staff_id=assigned_to_staff_id, open_only=open_only, skip=skip, limit=limit,
    )
    return paginate_response(items=items, total=total, skip=skip, limit=limit, message="Alerts fetched successfully.")


@router.post("/", response_model=ClinicalAlertActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Raise a manual clinical alert")
def create_alert(
    payload: ClinicalAlertCreateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(_MANAGE)],
    service: Annotated[ClinicalAlertService, Depends(get_service)],
):
    alert = service.create_manual(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Alert raised.", "alert": alert}


@router.get("/{alert_id}", response_model=ClinicalAlertActionResponseSchema, summary="Get an alert")
def get_alert(
    alert_id: int,
    _: Annotated[User, Depends(_READ)],
    service: Annotated[ClinicalAlertService, Depends(get_service)],
):
    return {"success": True, "message": "Alert fetched.", "alert": service.get(alert_id)}


@router.post("/{alert_id}/acknowledge", response_model=ClinicalAlertActionResponseSchema, summary="Acknowledge an alert")
def acknowledge_alert(
    alert_id: int,
    payload: AlertAcknowledgeSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(_MANAGE)],
    service: Annotated[ClinicalAlertService, Depends(get_service)],
):
    alert = service.acknowledge(alert_id, actor_user_id=actor.id, note=payload.note)
    return {"success": True, "message": "Alert acknowledged.", "alert": alert}


@router.post("/{alert_id}/resolve", response_model=ClinicalAlertActionResponseSchema, summary="Resolve an alert")
def resolve_alert(
    alert_id: int,
    payload: AlertResolveSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(_MANAGE)],
    service: Annotated[ClinicalAlertService, Depends(get_service)],
):
    alert = service.resolve(alert_id, actor_user_id=actor.id, resolution_note=payload.resolution_note)
    return {"success": True, "message": "Alert resolved.", "alert": alert}


@router.post("/{alert_id}/dismiss", response_model=ClinicalAlertActionResponseSchema, summary="Dismiss an alert")
def dismiss_alert(
    alert_id: int,
    payload: AlertResolveSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(_MANAGE)],
    service: Annotated[ClinicalAlertService, Depends(get_service)],
):
    alert = service.dismiss(alert_id, actor_user_id=actor.id, note=payload.resolution_note)
    return {"success": True, "message": "Alert dismissed.", "alert": alert}


@router.post("/{alert_id}/escalate", response_model=ClinicalAlertActionResponseSchema, summary="Escalate an alert")
def escalate_alert(
    alert_id: int,
    payload: AlertEscalateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(_MANAGE)],
    service: Annotated[ClinicalAlertService, Depends(get_service)],
):
    alert = service.escalate(alert_id, actor_user_id=actor.id, escalated_to_staff_id=payload.escalated_to_staff_id, note=payload.note)
    return {"success": True, "message": "Alert escalated.", "alert": alert}
