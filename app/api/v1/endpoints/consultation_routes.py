# app/api/v1/endpoints/consultation_routes.py
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.consultation_schema import (
    ConsultationActionResponseSchema,
    ConsultationCreateSchema,
    ConsultationFinalizeSchema,
    ConsultationListResponseSchema,
    ConsultationReadSchema,
    ConsultationUpdateSchema,
)
from app.services.consultation_service import ConsultationService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/consultations", 
    tags=["Consultations"],
    dependencies=[Depends(require_plan_feature("clinical"))]
)


def get_consultation_service(db: Annotated[Session, Depends(get_db)]) -> ConsultationService:
    return ConsultationService(db)


def _serialize(c) -> dict:
    return {
        "id": c.id,
        "visit_id": c.visit_id,
        "clinician_staff_id": c.clinician_staff_id,
        "status": str(c.status),
        "subjective_note": c.subjective_note,
        "objective_note": c.objective_note,
        "assessment_note": c.assessment_note,
        "plan_note": c.plan_note,
        "consultation_started_at": c.consultation_started_at,
        "consultation_ended_at": c.consultation_ended_at,
        "created_at": getattr(c, "created_at", None),
        "updated_at": getattr(c, "updated_at", None),
    }


@router.get(
    "/visits/{visit_id}",
    response_model=ConsultationListResponseSchema,
    summary="List consultations for a visit",
)
def list_for_visit(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("CONSULTATION_READ", "VISIT_READ"))],
    service: Annotated[ConsultationService, Depends(get_consultation_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    items, total = service.list_for_visit(visit_id, skip=skip, limit=limit)
    return paginate_response(
        items=[_serialize(c) for c in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Consultations fetched successfully.",
    )


@router.post(
    "/",
    response_model=ConsultationActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Start a consultation",
)
def create_consultation(
    payload: ConsultationCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[ConsultationService, Depends(get_consultation_service)],
    _: Annotated[User, Depends(require_permission("CONSULTATION_WRITE"))],
):
    consultation = service.create(payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Consultation started.",
        "consultation": _serialize(consultation),
    }


@router.get(
    "/{consultation_id}",
    response_model=ConsultationReadSchema,
    summary="Get consultation details",
)
def get_consultation(
    consultation_id: int,
    _: Annotated[User, Depends(require_permission("CONSULTATION_READ"))],
    service: Annotated[ConsultationService, Depends(get_consultation_service)],
):
    return _serialize(service.get(consultation_id))


@router.put(
    "/{consultation_id}",
    response_model=ConsultationActionResponseSchema,
    summary="Update consultation notes",
)
def update_consultation(
    consultation_id: int,
    payload: ConsultationUpdateSchema,
    actor: CurrentActiveUser,
    service: Annotated[ConsultationService, Depends(get_consultation_service)],
    _: Annotated[User, Depends(require_permission("CONSULTATION_WRITE"))],
):
    consultation = service.update(consultation_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Consultation updated.",
        "consultation": _serialize(consultation),
    }


@router.post(
    "/{consultation_id}/finalize",
    response_model=ConsultationActionResponseSchema,
    summary="Finalize a consultation (route or end visit)",
)
def finalize_consultation(
    consultation_id: int,
    payload: ConsultationFinalizeSchema,
    actor: CurrentActiveUser,
    service: Annotated[ConsultationService, Depends(get_consultation_service)],
    _: Annotated[User, Depends(require_permission("CONSULTATION_WRITE", "VISIT_ROUTE"))],
):
    consultation = service.finalize(consultation_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Consultation finalized.",
        "consultation": _serialize(consultation),
    }


@router.post(
    "/{consultation_id}/cancel",
    response_model=ConsultationActionResponseSchema,
    summary="Cancel a consultation",
)
def cancel_consultation(
    consultation_id: int,
    actor: CurrentActiveUser,
    service: Annotated[ConsultationService, Depends(get_consultation_service)],
    _: Annotated[User, Depends(require_permission("CONSULTATION_WRITE"))],
    reason: Optional[str] = Query(None, max_length=500),
):
    consultation = service.cancel(consultation_id, reason=reason, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Consultation cancelled.",
        "consultation": _serialize(consultation),
    }
