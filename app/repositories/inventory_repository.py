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
    """Repository for physical or logical inventory stores."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, store_id: int) -> Optional[InventoryStore]:
        """Fetch a store by its primary key if not deleted."""
        return (
            self.db.query(InventoryStore)
            .filter(InventoryStore.id == store_id, InventoryStore.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, store_id: int) -> InventoryStore:
        """Fetch a store by ID or raise NotFoundError."""
        s = self.get_by_id(store_id)
        if not s:
            raise NotFoundError(message="Store not found.", detail={"store_id": store_id})
        return s

    def get_by_code(self, code: str) -> Optional[InventoryStore]:
        """Fetch a store by its unique alphanumeric code."""
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
        """Return a paginated list of active stores with optional search."""
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
        """Persist a new store, ensuring code uniqueness."""
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
        """Update fields of an existing store record."""
        for field, value in kwargs.items():
            if value is not None:
                setattr(s, field, value)
        self.db.add(s)
        self.db.flush()
        self.db.refresh(s)
        return s

    def soft_delete(self, s: InventoryStore) -> InventoryStore:
        """Mark a store as deleted (logical delete)."""
        s.is_deleted = True
        self.db.add(s)
        self.db.flush()
        return s


class InventoryStockItemRepository:
    """Repository for individual trackable items within stores."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, item_id: int) -> Optional[InventoryStockItem]:
        """Fetch a stock item by its primary key if not deleted."""
        return (
            self.db.query(InventoryStockItem)
            .filter(InventoryStockItem.id == item_id, InventoryStockItem.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, item_id: int) -> InventoryStockItem:
        """Fetch a stock item by ID or raise NotFoundError."""
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
        """
        Query stock items with advanced filtering for clinical and logistical workflows.
        
        Supports:
        - Store/Drug/Type filtering
        - Low stock detection (based on reorder_level)
        - Expiry date monitoring
        """
        query = self.db.query(InventoryStockItem).filter(
            InventoryStockItem.is_deleted.is_(False)
        )
        if store_id is not None:
            query = query.filter(InventoryStockItem.store_id == store_id)
        if drug_id is not None:
            query = query.filter(InventoryStockItem.drug_id == drug_id)
        if item_type is not None:
            query = query.filter(InventoryStockItem.item_type == item_type)
        
        # Low stock filter
        if only_low_stock:
            query = query.filter(
                InventoryStockItem.reorder_level.isnot(None),
                InventoryStockItem.quantity_on_hand <= InventoryStockItem.reorder_level,
            )
            
        # Expiry monitor
        if only_expiring_within_days is not None:
            from datetime import datetime, timedelta, timezone
            cutoff = (datetime.now(timezone.utc) + timedelta(days=only_expiring_within_days)).date()
            query = query.filter(InventoryStockItem.expiry_date.isnot(None))
            query = query.filter(InventoryStockItem.expiry_date <= cutoff)
            
        # Text search
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
        Pick the next stock item to dispense for a specific drug.
        
        Prioritizes:
        1. Earliest expiring (FEFO - First Expired, First Out)
        2. Highest on-hand balance (to deplete large batches)
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
        """Create a new stock record."""
        item_type = kwargs.get("item_type")
        if isinstance(item_type, str):
            kwargs["item_type"] = InventoryItemType(item_type)
        i = InventoryStockItem(**kwargs)
        self.db.add(i)
        self.db.flush()
        self.db.refresh(i)
        return i

    def update(self, i: InventoryStockItem, **kwargs) -> InventoryStockItem:
        """Update existing item metadata."""
        for field, value in kwargs.items():
            if value is not None:
                setattr(i, field, value)
        self.db.add(i)
        self.db.flush()
        self.db.refresh(i)
        return i

    def soft_delete(self, i: InventoryStockItem) -> InventoryStockItem:
        """Mark a stock item as deleted."""
        i.is_deleted = True
        self.db.add(i)
        self.db.flush()
        return i

    def adjust_quantity(self, i: InventoryStockItem, delta: Decimal) -> InventoryStockItem:
        """
        In-place quantity adjustment for an item.
        Note: This is usually called from StockMovementService.
        """
        new_quantity = (i.quantity_on_hand or Decimal("0")) + delta
        i.quantity_on_hand = new_quantity
        self.db.add(i)
        self.db.flush()
        self.db.refresh(i)
        return i


class StockMovementRepository:
    """Repository for historical audit of all stock changes."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, movement_id: int) -> Optional[StockMovement]:
        """Fetch a specific movement record."""
        from app.models.all_models import StockMovement
        return (
            self.db.query(StockMovement)
            .filter(StockMovement.id == movement_id, StockMovement.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, movement_id: int) -> StockMovement:
        """Fetch a movement by ID or raise NotFoundError."""
        m = self.get_by_id(movement_id)
        if not m:
            raise NotFoundError(message="Stock movement not found.", detail={"movement_id": movement_id})
        return m

    def list_movements(
        self,
        *,
        store_id: Optional[int] = None,
        stock_item_id: Optional[int] = None,
        movement_type: Optional[StockMovementType] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[StockMovement], int]:
        """Return historical ledger of movements with filtering."""
        from app.models.all_models import StockMovement
        query = self.db.query(StockMovement).filter(StockMovement.is_deleted.is_(False))
        if store_id is not None:
            query = query.filter(StockMovement.store_id == store_id)
        if stock_item_id is not None:
            query = query.filter(StockMovement.stock_item_id == stock_item_id)
        if movement_type is not None:
            query = query.filter(StockMovement.movement_type == movement_type)

        total = query.with_entities(func.count(StockMovement.id)).scalar() or 0
        items = (
            query.order_by(StockMovement.movement_date.desc(), StockMovement.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def create(self, **kwargs) -> StockMovement:
        """Persist a movement record and set the balance timestamp."""
        from datetime import datetime, timezone
        from app.models.all_models import StockMovement
        from app.core.enums import StockMovementType

        m_type = kwargs.get("movement_type")
        if isinstance(m_type, str):
            kwargs["movement_type"] = StockMovementType(m_type)
        
        if "movement_date" not in kwargs:
            kwargs["movement_date"] = datetime.now(timezone.utc)

        m = StockMovement(**kwargs)
        self.db.add(m)
        self.db.flush()
        self.db.refresh(m)
        return m
