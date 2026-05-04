# app/services/stock_movement_service.py
from __future__ import annotations

"""
Service layer for posting stock movements with balance-after computation,
negative-stock guard, and inter-store transfers.
"""

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import InventoryItemType, StockMovementType
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import StockMovement
from app.repositories.inventory_repository import (
    InventoryStockItemRepository,
    InventoryStoreRepository,
)
from app.repositories.stock_movement_repository import StockMovementRepository
from app.schemas.stock_movement_schema import (
    StockMovementCreateSchema,
    StockTransferSchema,
)


# Movements that DECREASE on-hand quantity at a store/item.
DECREASING_MOVEMENTS = {
    StockMovementType.ISSUE,
    StockMovementType.DISPENSE,
    StockMovementType.TRANSFER_OUT,
    StockMovementType.ADJUSTMENT_OUT,
    StockMovementType.RETURN_OUT,
    StockMovementType.WRITE_OFF,
}

# Movements that INCREASE on-hand quantity at a store/item.
INCREASING_MOVEMENTS = {
    StockMovementType.OPENING_BALANCE,
    StockMovementType.PURCHASE,
    StockMovementType.TRANSFER_IN,
    StockMovementType.ADJUSTMENT_IN,
    StockMovementType.RETURN_IN,
}


class StockMovementService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = StockMovementRepository(db)
        self.stock_repository = InventoryStockItemRepository(db)
        self.store_repository = InventoryStoreRepository(db)

    # ============================================================
    # POST MOVEMENT
    # ============================================================

    def post_movement(
        self,
        payload: StockMovementCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> StockMovement:
        movement_type = StockMovementType(payload.movement_type)
        store = self.store_repository.get_required_by_id(payload.store_id)
        stock_item = self.stock_repository.get_required_by_id(payload.stock_item_id)

        if stock_item.store_id != store.id:
            raise BadRequestError(
                message="Stock item does not belong to the supplied store.",
                detail={"stock_item_store_id": stock_item.store_id, "store_id": store.id},
            )

        return self._apply_movement(
            stock_item=stock_item,
            store_id=store.id,
            movement_type=movement_type,
            quantity=payload.quantity,
            reference_no=payload.reference_no,
            note=payload.note,
            performed_by_staff_id=payload.performed_by_staff_id,
            commit=True,
        )

    # ============================================================
    # TRANSFER
    # ============================================================

    def transfer(
        self,
        payload: StockTransferSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> dict:
        """
        Transfer between stores. Decreases source stock item, finds-or-creates a
        matching destination stock item, then increases it.
        """
        source = self.stock_repository.get_required_by_id(payload.from_stock_item_id)
        target_store = self.store_repository.get_required_by_id(payload.to_store_id)

        if source.store_id == target_store.id:
            raise BadRequestError(message="Source and target stores must differ.")

        # Find or create the destination stock item with matching attributes.
        existing_dest, _ = self.stock_repository.list_items(
            store_id=target_store.id,
            drug_id=source.drug_id,
            item_type=source.item_type,
            limit=200,
        )
        match: Optional = None
        for candidate in existing_dest:
            if (
                candidate.item_name == source.item_name
                and (candidate.batch_no or None) == (source.batch_no or None)
                and (candidate.expiry_date or None) == (source.expiry_date or None)
            ):
                match = candidate
                break

        if match is None:
            match = self.stock_repository.create(
                store_id=target_store.id,
                drug_id=source.drug_id,
                item_type=source.item_type,
                item_name=source.item_name,
                sku=source.sku,
                unit_of_measure=source.unit_of_measure,
                quantity_on_hand=Decimal("0"),
                reorder_level=source.reorder_level,
                unit_cost=source.unit_cost,
                expiry_date=source.expiry_date,
                batch_no=source.batch_no,
            )

        out_movement = self._apply_movement(
            stock_item=source,
            store_id=source.store_id,
            movement_type=StockMovementType.TRANSFER_OUT,
            quantity=payload.quantity,
            reference_no=f"TRF-{source.id}->{match.id}",
            note=payload.note,
            performed_by_staff_id=payload.performed_by_staff_id,
            commit=False,
        )
        in_movement = self._apply_movement(
            stock_item=match,
            store_id=target_store.id,
            movement_type=StockMovementType.TRANSFER_IN,
            quantity=payload.quantity,
            reference_no=f"TRF-{source.id}->{match.id}",
            note=payload.note,
            performed_by_staff_id=payload.performed_by_staff_id,
            commit=False,
        )

        self.db.commit()
        return {
            "out_movement": self.repository.get_required_by_id(out_movement.id),
            "in_movement": self.repository.get_required_by_id(in_movement.id),
        }

    # ============================================================
    # READ
    # ============================================================

    def list_movements(self, **kwargs):
        movement_type = kwargs.pop("movement_type", None)
        if movement_type:
            kwargs["movement_type"] = StockMovementType(movement_type)
        return self.repository.list_movements(**kwargs)

    def get(self, movement_id: int) -> StockMovement:
        return self.repository.get_required_by_id(movement_id)

    # ============================================================
    # INTERNAL
    # ============================================================

    def _apply_movement(
        self,
        *,
        stock_item,
        store_id: int,
        movement_type: StockMovementType,
        quantity: Decimal,
        reference_no: Optional[str],
        note: Optional[str],
        performed_by_staff_id: Optional[int],
        commit: bool,
    ) -> StockMovement:
        if quantity is None or Decimal(quantity) <= 0:
            raise BadRequestError(message="quantity must be greater than zero.")

        delta = Decimal(quantity)
        if movement_type in DECREASING_MOVEMENTS:
            delta = -delta
        elif movement_type not in INCREASING_MOVEMENTS:
            raise BadRequestError(
                message="Unsupported movement_type.",
                detail={"movement_type": str(movement_type)},
            )

        new_balance = (stock_item.quantity_on_hand or Decimal("0")) + delta
        if new_balance < 0 and not bool(getattr(settings, "NEGATIVE_STOCK_ALLOWED", False)):
            raise BadRequestError(
                message="Insufficient stock for this movement.",
                detail={
                    "stock_item_id": stock_item.id,
                    "current_quantity": str(stock_item.quantity_on_hand),
                    "requested_quantity": str(quantity),
                },
            )

        self.stock_repository.adjust_quantity(stock_item, delta)
        movement = self.repository.create(
            store_id=store_id,
            stock_item_id=stock_item.id,
            movement_type=movement_type,
            quantity=Decimal(quantity),
            balance_after=new_balance,
            reference_no=reference_no,
            note=note,
            performed_by_staff_id=performed_by_staff_id,
        )
        if commit:
            self.db.commit()
        return movement
