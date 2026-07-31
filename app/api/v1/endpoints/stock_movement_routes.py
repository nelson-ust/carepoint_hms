# app/api/v1/endpoints/stock_movement_routes.py
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.stock_movement_schema import (
    StockMovementActionResponseSchema,
    StockMovementCreateSchema,
    StockMovementListResponseSchema,
    StockMovementReadSchema,
    StockTransferSchema,
)
from app.services.stock_movement_service import StockMovementService
from app.utils.pagination import paginate_response

router = APIRouter(prefix="/stock-movements", tags=["Stock Movements"])


def get_stock_movement_service(db: Annotated[Session, Depends(get_db)]) -> StockMovementService:
    return StockMovementService(db)


# ============================================================
# READ
# ============================================================


@router.get(
    "/",
    response_model=StockMovementListResponseSchema,
    summary="List stock movements",
)
def list_movements(
    _: Annotated[User, Depends(require_permission("INVENTORY_READ"))],
    service: Annotated[StockMovementService, Depends(get_stock_movement_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    store_id: Optional[int] = Query(None),
    stock_item_id: Optional[int] = Query(None),
    movement_type: Optional[str] = Query(None),
):
    items, total = service.list_movements(
        skip=skip, limit=limit,
        store_id=store_id, stock_item_id=stock_item_id, movement_type=movement_type,
    )
    return paginate_response(
        items=items,
        total=total, skip=skip, limit=limit,
        message="Stock movements fetched successfully.",
    )


@router.post(
    "/",
    response_model=StockMovementActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Post a stock movement",
)
def post_movement(
    payload: StockMovementCreateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("STOCK_MOVEMENT_POST"))],
    service: Annotated[StockMovementService, Depends(get_stock_movement_service)],
):
    movement = service.post_movement(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Stock movement posted.", "movement": movement}


@router.post(
    "/transfer",
    summary="Transfer stock between stores",
)
def transfer_stock(
    payload: StockTransferSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("STOCK_MOVEMENT_POST"))],
    service: Annotated[StockMovementService, Depends(get_stock_movement_service)],
):
    result = service.transfer(payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Stock transferred.",
        "out_movement": result["out_movement"],
        "in_movement": result["in_movement"],
    }


@router.get(
    "/{movement_id}",
    response_model=StockMovementReadSchema,
    summary="Get a stock movement",
)
def get_movement(
    movement_id: int,
    _: Annotated[User, Depends(require_permission("INVENTORY_READ"))],
    service: Annotated[StockMovementService, Depends(get_stock_movement_service)],
):
    return service.get(movement_id)
