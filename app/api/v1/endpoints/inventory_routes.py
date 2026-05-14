# app/api/v1/endpoints/inventory_routes.py
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.inventory_schema import (
    InventoryStockItemActionResponseSchema,
    InventoryStockItemCreateSchema,
    InventoryStockItemListResponseSchema,
    InventoryStockItemReadSchema,
    InventoryStockItemUpdateSchema,
    InventoryStoreActionResponseSchema,
    InventoryStoreCreateSchema,
    InventoryStoreListResponseSchema,
    InventoryStoreReadSchema,
    InventoryStoreUpdateSchema,
    StockMovementActionResponseSchema,
    StockMovementCreateSchema,
    StockMovementListResponseSchema,
    StockMovementReadSchema,
)
from app.services.inventory_service import (
    InventoryStockItemService,
    InventoryStoreService,
    StockMovementService,
)
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/inventory", 
    tags=["Inventory"],
    dependencies=[Depends(require_plan_feature("inventory"))]
)


def get_store_service(db: Annotated[Session, Depends(get_db)]) -> InventoryStoreService:
    return InventoryStoreService(db)


def get_stock_item_service(db: Annotated[Session, Depends(get_db)]) -> InventoryStockItemService:
    return InventoryStockItemService(db)


def get_movement_service(db: Annotated[Session, Depends(get_db)]) -> StockMovementService:
    return StockMovementService(db)


# ============================================================
# READ
# ============================================================

# ----- STORES -----

