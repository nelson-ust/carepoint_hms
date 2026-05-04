# app/api/v1/endpoints/vital_sign_routes.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.vital_sign_schema import (
    VitalSignActionResponseSchema,
    VitalSignCreateSchema,
    VitalSignListResponseSchema,
    VitalSignReadSchema,
)
from app.services.vital_sign_service import VitalSignService
from app.utils.pagination import paginate_response

router = APIRouter(prefix="/vital-signs", tags=["Vital Signs"])


def get_vital_sign_service(db: Annotated[Session, Depends(get_db)]) -> VitalSignService:
    return VitalSignService(db)


def _serialize(v) -> dict:
    return {
        "id": v.id,
        "visit_id": v.visit_id,
        "recorded_by_staff_id": v.recorded_by_staff_id,
        "temperature_celsius": v.temperature_celsius,
        "pulse_rate": v.pulse_rate,
        "respiratory_rate": v.respiratory_rate,
        "systolic_bp": v.systolic_bp,
        "diastolic_bp": v.diastolic_bp,
        "oxygen_saturation": v.oxygen_saturation,
        "weight_kg": v.weight_kg,
        "height_cm": v.height_cm,
        "bmi": v.bmi,
        "pain_score": v.pain_score,
        "recorded_at": v.recorded_at,
        "created_at": getattr(v, "created_at", None),
    }


@router.get(
    "/visits/{visit_id}",
    response_model=VitalSignListResponseSchema,
    summary="List vital signs for a visit",
)
def list_for_visit(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("VITAL_SIGN_RECORD", "VISIT_READ"))],
    service: Annotated[VitalSignService, Depends(get_vital_sign_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    items, total = service.list_for_visit(visit_id, skip=skip, limit=limit)
    return paginate_response(
        items=[_serialize(v) for v in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Vital signs fetched successfully.",
    )


@router.get(
    "/visits/{visit_id}/latest",
    response_model=VitalSignReadSchema,
    summary="Latest vital sign record for a visit",
)
def latest_for_visit(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("VITAL_SIGN_RECORD", "VISIT_READ"))],
    service: Annotated[VitalSignService, Depends(get_vital_sign_service)],
):
    latest = service.latest_for_visit(visit_id)
    if latest is None:
        return {
            "id": 0,
            "visit_id": visit_id,
            "recorded_at": None,
            "recorded_by_staff_id": None,
            "temperature_celsius": None,
            "pulse_rate": None,
            "respiratory_rate": None,
            "systolic_bp": None,
            "diastolic_bp": None,
            "oxygen_saturation": None,
            "weight_kg": None,
            "height_cm": None,
            "bmi": None,
            "pain_score": None,
        }
    return _serialize(latest)


@router.post(
    "/",
    response_model=VitalSignActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record vital signs",
)
def create_vitals(
    payload: VitalSignCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[VitalSignService, Depends(get_vital_sign_service)],
    _: Annotated[User, Depends(require_permission("VITAL_SIGN_RECORD"))],
):
    record = service.create(payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Vital signs recorded.",
        "vital_sign": _serialize(record),
    }
