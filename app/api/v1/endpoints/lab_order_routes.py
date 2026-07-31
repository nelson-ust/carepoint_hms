# app/api/v1/endpoints/lab_order_routes.py
from __future__ import annotations

"""
app.api.v1.endpoints.lab_order_routes

FastAPI route handlers for Laboratory Order management.

Purpose
-------
This module exposes endpoints for:
- Creating and managing laboratory orders within patient visits.
- Retrieving lab worklists for processing.
- Recording specimen collection and analytical phase transitions.
- Cancelling orders or specific line items.

Security
--------
- Requires the "laboratory" plan feature to be enabled for the tenant.
- Enforces fine-grained permissions (LAB_ORDER_CREATE, LAB_RESULT_ENTER, VISIT_READ).
- Automatically records security events for mutative actions (creation, cancellation).
"""

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
    """
    Dependency provider for LabOrderService.
    """
    return LabOrderService(db)


# ============================================================
# READ ROUTES
# ============================================================

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
    limit: int = Query(50, ge=1, le=1000),
):
    """
    Retrieve all laboratory orders associated with a specific visit ID.
    """
    items, total = service.list_for_visit(visit_id, skip=skip, limit=limit)
    return paginate_response(
        items=items,
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
    limit: int = Query(50, ge=1, le=1000),
    statuses: Optional[list[str]] = Query(
        None, description="Filter by: ORDERED, SAMPLE_COLLECTED, IN_PROGRESS, RESULT_READY, COMPLETED, CANCELLED."
    ),
):
    """
    Retrieve a worklist of active laboratory orders for processing.
    
    Defaults to orders that are not yet COMPLETED or CANCELLED.
    """
    items, total = service.list_lab_worklist(skip=skip, limit=limit, statuses=statuses)
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Lab worklist fetched successfully.",
    )


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
    """
    Retrieve full details for a single laboratory order by its ID.
    """
    return service.get(order_id)


# ============================================================
# MUTATION ROUTES
# ============================================================

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
    """
    Initiate a new laboratory order for a visit.
    """
    order = service.create_order(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Lab order created.", "lab_order": order}


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
    """
    Record biological specimen collection for a specific test item.
    """
    item = service.collect_specimen(item_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Specimen collected.",
        "lab_order": service.get(item.lab_order_id),
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
    """
    Mark a lab order item as having entered the analytical processing phase.
    """
    item = service.start_processing(item_id, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Processing started.",
        "lab_order": service.get(item.lab_order_id),
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
    """
    Cancel a single laboratory test within an order.
    """
    item = service.cancel_item(item_id, reason=payload.reason, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Lab order item cancelled.",
        "lab_order": service.get(item.lab_order_id),
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
    """
    Cancel an entire laboratory order and all its non-terminal items.
    """
    order = service.cancel_order(order_id, reason=payload.reason, actor_user_id=actor.id)
    return {"success": True, "message": "Lab order cancelled.", "lab_order": order}
