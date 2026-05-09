# app/services/inventory_service.py
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import InventoryItemType
from app.models.all_models import InventoryStockItem, InventoryStore, StockMovement
from app.repositories.inventory_repository import (
    InventoryStockItemRepository,
    InventoryStoreRepository,
    StockMovementRepository,
)
from app.schemas.inventory_schema import (
    InventoryStockItemCreateSchema,
    InventoryStockItemUpdateSchema,
    InventoryStoreCreateSchema,
    InventoryStoreUpdateSchema,
    StockMovementCreateSchema,
    StockMovementReadSchema,
)


class InventoryStoreService:
    """Service for managing physical or logical inventory stores."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = InventoryStoreRepository(db)

    def list(self, *, skip=0, limit=50, search=None):
        """List stores with optional search and pagination."""
        return self.repository.list_stores(skip=skip, limit=limit, search=search)

    def get(self, store_id: int) -> InventoryStore:
        """Fetch store details by ID."""
        return self.repository.get_required_by_id(store_id)

    def create(self, payload: InventoryStoreCreateSchema) -> InventoryStore:
        """Create a new store record."""
        s = self.repository.create(
            name=payload.name,
            code=payload.code,
            location_description=payload.location_description,
            description=payload.description,
        )
        self.db.commit()
        return self.repository.get_required_by_id(s.id)

    def update(self, store_id: int, payload: InventoryStoreUpdateSchema) -> InventoryStore:
        """Update store metadata."""
        s = self.repository.get_required_by_id(store_id)
        updated = self.repository.update(s, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def soft_delete(self, store_id: int) -> InventoryStore:
        """Logical delete of a store."""
        s = self.repository.get_required_by_id(store_id)
        deleted = self.repository.soft_delete(s)
        self.db.commit()
        return deleted


class InventoryStockItemService:
    """Service for managing individual stock records and their quantities."""

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
        """Query stock items with advanced business filters (low stock, expiring soon)."""
        item_type_enum = InventoryItemType(item_type) if item_type else None
        return self.repository.list_items(
            skip=skip, limit=limit, search=search,
            store_id=store_id, drug_id=drug_id, item_type=item_type_enum,
            only_low_stock=only_low_stock,
            only_expiring_within_days=only_expiring_within_days,
        )

    def get(self, item_id: int) -> InventoryStockItem:
        """Fetch stock item details."""
        return self.repository.get_required_by_id(item_id)

    def create(self, payload: InventoryStockItemCreateSchema) -> InventoryStockItem:
        """Register a new stock item in a specific store."""
        # Ensure the store exists before adding stock to it.
        self.store_repository.get_required_by_id(payload.store_id)
        i = self.repository.create(**payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(i.id)

    def update(self, item_id: int, payload: InventoryStockItemUpdateSchema) -> InventoryStockItem:
        """Update stock item metadata (non-quantity fields)."""
        i = self.repository.get_required_by_id(item_id)
        updated = self.repository.update(i, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def soft_delete(self, item_id: int) -> InventoryStockItem:
        """Logical delete of a stock item."""
        i = self.repository.get_required_by_id(item_id)
        deleted = self.repository.soft_delete(i)
        self.db.commit()
        return deleted


class StockMovementService:
    """
    Orchestrator for stock adjustments.
    
    This service is responsible for the atomic transaction of recording a
    movement (audit) and updating the stock item's balance (current state).
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = StockMovementRepository(db)
        self.item_repository = InventoryStockItemRepository(db)

    def list(
        self,
        *,
        skip=0,
        limit=50,
        store_id: Optional[int] = None,
        stock_item_id: Optional[int] = None,
        movement_type: Optional[str] = None,
    ):
        """List historical movements with filtering."""
        from app.core.enums import StockMovementType
        m_type = StockMovementType(movement_type) if movement_type else None
        return self.repository.list_movements(
            skip=skip, limit=limit,
            store_id=store_id, stock_item_id=stock_item_id, movement_type=m_type
        )

    def get(self, movement_id: int) -> StockMovement:
        """Fetch movement record details."""
        return self.repository.get_required_by_id(movement_id)

    def create(self, payload: StockMovementCreateSchema) -> StockMovement:
        """
        Record a stock movement and atomically adjust the stock item quantity.
        
        Business Logic:
        1. Validates that the store_id matches the stock item's store.
        2. Determines if the movement is additive or subtractive based on type.
        3. Updates the InventoryStockItem.quantity_on_hand.
        4. Records the StockMovement audit row with a 'balance_after' snapshot.
        """
        from app.core.enums import StockMovementType
        item = self.item_repository.get_required_by_id(payload.stock_item_id)
        
        # Guard: Movements cannot move stock between different physical stores.
        if payload.store_id != item.store_id:
             from app.core.exceptions import BadRequestError
             raise BadRequestError(
                 message="Store mismatch. Item belongs to a different store.",
                 detail={"item_store_id": item.store_id, "payload_store_id": payload.store_id}
             )

        m_type = StockMovementType(payload.movement_type)
        
        # Categorize movement direction.
        # Additive: Stock entering the system (Purchases, Returns, Adjustments IN).
        # Subtractive: Stock leaving the system (Issues, Dispensing, Adjustments OUT, Waste).
        additive_types = {
            StockMovementType.OPENING_BALANCE,
            StockMovementType.PURCHASE,
            StockMovementType.TRANSFER_IN,
            StockMovementType.ADJUSTMENT_IN,
            StockMovementType.RETURN_IN
        }
        
        delta = payload.quantity
        if m_type not in additive_types:
            # Force negative delta for subtractive movements
            delta = -abs(delta)
        else:
            # Force positive delta for additive movements
            delta = abs(delta)

        # Update the live balance in the stock item record
        item = self.item_repository.adjust_quantity(item, delta)
        
        # Record the audit row with the final balance snapshot
        m = self.repository.create(
            **payload.model_dump(exclude_unset=True),
            balance_after=item.quantity_on_hand
        )
        
        self.db.commit()
        return self.repository.get_required_by_id(m.id)
