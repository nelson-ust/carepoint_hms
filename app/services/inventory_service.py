# app/services/inventory_service.py
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import InventoryItemType
from app.models.all_models import InventoryStockItem, InventoryStore
from app.repositories.inventory_repository import (
    InventoryStockItemRepository,
    InventoryStoreRepository,
)
from app.schemas.inventory_schema import (
    InventoryStockItemCreateSchema,
    InventoryStockItemUpdateSchema,
    InventoryStoreCreateSchema,
    InventoryStoreUpdateSchema,
)


class InventoryStoreService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = InventoryStoreRepository(db)

    def list(self, *, skip=0, limit=50, search=None):
        return self.repository.list_stores(skip=skip, limit=limit, search=search)

    def get(self, store_id: int) -> InventoryStore:
        return self.repository.get_required_by_id(store_id)

    def create(self, payload: InventoryStoreCreateSchema) -> InventoryStore:
        s = self.repository.create(
            name=payload.name,
            code=payload.code,
            location_description=payload.location_description,
            description=payload.description,
        )
        self.db.commit()
        return self.repository.get_required_by_id(s.id)

    def update(self, store_id: int, payload: InventoryStoreUpdateSchema) -> InventoryStore:
        s = self.repository.get_required_by_id(store_id)
        updated = self.repository.update(s, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def soft_delete(self, store_id: int) -> InventoryStore:
        s = self.repository.get_required_by_id(store_id)
        deleted = self.repository.soft_delete(s)
        self.db.commit()
        return deleted


class InventoryStockItemService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = InventoryStockItemRepository(db)
        self.store_repository = InventoryStoreRepository(db)

    def list(
        self,
        *,
        skip=0,
        limit=50,
        store_id: Optional[int] = None,
        drug_id: Optional[int] = None,
        item_type: Optional[str] = None,
        only_low_stock: bool = False,
        only_expiring_within_days: Optional[int] = None,
        search: Optional[str] = None,
    ):
        item_type_enum = InventoryItemType(item_type) if item_type else None
        return self.repository.list_items(
            skip=skip, limit=limit, search=search,
            store_id=store_id, drug_id=drug_id, item_type=item_type_enum,
            only_low_stock=only_low_stock,
            only_expiring_within_days=only_expiring_within_days,
        )

    def get(self, item_id: int) -> InventoryStockItem:
        return self.repository.get_required_by_id(item_id)

    def create(self, payload: InventoryStockItemCreateSchema) -> InventoryStockItem:
        self.store_repository.get_required_by_id(payload.store_id)
        i = self.repository.create(**payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(i.id)

    def update(self, item_id: int, payload: InventoryStockItemUpdateSchema) -> InventoryStockItem:
        i = self.repository.get_required_by_id(item_id)
        updated = self.repository.update(i, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def soft_delete(self, item_id: int) -> InventoryStockItem:
        i = self.repository.get_required_by_id(item_id)
        deleted = self.repository.soft_delete(i)
        self.db.commit()
        return deleted
