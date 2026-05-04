# app/repositories/lab_order_repository.py
from __future__ import annotations

"""
Repository for LabOrder and LabOrderItem.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.enums import OrderStatus
from app.core.exceptions import NotFoundError
from app.models.all_models import LabOrder, LabOrderItem, LabTestCatalog, Visit
from app.utils.helpers import generate_uuid_str


class LabOrderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ============================================================
    # LOOKUPS
    # ============================================================

    def get_visit(self, visit_id: int) -> Optional[Visit]:
        return (
            self.db.query(Visit)
            .filter(Visit.id == visit_id, Visit.is_deleted.is_(False))
            .first()
        )

    def get_by_id(self, order_id: int) -> Optional[LabOrder]:
        return (
            self.db.query(LabOrder)
            .options(selectinload(LabOrder.items))
            .filter(LabOrder.id == order_id, LabOrder.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, order_id: int) -> LabOrder:
        order = self.get_by_id(order_id)
        if not order:
            raise NotFoundError(message="Lab order not found.", detail={"lab_order_id": order_id})
        return order

    def get_item_by_id(self, item_id: int) -> Optional[LabOrderItem]:
        return (
            self.db.query(LabOrderItem)
            .options(joinedload(LabOrderItem.lab_order))
            .filter(LabOrderItem.id == item_id, LabOrderItem.is_deleted.is_(False))
            .first()
        )

    def get_required_item_by_id(self, item_id: int) -> LabOrderItem:
        item = self.get_item_by_id(item_id)
        if not item:
            raise NotFoundError(message="Lab order item not found.", detail={"item_id": item_id})
        return item

    def list_for_visit(
        self, visit_id: int, *, skip: int = 0, limit: int = 50
    ) -> tuple[list[LabOrder], int]:
        query = (
            self.db.query(LabOrder)
            .options(selectinload(LabOrder.items))
            .filter(LabOrder.visit_id == visit_id, LabOrder.is_deleted.is_(False))
        )
        total = query.with_entities(func.count(LabOrder.id)).scalar() or 0
        items = (
            query.order_by(LabOrder.id.desc()).offset(skip).limit(limit).all()
        )
        return items, int(total)

    def list_lab_worklist(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        statuses: Optional[list[OrderStatus]] = None,
    ) -> tuple[list[LabOrder], int]:
        """
        Worklist of lab orders (default: not yet completed).
        """
        query = (
            self.db.query(LabOrder)
            .options(selectinload(LabOrder.items))
            .filter(LabOrder.is_deleted.is_(False))
        )
        if statuses:
            query = query.filter(LabOrder.status.in_(statuses))
        else:
            query = query.filter(
                LabOrder.status.notin_([OrderStatus.COMPLETED, OrderStatus.CANCELLED])
            )

        total = query.with_entities(func.count(LabOrder.id)).scalar() or 0
        items = query.order_by(LabOrder.ordered_at.asc()).offset(skip).limit(limit).all()
        return items, int(total)

    # ============================================================
    # CREATE
    # ============================================================

    def generate_order_number(self) -> str:
        return f"LAB-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create_order(
        self,
        *,
        visit_id: int,
        consultation_id: Optional[int],
        ordered_by_staff_id: Optional[int],
        clinical_note: Optional[str],
        items_payload: list[dict],
    ) -> LabOrder:
        order = LabOrder(
            visit_id=visit_id,
            consultation_id=consultation_id,
            ordered_by_staff_id=ordered_by_staff_id,
            order_no=self.generate_order_number(),
            status=OrderStatus.ORDERED,
            clinical_note=clinical_note,
            ordered_at=datetime.now(timezone.utc),
        )
        self.db.add(order)
        self.db.flush()
        self.db.refresh(order)

        for entry in items_payload:
            item = LabOrderItem(
                lab_order_id=order.id,
                lab_test_catalog_id=entry["lab_test_catalog_id"],
                status=OrderStatus.ORDERED,
            )
            self.db.add(item)
        self.db.flush()
        self.db.refresh(order)
        return order

    # ============================================================
    # MUTATIONS
    # ============================================================

    def save(self, order: LabOrder) -> LabOrder:
        self.db.add(order)
        self.db.flush()
        self.db.refresh(order)
        return order

    def save_item(self, item: LabOrderItem) -> LabOrderItem:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_test(self, test_id: int) -> Optional[LabTestCatalog]:
        return (
            self.db.query(LabTestCatalog)
            .filter(LabTestCatalog.id == test_id, LabTestCatalog.is_deleted.is_(False))
            .first()
        )

    def items_for_order(self, order_id: int) -> list[LabOrderItem]:
        return (
            self.db.query(LabOrderItem)
            .filter(LabOrderItem.lab_order_id == order_id, LabOrderItem.is_deleted.is_(False))
            .all()
        )

    def recompute_order_status(self, order: LabOrder) -> LabOrder:
        """
        Walk the items and roll the order status forward to the most-advanced
        common state.
        """
        items = self.items_for_order(order.id)
        if not items:
            return order

        statuses = {i.status for i in items}

        if all(s == OrderStatus.CANCELLED for s in statuses):
            order.status = OrderStatus.CANCELLED
        elif all(s in {OrderStatus.COMPLETED, OrderStatus.CANCELLED} for s in statuses):
            order.status = OrderStatus.COMPLETED
        elif any(s == OrderStatus.RESULT_READY for s in statuses):
            order.status = OrderStatus.RESULT_READY
        elif any(s == OrderStatus.IN_PROGRESS for s in statuses):
            order.status = OrderStatus.IN_PROGRESS
        elif any(s == OrderStatus.SAMPLE_COLLECTED for s in statuses):
            order.status = OrderStatus.SAMPLE_COLLECTED
        else:
            order.status = OrderStatus.ORDERED

        self.db.add(order)
        self.db.flush()
        self.db.refresh(order)
        return order
