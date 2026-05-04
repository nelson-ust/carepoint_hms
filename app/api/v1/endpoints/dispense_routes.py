# app/api/v1/endpoints/dispense_routes.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.dispense_schema import (
    DispenseActionResponseSchema,
    DispenseCreateSchema,
    DispenseListResponseSchema,
    DispenseReadSchema,
)
from app.services.dispense_service import DispenseService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/dispenses", 
    tags=["Dispenses"],
    dependencies=[Depends(require_plan_feature("pharmacy"))]
)


def get_dispense_service(db: Annotated[Session, Depends(get_db)]) -> DispenseService:
    return DispenseService(db)


def _serialize_item(i) -> dict:
    return {
        "id": i.id,
        "dispense_id": i.dispense_id,
        "prescription_item_id": i.prescription_item_id,
        "quantity_dispensed": i.quantity_dispensed,
        "note": i.note,
        "created_at": getattr(i, "created_at", None),
    }


def _serialize(d) -> dict:
    return {
        "id": d.id,
        "prescription_id": d.prescription_id,
        "dispensed_by_staff_id": d.dispensed_by_staff_id,
        "dispense_no": d.dispense_no,
        "status": str(d.status),
        "dispensed_at": d.dispensed_at,
        "note": d.note,
        "items": [_serialize_item(i) for i in (d.items or []) if not getattr(i, "is_deleted", False)],
        "created_at": getattr(d, "created_at", None),
        "updated_at": getattr(d, "updated_at", None),
    }


@router.post(
    "/",
    response_model=DispenseActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Dispense from a prescription",
)
def create_dispense(
    payload: DispenseCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[DispenseService, Depends(get_dispense_service)],
    _: Annotated[User, Depends(require_permission("PRESCRIPTION_DISPENSE"))],
):
    d = service.create_dispense(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Dispense recorded.", "dispense": _serialize(d)}


@router.get(
    "/visits/{visit_id}",
    response_model=DispenseListResponseSchema,
    summary="List dispenses for a visit",
)
def list_for_visit(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("PRESCRIPTION_DISPENSE", "VISIT_READ"))],
    service: Annotated[DispenseService, Depends(get_dispense_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    items, total = service.list_for_visit(visit_id, skip=skip, limit=limit)
    return paginate_response(
        items=[_serialize(d) for d in items],
        total=total, skip=skip, limit=limit,
        message="Dispenses fetched successfully.",
    )


@router.get(
    "/prescriptions/{prescription_id}",
    response_model=DispenseListResponseSchema,
    summary="List dispenses for a prescription",
)
def list_for_prescription(
    prescription_id: int,
    _: Annotated[User, Depends(require_permission("PRESCRIPTION_DISPENSE", "PRESCRIPTION_WRITE"))],
    service: Annotated[DispenseService, Depends(get_dispense_service)],
):
    items = service.list_for_prescription(prescription_id)
    return paginate_response(
        items=[_serialize(d) for d in items],
        total=len(items),
        skip=0,
        limit=len(items) or 1,
        message="Dispenses fetched successfully.",
    )


@router.get(
    "/{dispense_id}",
    response_model=DispenseReadSchema,
    summary="Get a dispense",
)
def get_dispense(
    dispense_id: int,
    _: Annotated[User, Depends(require_permission("PRESCRIPTION_DISPENSE", "PRESCRIPTION_WRITE"))],
    service: Annotated[DispenseService, Depends(get_dispense_service)],
):
    return _serialize(service.get(dispense_id))
