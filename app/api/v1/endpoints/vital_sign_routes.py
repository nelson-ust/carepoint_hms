# app/api/v1/endpoints/vital_sign_routes.py
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
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

router = APIRouter(
    prefix="/vital-signs", 
    tags=["Vital Signs"],
    dependencies=[Depends(require_plan_feature("clinical"))]
)


def get_vital_sign_service(db: Annotated[Session, Depends(get_db)]) -> VitalSignService:
    return VitalSignService(db)


# ============================================================
# READ
# ============================================================


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
    limit: int = Query(50, ge=1, le=1000),
):
    items, total = service.list_for_visit(visit_id, skip=skip, limit=limit)
    return paginate_response(
        items=items,
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
            "recorded_at": datetime.now(),
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
    return latest


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
        "vital_sign": record,
    }
