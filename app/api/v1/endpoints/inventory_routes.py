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
)
from app.services.inventory_service import (
    InventoryStockItemService,
    InventoryStoreService,
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


def _serialize_store(s) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "code": s.code,
        "location_description": s.location_description,
        "description": s.description,
        "created_at": getattr(s, "created_at", None),
        "updated_at": getattr(s, "updated_at", None),
    }


def _serialize_item(i) -> dict:
    return {
        "id": i.id,
        "store_id": i.store_id,
        "drug_id": i.drug_id,
        "item_type": str(i.item_type),
        "item_name": i.item_name,
        "sku": i.sku,
        "unit_of_measure": i.unit_of_measure,
        "quantity_on_hand": i.quantity_on_hand,
        "reorder_level": i.reorder_level,
        "unit_cost": i.unit_cost,
        "expiry_date": i.expiry_date,
        "batch_no": i.batch_no,
        "created_at": getattr(i, "created_at", None),
        "updated_at": getattr(i, "updated_at", None),
    }


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
    items, total = service.list(skip=skip, limit=limit, search=search)
    return paginate_response(
        items=[_serialize_store(s) for s in items],
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
    s = service.create(payload)
    return {"success": True, "message": "Store created.", "store": _serialize_store(s)}


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
    return _serialize_store(service.get(store_id))


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
    s = service.update(store_id, payload)
    return {"success": True, "message": "Store updated.", "store": _serialize_store(s)}


@router.delete(
    "/stores/{store_id}",
    summary="Soft-delete a store",
)
def delete_store(
    store_id: int,
    _: Annotated[User, Depends(require_permission("INVENTORY_MANAGE"))],
    service: Annotated[InventoryStoreService, Depends(get_store_service)],
):
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
    items, total = service.list(
        skip=skip, limit=limit, search=search,
        store_id=store_id, drug_id=drug_id, item_type=item_type,
        only_low_stock=only_low_stock,
        only_expiring_within_days=only_expiring_within_days,
    )
    return paginate_response(
        items=[_serialize_item(i) for i in items],
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
    i = service.create(payload)
    return {"success": True, "message": "Stock item created.", "stock_item": _serialize_item(i)}


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
    return _serialize_item(service.get(item_id))


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
    i = service.update(item_id, payload)
    return {"success": True, "message": "Stock item updated.", "stock_item": _serialize_item(i)}


@router.delete(
    "/items/{item_id}",
    summary="Soft-delete a stock item",
)
def delete_item(
    item_id: int,
    _: Annotated[User, Depends(require_permission("INVENTORY_MANAGE"))],
    service: Annotated[InventoryStockItemService, Depends(get_stock_item_service)],
):
    i = service.soft_delete(item_id)
    return {"success": True, "message": "Stock item deactivated.", "stock_item_id": i.id}