@router.get(
    "/stores",
    response_model=InventoryStoreListResponseSchema,
    summary="List inventory stores",
)
def list_stores(
    _: Annotated[User, Depends(require_permission("INVENTORY_READ"))],
    service: Annotated[InventoryStoreService, Depends(get_store_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
):
    """
    Fetch a paginated list of all inventory stores.
    
    Permissions: INVENTORY_READ
    """
    items, total = service.list(skip=skip, limit=limit, search=search)
    return paginate_response(
        items=items,
        total=total, skip=skip, limit=limit,
        message="Inventory stores fetched successfully.",
    )


@router.post(
    "/stores",
    response_model=InventoryStoreActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create an inventory store",
)
def create_store(
    payload: InventoryStoreCreateSchema,
    _: Annotated[User, Depends(require_permission("INVENTORY_MANAGE"))],
    service: Annotated[InventoryStoreService, Depends(get_store_service)],
):
    """
    Register a new inventory store (e.g., Pharmacy, Lab Store).
    
    Permissions: INVENTORY_MANAGE
    """
    s = service.create(payload)
    return {"success": True, "message": "Store created.", "store": s}


@router.get(
    "/stores/{store_id}",
    response_model=InventoryStoreReadSchema,
    summary="Get a store",
)
def get_store(
    store_id: int,
    _: Annotated[User, Depends(require_permission("INVENTORY_READ"))],
    service: Annotated[InventoryStoreService, Depends(get_store_service)],
):
    """
    Retrieve details of a specific store.
    
    Permissions: INVENTORY_READ
    """
    return service.get(store_id)


@router.put(
    "/stores/{store_id}",
    response_model=InventoryStoreActionResponseSchema,
    summary="Update a store",
)
def update_store(
    store_id: int,
    payload: InventoryStoreUpdateSchema,
    _: Annotated[User, Depends(require_permission("INVENTORY_MANAGE"))],
    service: Annotated[InventoryStoreService, Depends(get_store_service)],
):
    """
    Update store name or description.
    
    Permissions: INVENTORY_MANAGE
    """
    s = service.update(store_id, payload)
    return {"success": True, "message": "Store updated.", "store": s}


@router.delete(
    "/stores/{store_id}",
    summary="Soft-delete a store",
)
def delete_store(
    store_id: int,
    _: Annotated[User, Depends(require_permission("INVENTORY_MANAGE"))],
    service: Annotated[InventoryStoreService, Depends(get_store_service)],
):
    """
    Mark a store as inactive.
    
    Permissions: INVENTORY_MANAGE
    """
    s = service.soft_delete(store_id)
    return {"success": True, "message": "Store deactivated.", "store_id": s.id}


# ----- STOCK ITEMS -----

@router.get(
    "/items",
    response_model=InventoryStockItemListResponseSchema,
    summary="List stock items",
)
def list_items(
    _: Annotated[User, Depends(require_permission("INVENTORY_READ"))],
    service: Annotated[InventoryStockItemService, Depends(get_stock_item_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    store_id: Optional[int] = Query(None),
    drug_id: Optional[int] = Query(None),
    item_type: Optional[str] = Query(None),
    only_low_stock: bool = Query(False),
    only_expiring_within_days: Optional[int] = Query(None, ge=0, le=365),
    search: Optional[str] = Query(None),
):
    """
    Search and filter stock items across all stores.
    
    Includes filters for:
    - store_id: Find items in a specific department
    - only_low_stock: Find items below reorder level
    - only_expiring_within_days: Find items nearing expiry
    
    Permissions: INVENTORY_READ
    """
    items, total = service.list(
        skip=skip, limit=limit, search=search,
        store_id=store_id, drug_id=drug_id, item_type=item_type,
        only_low_stock=only_low_stock,
        only_expiring_within_days=only_expiring_within_days,
    )
    return paginate_response(
        items=items,
        total=total, skip=skip, limit=limit,
        message="Stock items fetched successfully.",
    )


@router.post(
    "/items",
    response_model=InventoryStockItemActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a stock item",
)
def create_item(
    payload: InventoryStockItemCreateSchema,
    _: Annotated[User, Depends(require_permission("INVENTORY_MANAGE"))],
    service: Annotated[InventoryStockItemService, Depends(get_stock_item_service)],
):
    """
    Register a specific batch/item in a store.
    
    Permissions: INVENTORY_MANAGE
    """
    i = service.create(payload)
    return {"success": True, "message": "Stock item created.", "stock_item": i}


@router.get(
    "/items/{item_id}",
    response_model=InventoryStockItemReadSchema,
    summary="Get a stock item",
)
def get_item(
    item_id: int,
    _: Annotated[User, Depends(require_permission("INVENTORY_READ"))],
    service: Annotated[InventoryStockItemService, Depends(get_stock_item_service)],
):
    """
    Retrieve current balance and metadata for a stock item.
    
    Permissions: INVENTORY_READ
    """
    return service.get(item_id)


@router.put(
    "/items/{item_id}",
    response_model=InventoryStockItemActionResponseSchema,
    summary="Update a stock item",
)
def update_item(
    item_id: int,
    payload: InventoryStockItemUpdateSchema,
    _: Annotated[User, Depends(require_permission("INVENTORY_MANAGE"))],
    service: Annotated[InventoryStockItemService, Depends(get_stock_item_service)],
):
    """
    Update metadata like SKU, batch number, or unit cost.
    
    Permissions: INVENTORY_MANAGE
    """
    i = service.update(item_id, payload)
    return {"success": True, "message": "Stock item updated.", "stock_item": i}


@router.delete(
    "/items/{item_id}",
    summary="Soft-delete a stock item",
)
def delete_item(
    item_id: int,
    _: Annotated[User, Depends(require_permission("INVENTORY_MANAGE"))],
    service: Annotated[InventoryStockItemService, Depends(get_stock_item_service)],
):
    """
    Mark a stock item record as deleted.
    
    Permissions: INVENTORY_MANAGE
    """
    i = service.soft_delete(item_id)
    return {"success": True, "message": "Stock item deactivated.", "stock_item_id": i.id}


# ----- STOCK MOVEMENTS -----

@router.get(
    "/movements",
    response_model=StockMovementListResponseSchema,
    summary="List stock movements",
)
def list_movements(
    _: Annotated[User, Depends(require_permission("INVENTORY_READ"))],
    service: Annotated[StockMovementService, Depends(get_movement_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    store_id: Optional[int] = Query(None),
    stock_item_id: Optional[int] = Query(None),
    movement_type: Optional[str] = Query(None),
):
    """
    Fetch historical audit of all stock movements.
    
    Permissions: INVENTORY_READ
    """
    items, total = service.list(
        skip=skip, limit=limit,
        store_id=store_id, stock_item_id=stock_item_id, movement_type=movement_type
    )
    return paginate_response(
        items=items,
        total=total, skip=skip, limit=limit,
        message="Stock movements fetched successfully.",
    )


@router.post(
    "/movements",
    response_model=StockMovementActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record a stock movement",
)
def record_movement(
    payload: StockMovementCreateSchema,
    _: Annotated[User, Depends(require_permission("INVENTORY_MANAGE"))],
    service: Annotated[StockMovementService, Depends(get_movement_service)],
):
    """
    Record a stock movement (Purchase, Issue, Dispense, etc.).
    
    This endpoint atomically updates the stock item's live balance and
    records the movement in the audit ledger.
    
    Permissions: INVENTORY_MANAGE
    """
    m = service.create(payload)
    return {"success": True, "message": "Stock movement recorded.", "movement": m}


@router.get(
    "/movements/{movement_id}",
    response_model=StockMovementReadSchema,
    summary="Get a stock movement",
)
def get_movement(
    movement_id: int,
    _: Annotated[User, Depends(require_permission("INVENTORY_READ"))],
    service: Annotated[StockMovementService, Depends(get_movement_service)],
):
    """
    Retrieve details of a specific movement event.
    
    Permissions: INVENTORY_READ
    """
    return service.get(movement_id)
