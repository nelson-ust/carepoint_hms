# app/api/v1/endpoints/meal_routes.py
from __future__ import annotations

"""
FastAPI routes for Dietary & Meal Management.
Allows cataloging meals and tracking patient/caregiver meal orders with billing.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.meal_schemas import (
    MealOrderActionResponse,
    MealOrderCreate,
    MealOrderListResponse,
    MealOrderRead,
    MealTypeActionResponse,
    MealTypeCreate,
    MealTypeRead,
)
from app.services.meal_service import MealService
from app.utils.pagination import paginate_response

router = APIRouter(prefix="/meals", tags=["Dietary & Meals"])


# --- Service factory -------------------------------------------------------

def get_meal_service(db: Annotated[Session, Depends(get_db)]) -> MealService:
    return MealService(db)


# ============================================================
# MEAL TYPES (CATALOG)
# ============================================================

@router.get(
    "/types",
    response_model=list[MealTypeRead],
    summary="List available meal types",
)
def list_meal_types(
    service: Annotated[MealService, Depends(get_meal_service)],
    _: Annotated[User, Depends(require_permission("MEAL_READ"))],
):
    """Fetch the catalog of meals served by the hospital."""
    return service.list_meal_types()


@router.post(
    "/types",
    response_model=MealTypeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new meal type",
)
def create_meal_type(
    payload: MealTypeCreate,
    service: Annotated[MealService, Depends(get_meal_service)],
    _: Annotated[User, Depends(require_permission("MEAL_MANAGE"))],
):
    """Add a new meal (e.g. 'Standard Lunch') to the hospital catalog."""
    return service.create_meal_type(payload)


# ============================================================
# MEAL ORDERS
# ============================================================

@router.get(
    "/orders",
    response_model=MealOrderListResponse,
    summary="List meal orders",
)
def list_meal_orders(
    service: Annotated[MealService, Depends(get_meal_service)],
    _: Annotated[User, Depends(require_permission("MEAL_READ"))],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    visit_id: Optional[int] = Query(None),
    patient_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None, description="ORDERED, SERVED, CANCELLED"),
):
    """Retrieve meal orders with optional filtering by patient or visit."""
    items, total = service.list_orders(
        skip=skip, limit=limit, 
        visit_id=visit_id, patient_id=patient_id, status=status
    )
    return paginate_response(
        items=items,
        total=total, skip=skip, limit=limit,
        message="Meal orders fetched successfully."
    )


@router.post(
    "/orders",
    response_model=MealOrderActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Place a meal order",
)
def place_order(
    payload: MealOrderCreate,
    actor: CurrentActiveUser,
    service: Annotated[MealService, Depends(get_meal_service)],
    _: Annotated[User, Depends(require_permission("MEAL_ORDER"))],
):
    """
    Record a meal request for a patient or caregiver. 
    Note: Charges are NOT added to the bill until the meal is marked as SERVED.
    """
    order = service.place_order(payload, actor_staff_id=actor.id)
    return {
        "success": True, 
        "message": "Meal order placed successfully.", 
        "meal_order": order
    }


@router.post(
    "/orders/{order_id}/serve",
    response_model=MealOrderActionResponse,
    summary="Mark meal as served",
)
def serve_meal(
    order_id: int,
    actor: CurrentActiveUser,
    service: Annotated[MealService, Depends(get_meal_service)],
    _: Annotated[User, Depends(require_permission("MEAL_SERVE"))],
):
    """
    Mark a meal as served. 
    CRITICAL: This action automatically adds the meal charge to the patient's bill.
    """
    order = service.serve_meal(order_id, actor_staff_id=actor.id)
    return {
        "success": True, 
        "message": "Meal served and charged to patient bill.", 
        "meal_order": order
    }


@router.post(
    "/orders/{order_id}/cancel",
    response_model=MealOrderActionResponse,
    summary="Cancel a meal order",
)
def cancel_order(
    order_id: int,
    service: Annotated[MealService, Depends(get_meal_service)],
    _: Annotated[User, Depends(require_permission("MEAL_ORDER"))],
):
    """Cancel an order before it is served. Served meals cannot be cancelled."""
    order = service.cancel_order(order_id)
    return {
        "success": True, 
        "message": "Meal order cancelled.", 
        "meal_order": order
    }
