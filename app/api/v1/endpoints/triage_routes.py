# app/api/v1/endpoints/triage_routes.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.triage_schema import (
    TriageActionResponseSchema,
    TriageCreateSchema,
    TriageListResponseSchema,
    TriageReadSchema,
    TriageUpdateSchema,
)
from app.services.triage_service import TriageService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/triage", 
    tags=["Triage"],
    dependencies=[Depends(require_plan_feature("clinical"))]
)


def get_triage_service(db: Annotated[Session, Depends(get_db)]) -> TriageService:
    return TriageService(db)


# ============================================================
# READ
# ============================================================


@router.get(
    "/visits/{visit_id}",
    response_model=TriageListResponseSchema,
    summary="List triage assessments for a visit",
)
def list_for_visit(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("TRIAGE_PERFORM", "VISIT_READ"))],
    service: Annotated[TriageService, Depends(get_triage_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    items, total = service.list_for_visit(visit_id, skip=skip, limit=limit)
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Triage assessments fetched successfully.",
    )


@router.post(
    "/",
    response_model=TriageActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record a triage assessment",
)
def create_triage(
    payload: TriageCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[TriageService, Depends(get_triage_service)],
    _: Annotated[User, Depends(require_permission("TRIAGE_PERFORM"))],
):
    triage = service.create(payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Triage assessment recorded.",
        "triage": triage,
    }


@router.get(
    "/{triage_id}",
    response_model=TriageReadSchema,
    summary="Get triage assessment",
)
def get_triage(
    triage_id: int,
    _: Annotated[User, Depends(require_permission("TRIAGE_PERFORM", "VISIT_READ"))],
    service: Annotated[TriageService, Depends(get_triage_service)],
):
    return service.get(triage_id)


@router.put(
    "/{triage_id}",
    response_model=TriageActionResponseSchema,
    summary="Update triage assessment",
)
def update_triage(
    triage_id: int,
    payload: TriageUpdateSchema,
    actor: CurrentActiveUser,
    service: Annotated[TriageService, Depends(get_triage_service)],
    _: Annotated[User, Depends(require_permission("TRIAGE_PERFORM"))],
):
    triage = service.update(triage_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Triage assessment updated.",
        "triage": triage,
    }
