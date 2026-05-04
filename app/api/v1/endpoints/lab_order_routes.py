# app/api/v1/endpoints/lab_order_routes.py
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.lab_order_schema import (
    LabOrderActionResponseSchema,
    LabOrderCancelSchema,
    LabOrderCreateSchema,
    LabOrderItemSpecimenSchema,
    LabOrderListResponseSchema,
    LabOrderReadSchema,
)
from app.services.lab_order_service import LabOrderService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/lab/orders", 
    tags=["Laboratory - Orders"],
    dependencies=[Depends(require_plan_feature("laboratory"))]
)


def get_lab_order_service(db: Annotated[Session, Depends(get_db)]) -> LabOrderService:
    return LabOrderService(db)


def _serialize_item(item) -> dict:
    return {
        "id": item.id,
        "lab_order_id": item.lab_order_id,
        "lab_test_catalog_id": item.lab_test_catalog_id,
        "status": str(item.status),
        "specimen_id": item.specimen_id,
        "sample_collected_at": item.sample_collected_at,
        "collected_by_staff_id": item.collected_by_staff_id,
        "created_at": getattr(item, "created_at", None),
        "updated_at": getattr(item, "updated_at", None),
    }


def _serialize(order) -> dict:
    return {
        "id": order.id,
        "visit_id": order.visit_id,
        "consultation_id": order.consultation_id,
        "ordered_by_staff_id": order.ordered_by_staff_id,
        "order_no": order.order_no,
        "status": str(order.status),
        "clinical_note": order.clinical_note,
        "ordered_at": order.ordered_at,
        "items": [_serialize_item(i) for i in (order.items or []) if not getattr(i, "is_deleted", False)],
        "created_at": getattr(order, "created_at", None),
        "updated_at": getattr(order, "updated_at", None),
    }


@router.get(
    "/visits/{visit_id}",
    response_model=LabOrderListResponseSchema,
    summary="List lab orders for a visit",
)
def list_for_visit(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("LAB_ORDER_CREATE", "LAB_RESULT_ENTER", "VISIT_READ"))],
    service: Annotated[LabOrderService, Depends(get_lab_order_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    items, total = service.list_for_visit(visit_id, skip=skip, limit=limit)
    return paginate_response(
        items=[_serialize(o) for o in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Lab orders fetched successfully.",
    )


@router.get(
    "/worklist",
    response_model=LabOrderListResponseSchema,
    summary="Lab worklist (open orders)",
)
def list_worklist(
    _: Annotated[User, Depends(require_permission("LAB_RESULT_ENTER"))],
    service: Annotated[LabOrderService, Depends(get_lab_order_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    statuses: Optional[list[str]] = Query(
        None, description="ORDERED, SAMPLE_COLLECTED, IN_PROGRESS, RESULT_READY, COMPLETED, CANCELLED."
    ),
):
    items, total = service.list_lab_worklist(skip=skip, limit=limit, statuses=statuses)
    return paginate_response(
        items=[_serialize(o) for o in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Lab worklist fetched successfully.",
    )


@router.post(
    "/",
    response_model=LabOrderActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a lab order",
)
def create_order(
    payload: LabOrderCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[LabOrderService, Depends(get_lab_order_service)],
    _: Annotated[User, Depends(require_permission("LAB_ORDER_CREATE"))],
):
    order = service.create_order(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Lab order created.", "lab_order": _serialize(order)}


@router.get(
    "/{order_id}",
    response_model=LabOrderReadSchema,
    summary="Get a lab order",
)
def get_order(
    order_id: int,
    _: Annotated[User, Depends(require_permission("LAB_ORDER_CREATE", "LAB_RESULT_ENTER", "VISIT_READ"))],
    service: Annotated[LabOrderService, Depends(get_lab_order_service)],
):
    return _serialize(service.get(order_id))


@router.post(
    "/items/{item_id}/collect-specimen",
    response_model=LabOrderActionResponseSchema,
    summary="Record specimen collection for a lab order item",
)
def collect_specimen(
    item_id: int,
    payload: LabOrderItemSpecimenSchema,
    actor: CurrentActiveUser,
    service: Annotated[LabOrderService, Depends(get_lab_order_service)],
    _: Annotated[User, Depends(require_permission("LAB_RESULT_ENTER"))],
):
    item = service.collect_specimen(item_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Specimen collected.",
        "lab_order": _serialize(service.get(item.lab_order_id)),
    }


@router.post(
    "/items/{item_id}/start-processing",
    response_model=LabOrderActionResponseSchema,
    summary="Start processing a lab order item",
)
def start_processing(
    item_id: int,
    actor: CurrentActiveUser,
    service: Annotated[LabOrderService, Depends(get_lab_order_service)],
    _: Annotated[User, Depends(require_permission("LAB_RESULT_ENTER"))],
):
    item = service.start_processing(item_id, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Processing started.",
        "lab_order": _serialize(service.get(item.lab_order_id)),
    }


@router.post(
    "/items/{item_id}/cancel",
    response_model=LabOrderActionResponseSchema,
    summary="Cancel a single lab order item",
)
def cancel_item(
    item_id: int,
    payload: LabOrderCancelSchema,
    actor: CurrentActiveUser,
    service: Annotated[LabOrderService, Depends(get_lab_order_service)],
    _: Annotated[User, Depends(require_permission("LAB_ORDER_CREATE"))],
):
    item = service.cancel_item(item_id, reason=payload.reason, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Lab order item cancelled.",
        "lab_order": _serialize(service.get(item.lab_order_id)),
    }


@router.post(
    "/{order_id}/cancel",
    response_model=LabOrderActionResponseSchema,
    summary="Cancel a lab order",
)
def cancel_order(
    order_id: int,
    payload: LabOrderCancelSchema,
    actor: CurrentActiveUser,
    service: Annotated[LabOrderService, Depends(get_lab_order_service)],
    _: Annotated[User, Depends(require_permission("LAB_ORDER_CREATE"))],
):
    order = service.cancel_order(order_id, reason=payload.reason, actor_user_id=actor.id)
    return {"success": True, "message": "Lab order cancelled.", "lab_order": _serialize(order)}
