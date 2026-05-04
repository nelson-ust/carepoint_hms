# app/repositories/stock_movement_repository.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import StockMovementType
from app.core.exceptions import NotFoundError
from app.models.all_models import StockMovement


class StockMovementRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        store_id: int,
        stock_item_id: int,
        movement_type: StockMovementType,
        quantity: Decimal,
        balance_after: Decimal,
        reference_no: Optional[str] = None,
        note: Optional[str] = None,
        performed_by_staff_id: Optional[int] = None,
    ) -> StockMovement:
        movement = StockMovement(
            store_id=store_id,
            stock_item_id=stock_item_id,
            movement_type=movement_type,
            quantity=quantity,
            balance_after=balance_after,
            reference_no=reference_no,
            note=note,
            performed_by_staff_id=performed_by_staff_id,
            movement_date=datetime.now(timezone.utc),
        )
        self.db.add(movement)
        self.db.flush()
        self.db.refresh(movement)
        return movement

    def get_by_id(self, movement_id: int) -> Optional[StockMovement]:
        return (
            self.db.query(StockMovement)
            .filter(StockMovement.id == movement_id, StockMovement.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, movement_id: int) -> StockMovement:
        m = self.get_by_id(movement_id)
        if not m:
            raise NotFoundError(message="Stock movement not found.", detail={"movement_id": movement_id})
        return m

    def list_movements(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        store_id: Optional[int] = None,
        stock_item_id: Optional[int] = None,
        movement_type: Optional[StockMovementType] = None,
    ) -> tuple[list[StockMovement], int]:
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
