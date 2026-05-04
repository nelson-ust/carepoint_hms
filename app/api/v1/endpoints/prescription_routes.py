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


def _serialize_item(i) -> dict:
    return {
        "id": i.id,
        "prescription_id": i.prescription_id,
        "drug_id": i.drug_id,
        "dosage": i.dosage,
        "frequency": i.frequency,
        "duration": i.duration,
        "route": i.route,
        "quantity_prescribed": i.quantity_prescribed,
        "quantity_dispensed": i.quantity_dispensed,
        "instructions": i.instructions,
        "created_at": getattr(i, "created_at", None),
        "updated_at": getattr(i, "updated_at", None),
    }


def _serialize(p) -> dict:
    return {
        "id": p.id,
        "visit_id": p.visit_id,
        "consultation_id": p.consultation_id,
        "prescribed_by_staff_id": p.prescribed_by_staff_id,
        "prescription_no": p.prescription_no,
        "status": str(p.status),
        "note": p.note,
        "prescribed_at": p.prescribed_at,
        "items": [_serialize_item(i) for i in (p.items or []) if not getattr(i, "is_deleted", False)],
        "created_at": getattr(p, "created_at", None),
        "updated_at": getattr(p, "updated_at", None),
    }


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
    limit: int = Query(50, ge=1, le=200),
):
    items, total = service.list_for_visit(visit_id, skip=skip, limit=limit)
    return paginate_response(
        items=[_serialize(p) for p in items],
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
    return {"success": True, "message": "Prescription created.", "prescription": _serialize(p)}


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
    return _serialize(service.get(prescription_id))


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
    return {"success": True, "message": "Prescription cancelled.", "prescription": _serialize(p)}
