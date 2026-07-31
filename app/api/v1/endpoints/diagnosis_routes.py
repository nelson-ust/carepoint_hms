# app/api/v1/endpoints/diagnosis_routes.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.diagnosis_schema import (
    DiagnosisActionResponseSchema,
    DiagnosisCreateSchema,
    DiagnosisListResponseSchema,
    DiagnosisReadSchema,
    DiagnosisUpdateSchema,
)
from app.services.diagnosis_service import DiagnosisService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/diagnoses", 
    tags=["Diagnoses"],
    dependencies=[Depends(require_plan_feature("clinical"))]
)


def get_diagnosis_service(db: Annotated[Session, Depends(get_db)]) -> DiagnosisService:
    return DiagnosisService(db)


# ============================================================
# READ
# ============================================================


@router.get(
    "/visits/{visit_id}",
    response_model=DiagnosisListResponseSchema,
    summary="List diagnoses for a visit",
)
def list_for_visit(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("CONSULTATION_READ", "VISIT_READ"))],
    service: Annotated[DiagnosisService, Depends(get_diagnosis_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
):
    items, total = service.list_for_visit(visit_id, skip=skip, limit=limit)
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Diagnoses fetched successfully.",
    )


@router.post(
    "/",
    response_model=DiagnosisActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record a diagnosis",
)
def create_diagnosis(
    payload: DiagnosisCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[DiagnosisService, Depends(get_diagnosis_service)],
    _: Annotated[User, Depends(require_permission("DIAGNOSIS_WRITE"))],
):
    diagnosis = service.create(payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Diagnosis recorded.",
        "diagnosis": diagnosis,
    }


@router.get(
    "/{diagnosis_id}",
    response_model=DiagnosisReadSchema,
    summary="Get diagnosis details",
)
def get_diagnosis(
    diagnosis_id: int,
    _: Annotated[User, Depends(require_permission("CONSULTATION_READ"))],
    service: Annotated[DiagnosisService, Depends(get_diagnosis_service)],
):
    return service.get(diagnosis_id)


@router.put(
    "/{diagnosis_id}",
    response_model=DiagnosisActionResponseSchema,
    summary="Update a diagnosis",
)
def update_diagnosis(
    diagnosis_id: int,
    payload: DiagnosisUpdateSchema,
    actor: CurrentActiveUser,
    service: Annotated[DiagnosisService, Depends(get_diagnosis_service)],
    _: Annotated[User, Depends(require_permission("DIAGNOSIS_WRITE"))],
):
    diagnosis = service.update(diagnosis_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Diagnosis updated.",
        "diagnosis": diagnosis,
    }
