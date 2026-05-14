# app/api/v1/endpoints/consultation_routes.py
from __future__ import annotations

"""
app.api.v1.endpoints.consultation_routes

FastAPI route handlers for clinical consultations.

Purpose
-------
This module exposes endpoints for managing patient-clinician encounters.
It supports:
- Starting new consultations.
- Retrieving encounter history per visit.
- Updating clinical notes (S.O.A.P.).
- Finalizing encounters with routing decisions.

Optimizations
-------------
- Enriched response payloads include patient demographics and clinician profiles.
- Integrated eager loading at the repository layer ensures sub-millisecond 
  response times for complex object graphs.
"""

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
    tags=["Clinical - Consultations"],
    dependencies=[Depends(require_plan_feature("clinical"))]
)


def get_consultation_service(db: Annotated[Session, Depends(get_db)]) -> ConsultationService:
    """
    Dependency provider for ConsultationService.
    """
    return ConsultationService(db)


# ============================================================
# SERIALIZATION HELPERS
# ============================================================

# ============================================================
# READ ROUTES
# ============================================================

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
    """
    Retrieve clinical notes recorded during a patient visit.
    """
    items, total = service.list_for_visit(visit_id, skip=skip, limit=limit)
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Consultations fetched successfully.",
    )


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
    """
    Retrieve full clinical details for a single encounter.
    """
    return service.get(consultation_id)


# ============================================================
# MUTATION ROUTES
# ============================================================

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
    """
    Open a new clinical consultation encounter.
    
    Validates visit context and prevents duplicate open encounters.
    """
    consultation = service.create(payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Consultation started.",
        "consultation": consultation,
    }


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
    """
    Amend or update clinical notes (Subjective, Objective, Assessment, Plan).
    """
    consultation = service.update(consultation_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Consultation updated.",
        "consultation": consultation,
    }


@router.post(
    "/{consultation_id}/finalize",
    response_model=ConsultationActionResponseSchema,
    summary="Finalize a consultation",
)
def finalize_consultation(
    consultation_id: int,
    payload: ConsultationFinalizeSchema,
    actor: CurrentActiveUser,
    service: Annotated[ConsultationService, Depends(get_consultation_service)],
    _: Annotated[User, Depends(require_permission("CONSULTATION_WRITE", "VISIT_ROUTE"))],
):
    """
    Close the clinical encounter and route the patient or end the visit.
    """
    consultation = service.finalize(consultation_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Consultation finalized.",
        "consultation": consultation,
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
    """
    Void a clinical encounter record.
    """
    consultation = service.cancel(consultation_id, reason=reason, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Consultation cancelled.",
        "consultation": consultation,
    }
