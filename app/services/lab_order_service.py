# app/services/lab_order_service.py
from __future__ import annotations

"""
Service layer for LabOrder lifecycle.

Lifecycle (per item)
--------------------
ORDERED -> SAMPLE_COLLECTED -> IN_PROGRESS -> RESULT_READY -> COMPLETED
                                                    \\-> CANCELLED

The order itself rolls up to the most-advanced common state of its items.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import OrderStatus, ServicePointType, VisitStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import LabOrder, LabOrderItem, LabTestCatalog
from app.repositories.lab_order_repository import LabOrderRepository
from app.schemas.lab_order_schema import (
    LabOrderCreateSchema,
    LabOrderItemSpecimenSchema,
)
from app.utils.charge_capture import (
    add_charge,
    find_billable_service,
    get_or_create_open_billing,
)
from app.utils.payment_policy import requires_pre_payment
from app.utils.security_event_util import record_security_event
from app.utils.visit_routing import route_visit_to_next_sdp, validate_visit_sdp_activity


class LabOrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = LabOrderRepository(db)

    # ============================================================
    # READ
    # ============================================================

    def list_for_visit(self, visit_id: int, *, skip: int = 0, limit: int = 50):
        return self.repository.list_for_visit(visit_id, skip=skip, limit=limit)

    def get(self, order_id: int) -> LabOrder:
        return self.repository.get_required_by_id(order_id)

    def list_lab_worklist(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        statuses: Optional[list[str]] = None,
    ):
        normalized = None
        if statuses:
            normalized = [OrderStatus(s.strip().upper()) for s in statuses]
        return self.repository.list_lab_worklist(skip=skip, limit=limit, statuses=normalized)

    # ============================================================
    # CREATE
    # ============================================================

    def create_order(
        self,
        payload: LabOrderCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> LabOrder:
        visit = self.repository.get_visit(payload.visit_id)
        if not visit:
            raise NotFoundError(message="Visit not found.", detail={"visit_id": payload.visit_id})
        if visit.status in {VisitStatus.COMPLETED, VisitStatus.CANCELLED}:
            raise BadRequestError(
                message="Cannot order labs for a closed visit.",
                detail={"visit_status": str(visit.status)},
            )
            

        current_step = validate_visit_sdp_activity(
            self.db,
            visit_id=visit.id,
            required_sdp_types=[ServicePointType.CLINIC, ServicePointType.EMERGENCY, ServicePointType.WARD],
            activity_name="Lab Order creation",
        )

        # Validate every requested test exists.
        items_payload: list[dict] = []
        tests_by_id: dict[int, LabTestCatalog] = {}
        for entry in payload.items:
            test = self.repository.get_test(entry.lab_test_catalog_id)
            if not test:
                raise NotFoundError(
                    message="Lab test not found.",
                    detail={"lab_test_catalog_id": entry.lab_test_catalog_id},
                )
            items_payload.append({"lab_test_catalog_id": test.id})
            tests_by_id[test.id] = test

        order = self.repository.create_order(
            visit_id=visit.id,
            visit_flow_step_id=current_step.id,
            consultation_id=payload.consultation_id,
            ordered_by_staff_id=payload.ordered_by_staff_id,
            clinical_note=payload.clinical_note,
            items_payload=items_payload,
        )

        # Charge capture (one billing line per ordered test).
        if payload.auto_capture_charge:
            billing = get_or_create_open_billing(self.db, visit=visit)
            order_items = self.repository.items_for_order(order.id)
            for item in order_items:
                test = tests_by_id.get(item.lab_test_catalog_id)
                if test is None:
                    continue
                billable = find_billable_service(self.db, code=f"LAB-{test.code}")
                add_charge(
                    self.db,
                    billing=billing,
                    service_name=f"Lab: {test.name}",
                    service_code=f"LAB-{test.code}",
                    unit_price=Decimal(test.default_price or 0),
                    quantity=Decimal("1"),
                    billable_service_id=billable.id if billable else None,
                    source_reference=f"LAB_ORDER_ITEM:{item.id}",
                )

        # Routing decision: cashier first when pre-payment is required.
        next_sdp_id: Optional[int] = None
        if requires_pre_payment(source="LAB"):
            next_sdp_id = (
                payload.route_to_cashier_service_delivery_point_id
                or payload.route_to_lab_service_delivery_point_id
            )
        else:
            next_sdp_id = (
                payload.route_to_lab_service_delivery_point_id
                or payload.route_to_cashier_service_delivery_point_id
            )

        if next_sdp_id is not None:
            route_visit_to_next_sdp(
                self.db,
                visit_id=visit.id,
                target_service_delivery_point_id=next_sdp_id,
                routed_by_id=actor_user_id,
                notes="Routed by lab order.",
            )

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="LAB_ORDER_CREATED",
            severity="INFO",
            event_detail=f"Lab order {order.order_no} created for visit {visit.id}.",
            event_metadata={
                "order_id": order.id,
                "visit_id": visit.id,
                "item_count": len(items_payload),
            },
        )

        self.db.commit()
        return self.repository.get_required_by_id(order.id)

    # ============================================================
    # SPECIMEN / EXECUTION
    # ============================================================

    def collect_specimen(
        self,
        item_id: int,
        payload: LabOrderItemSpecimenSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> LabOrderItem:
        item = self.repository.get_required_item_by_id(item_id)
        if item.status not in {OrderStatus.ORDERED, OrderStatus.SAMPLE_COLLECTED}:
            raise BadRequestError(
                message="Specimen collection is not valid in the current state.",
                detail={"status": str(item.status)},
            )

        current_step = validate_visit_sdp_activity(
            self.db,
            visit_id=item.lab_order.visit_id,
            required_sdp_types=[ServicePointType.LABORATORY],
            activity_name="Sample Collection",
        )

        item.specimen_id = payload.specimen_id or item.specimen_id
        item.collected_by_staff_id = payload.collected_by_staff_id or item.collected_by_staff_id
        item.sample_collected_at = datetime.now(timezone.utc)
        item.visit_flow_step_id = current_step.id
        item.status = OrderStatus.SAMPLE_COLLECTED
        self.repository.save_item(item)

        order = self.repository.get_required_by_id(item.lab_order_id)
        self.repository.recompute_order_status(order)

        self.db.commit()
        return self.repository.get_required_item_by_id(item.id)

    def start_processing(
        self,
        item_id: int,
        *,
        actor_user_id: Optional[int] = None,
    ) -> LabOrderItem:
        item = self.repository.get_required_item_by_id(item_id)
        if item.status not in {OrderStatus.SAMPLE_COLLECTED, OrderStatus.IN_PROGRESS}:
            raise BadRequestError(
                message="Cannot start processing without a collected specimen.",
                detail={"status": str(item.status)},
            )
        item.status = OrderStatus.IN_PROGRESS
        self.repository.save_item(item)

        order = self.repository.get_required_by_id(item.lab_order_id)
        self.repository.recompute_order_status(order)
        self.db.commit()
        return self.repository.get_required_item_by_id(item.id)

    def cancel_item(
        self,
        item_id: int,
        *,
        reason: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> LabOrderItem:
        item = self.repository.get_required_item_by_id(item_id)
        if item.status in {OrderStatus.COMPLETED, OrderStatus.CANCELLED}:
            raise BadRequestError(
                message="Item is already in a terminal state.",
                detail={"status": str(item.status)},
            )
        item.status = OrderStatus.CANCELLED
        self.repository.save_item(item)

        order = self.repository.get_required_by_id(item.lab_order_id)
        self.repository.recompute_order_status(order)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="LAB_ORDER_ITEM_CANCELLED",
            severity="WARNING",
            event_detail=f"Lab order item {item.id} cancelled. Reason: {reason}",
            event_metadata={"item_id": item.id, "reason": reason},
        )
        self.db.commit()
        return self.repository.get_required_item_by_id(item.id)

    def cancel_order(
        self,
        order_id: int,
        *,
        reason: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> LabOrder:
        order = self.repository.get_required_by_id(order_id)
        if order.status in {OrderStatus.COMPLETED, OrderStatus.CANCELLED}:
            raise BadRequestError(
                message="Order is already in a terminal state.",
                detail={"status": str(order.status)},
            )

        for item in self.repository.items_for_order(order.id):
            if item.status not in {OrderStatus.COMPLETED, OrderStatus.CANCELLED}:
                item.status = OrderStatus.CANCELLED
                self.repository.save_item(item)

        order.status = OrderStatus.CANCELLED
        self.repository.save(order)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="LAB_ORDER_CANCELLED",
            severity="WARNING",
            event_detail=f"Lab order {order.order_no} cancelled. Reason: {reason}",
            event_metadata={"order_id": order.id, "reason": reason},
        )
        self.db.commit()
        return self.repository.get_required_by_id(order.id)
