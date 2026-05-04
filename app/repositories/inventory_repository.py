# app/repositories/inventory_repository.py
from __future__ import annotations

"""
Repository for InventoryStore and InventoryStockItem.
"""

from datetime import date as _date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.enums import InventoryItemType
from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.all_models import InventoryStockItem, InventoryStore


class InventoryStoreRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, store_id: int) -> Optional[InventoryStore]:
        return (
            self.db.query(InventoryStore)
            .filter(InventoryStore.id == store_id, InventoryStore.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, store_id: int) -> InventoryStore:
        s = self.get_by_id(store_id)
        if not s:
            raise NotFoundError(message="Store not found.", detail={"store_id": store_id})
        return s

    def get_by_code(self, code: str) -> Optional[InventoryStore]:
        return (
            self.db.query(InventoryStore)
            .filter(
                func.upper(InventoryStore.code) == code.strip().upper(),
                InventoryStore.is_deleted.is_(False),
            )
            .first()
        )

    def list_stores(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> tuple[list[InventoryStore], int]:
        query = self.db.query(InventoryStore).filter(InventoryStore.is_deleted.is_(False))
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(InventoryStore.name).like(term),
                    func.lower(InventoryStore.code).like(term),
                )
            )
        total = query.with_entities(func.count(InventoryStore.id)).scalar() or 0
        items = query.order_by(InventoryStore.name.asc()).offset(skip).limit(limit).all()
        return items, int(total)

    def create(self, **kwargs) -> InventoryStore:
        if self.get_by_code(kwargs["code"]):
            raise AlreadyExistsError(
                message="A store with this code already exists.",
                detail={"code": kwargs["code"]},
            )
        s = InventoryStore(**kwargs)
        self.db.add(s)
        self.db.flush()
        self.db.refresh(s)
        return s

    def update(self, s: InventoryStore, **kwargs) -> InventoryStore:
        for field, value in kwargs.items():
            if value is not None:
                setattr(s, field, value)
        self.db.add(s)
        self.db.flush()
        self.db.refresh(s)
        return s

    def soft_delete(self, s: InventoryStore) -> InventoryStore:
        s.is_deleted = True
        self.db.add(s)
        self.db.flush()
        return s


class InventoryStockItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, item_id: int) -> Optional[InventoryStockItem]:
        return (
            self.db.query(InventoryStockItem)
            .filter(InventoryStockItem.id == item_id, InventoryStockItem.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, item_id: int) -> InventoryStockItem:
        i = self.get_by_id(item_id)
        if not i:
            raise NotFoundError(message="Stock item not found.", detail={"stock_item_id": item_id})
        return i

    def list_items(
        self,
        *,
        store_id: Optional[int] = None,
        drug_id: Optional[int] = None,
        item_type: Optional[InventoryItemType] = None,
        only_low_stock: bool = False,
        only_expiring_within_days: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> tuple[list[InventoryStockItem], int]:
        query = self.db.query(InventoryStockItem).filter(
            InventoryStockItem.is_deleted.is_(False)
        )
        if store_id is not None:
            query = query.filter(InventoryStockItem.store_id == store_id)
        if drug_id is not None:
            query = query.filter(InventoryStockItem.drug_id == drug_id)
        if item_type is not None:
            query = query.filter(InventoryStockItem.item_type == item_type)
        if only_low_stock:
            query = query.filter(
                InventoryStockItem.reorder_level.isnot(None),
                InventoryStockItem.quantity_on_hand <= InventoryStockItem.reorder_level,
            )
        if only_expiring_within_days is not None:
            from datetime import datetime, timedelta, timezone
            cutoff = (datetime.now(timezone.utc) + timedelta(days=only_expiring_within_days)).date()
            query = query.filter(InventoryStockItem.expiry_date.isnot(None))
            query = query.filter(InventoryStockItem.expiry_date <= cutoff)
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(InventoryStockItem.item_name).like(term),
                    func.lower(func.coalesce(InventoryStockItem.sku, "")).like(term),
                    func.lower(func.coalesce(InventoryStockItem.batch_no, "")).like(term),
                )
            )

        total = query.with_entities(func.count(InventoryStockItem.id)).scalar() or 0
        items = (
            query.order_by(InventoryStockItem.item_name.asc(), InventoryStockItem.id.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def find_first_dispensable_for_drug(
        self,
        drug_id: int,
        *,
        store_id: Optional[int] = None,
    ) -> Optional[InventoryStockItem]:
        """
        Pick the next stock item to dispense from for a drug — earliest expiring,
        then highest on-hand. Restrict to a store if specified.
        """
        query = self.db.query(InventoryStockItem).filter(
            InventoryStockItem.is_deleted.is_(False),
            InventoryStockItem.drug_id == drug_id,
            InventoryStockItem.quantity_on_hand > 0,
        )
        if store_id is not None:
            query = query.filter(InventoryStockItem.store_id == store_id)
        return (
            query.order_by(
                InventoryStockItem.expiry_date.asc().nullslast(),
                InventoryStockItem.quantity_on_hand.desc(),
            )
            .first()
        )

    def create(self, **kwargs) -> InventoryStockItem:
        item_type = kwargs.get("item_type")
        if isinstance(item_type, str):
            kwargs["item_type"] = InventoryItemType(item_type)
        i = InventoryStockItem(**kwargs)
        self.db.add(i)
        self.db.flush()
        self.db.refresh(i)
        return i

    def update(self, i: InventoryStockItem, **kwargs) -> InventoryStockItem:
        for field, value in kwargs.items():
            if value is not None:
                setattr(i, field, value)
        self.db.add(i)
        self.db.flush()
        self.db.refresh(i)
        return i

    def soft_delete(self, i: InventoryStockItem) -> InventoryStockItem:
        i.is_deleted = True
        self.db.add(i)
        self.db.flush()
        return i

    def adjust_quantity(self, i: InventoryStockItem, delta: Decimal) -> InventoryStockItem:
        new_quantity = (i.quantity_on_hand or Decimal("0")) + delta
        i.quantity_on_hand = new_quantity
        self.db.add(i)
        self.db.flush()
        self.db.refresh(i)
        return i
