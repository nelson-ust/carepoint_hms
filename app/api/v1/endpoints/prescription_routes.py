# app/api/v1/endpoints/prescription_routes.py
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.prescription_schema import (
    PrescriptionActionResponseSchema,
    PrescriptionCancelSchema,
    PrescriptionCreateSchema,
    PrescriptionListResponseSchema,
    PrescriptionReadSchema,
)
from app.services.prescription_service import PrescriptionService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/prescriptions", 
    tags=["Prescriptions"],
    dependencies=[Depends(require_plan_feature("clinical"))]
)


def get_prescription_service(db: Annotated[Session, Depends(get_db)]) -> PrescriptionService:
    return PrescriptionService(db)


# ============================================================
# READ
# ============================================================


@router.get(
    "/visits/{visit_id}",
    response_model=PrescriptionListResponseSchema,
    summary="List prescriptions for a visit",
)
def list_for_visit(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("PRESCRIPTION_WRITE", "PRESCRIPTION_DISPENSE", "VISIT_READ"))],
    service: Annotated[PrescriptionService, Depends(get_prescription_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
):
    items, total = service.list_for_visit(visit_id, skip=skip, limit=limit)
    return paginate_response(
        items=items,
        total=total, skip=skip, limit=limit,
        message="Prescriptions fetched successfully.",
    )


@router.post(
    "/",
    response_model=PrescriptionActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Author a prescription",
)
def create_prescription(
    payload: PrescriptionCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[PrescriptionService, Depends(get_prescription_service)],
    _: Annotated[User, Depends(require_permission("PRESCRIPTION_WRITE"))],
):
    p = service.create_prescription(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Prescription created.", "prescription": p}


@router.get(
    "/{prescription_id}",
    response_model=PrescriptionReadSchema,
    summary="Get a prescription",
)
def get_prescription(
    prescription_id: int,
    _: Annotated[User, Depends(require_permission("PRESCRIPTION_WRITE", "PRESCRIPTION_DISPENSE"))],
    service: Annotated[PrescriptionService, Depends(get_prescription_service)],
):
    return service.get(prescription_id)


@router.post(
    "/{prescription_id}/cancel",
    response_model=PrescriptionActionResponseSchema,
    summary="Cancel a prescription",
)
def cancel_prescription(
    prescription_id: int,
    payload: PrescriptionCancelSchema,
    actor: CurrentActiveUser,
    service: Annotated[PrescriptionService, Depends(get_prescription_service)],
    _: Annotated[User, Depends(require_permission("PRESCRIPTION_WRITE"))],
):
    p = service.cancel_prescription(prescription_id, reason=payload.reason, actor_user_id=actor.id)
    return {"success": True, "message": "Prescription cancelled.", "prescription": p}
