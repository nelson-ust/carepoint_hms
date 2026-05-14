# app/repositories/lab_order_repository.py
from __future__ import annotations

"""
app.repositories.lab_order_repository

Repository layer for Laboratory Orders and Order Items.

Purpose
-------
This module handles persistence logic for:
- LabOrder (header)
- LabOrderItem (line items)
- Lab Worklist queries
- Status recomputation based on line-item states

It also handles order number generation and filtered eager loading to ensure
optimal performance and correct soft-delete handling.
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
    """
    Repository for LabOrder and LabOrderItem operations.
    
    This class centralizes all database interactions for the laboratory ordering 
    workflow, ensuring that soft-delete flags are respected and relationships 
    are loaded efficiently.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ============================================================
    # LOOKUPS
    # ============================================================

    def get_visit(self, visit_id: int) -> Optional[Visit]:
        """
        Retrieve a visit record for validation during order creation.
        """
        return (
            self.db.query(Visit)
            .filter(Visit.id == visit_id, Visit.is_deleted.is_(False))
            .first()
        )

    def get_by_id(self, order_id: int) -> Optional[LabOrder]:
        """
        Retrieve a lab order by ID with its items pre-loaded.
        
        Optimized with selectinload and server-side soft-delete filtering 
        for nested items.
        """
        return (
            self.db.query(LabOrder)
            .options(
                joinedload(LabOrder.visit).joinedload(Visit.patient),
                selectinload(
                    LabOrder.items.and_(LabOrderItem.is_deleted.is_(False))
                ).joinedload(LabOrderItem.lab_test_catalog),
            )
            .filter(LabOrder.id == order_id, LabOrder.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, order_id: int) -> LabOrder:
        """
        Retrieve a lab order by ID or raise NotFoundError if not present.
        """
        order = self.get_by_id(order_id)
        if not order:
            raise NotFoundError(message="Lab order not found.", detail={"lab_order_id": order_id})
        return order

    def get_item_by_id(self, item_id: int) -> Optional[LabOrderItem]:
        """
        Retrieve a single lab order item with its parent order header.
        """
        return (
            self.db.query(LabOrderItem)
            .options(joinedload(LabOrderItem.lab_order))
            .filter(LabOrderItem.id == item_id, LabOrderItem.is_deleted.is_(False))
            .first()
        )

    def get_required_item_by_id(self, item_id: int) -> LabOrderItem:
        """
        Retrieve a lab order item or raise NotFoundError if not present.
        """
        item = self.get_item_by_id(item_id)
        if not item:
            raise NotFoundError(message="Lab order item not found.", detail={"item_id": item_id})
        return item

    def list_for_visit(
        self, visit_id: int, *, skip: int = 0, limit: int = 50
    ) -> tuple[list[LabOrder], int]:
        """
        Return all lab orders associated with a specific visit.
        """
        query = (
            self.db.query(LabOrder)
            .options(
                selectinload(
                    LabOrder.items.and_(LabOrderItem.is_deleted.is_(False))
                ).joinedload(LabOrderItem.lab_test_catalog)
            )
            .filter(LabOrder.visit_id == visit_id, LabOrder.is_deleted.is_(False))
        )
        # Use separate count query for performance
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
        Fetch a worklist of lab orders for laboratory technicians.
        
        By default, returns orders that are not in a terminal state (COMPLETED/CANCELLED).
        """
        query = (
            self.db.query(LabOrder)
            .options(
                joinedload(LabOrder.visit).joinedload(Visit.patient),
                selectinload(
                    LabOrder.items.and_(LabOrderItem.is_deleted.is_(False))
                ).joinedload(LabOrderItem.lab_test_catalog),
            )
            .filter(LabOrder.is_deleted.is_(False))
        )
        
        # Filter by specific statuses if provided, else exclude terminal states
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
        """
        Generate a human-readable order number for laboratory requisitions.
        Format: LAB-YYYYMMDD-8CHARHASH
        """
        return f"LAB-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create_order(
        self,
        *,
        visit_id: int,
        consultation_id: Optional[int],
        ordered_by_staff_id: Optional[int],
        visit_flow_step_id: Optional[int] = None,
        clinical_note: Optional[str],
        items_payload: list[dict],
    ) -> LabOrder:
        """
        Initialize a new Lab Order and its associated items.
        """
        order = LabOrder(
            visit_id=visit_id,
            visit_flow_step_id=visit_flow_step_id,
            consultation_id=consultation_id,
            ordered_by_staff_id=ordered_by_staff_id,
            order_no=self.generate_order_number(),
            status=OrderStatus.ORDERED,
            clinical_note=clinical_note,
            ordered_at=datetime.now(timezone.utc),
        )
        self.db.add(order)
        self.db.flush() # Secure ID for items
        self.db.refresh(order)

        # Create line items from payload
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
        """
        Persist changes to a LabOrder header.
        """
        self.db.add(order)
        self.db.flush()
        self.db.refresh(order)
        return order

    def save_item(self, item: LabOrderItem) -> LabOrderItem:
        """
        Persist changes to a LabOrderItem.
        """
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_test(self, test_id: int) -> Optional[LabTestCatalog]:
        """
        Retrieve a test catalog entry by ID.
        """
        return (
            self.db.query(LabTestCatalog)
            .filter(LabTestCatalog.id == test_id, LabTestCatalog.is_deleted.is_(False))
            .first()
        )

    def items_for_order(self, order_id: int) -> list[LabOrderItem]:
        """
        Retrieve all active line items for a specific order.
        """
        return (
            self.db.query(LabOrderItem)
            .filter(LabOrderItem.lab_order_id == order_id, LabOrderItem.is_deleted.is_(False))
            .all()
        )

    def recompute_order_status(self, order: LabOrder) -> LabOrder:
        """
        Walk the items and roll the order status forward to the most-advanced
        common state.
        
        Logic:
        - If all items are CANCELLED -> Order is CANCELLED
        - If all items are COMPLETED/CANCELLED -> Order is COMPLETED
        - If any item is RESULT_READY -> Order is RESULT_READY
        - If any item is IN_PROGRESS -> Order is IN_PROGRESS
        - If any item is SAMPLE_COLLECTED -> Order is SAMPLE_COLLECTED
        - Else -> Order is ORDERED
        """
        items = self.items_for_order(order.id)
        if not items:
            return order

        # Extract unique statuses across all items
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

        # Persist the calculated status
        self.db.add(order)
        self.db.flush()
        self.db.refresh(order)
        return order
