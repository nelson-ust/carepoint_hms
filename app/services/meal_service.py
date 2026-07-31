# app/services/meal_service.py
from __future__ import annotations

"""
Service layer for Dietary & Meal Management.
Handles meal ordering, serving, and automatic billing integration.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.enums import MealRecipient, MealStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import MealOrder, MealType, Billing, BillingItem
from app.repositories.meal_repository import MealRepository
from app.repositories.billing_repository import BillingRepository
from app.utils.charge_capture import add_charge, resolve_billable_service
from app.schemas.meal_schemas import MealOrderCreate, MealOrderUpdate, MealTypeCreate


class MealService:
    """Business logic for Patient & Caregiver meals."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = MealRepository(db)
        self.billing_repository = BillingRepository(db)

    # ============================================================
    # MEAL TYPE MANAGEMENT
    # ============================================================

    def list_meal_types(self) -> list[MealType]:
        """Return all active meal types from the catalog."""
        return self.repository.list_meal_types()

    def create_meal_type(self, payload: MealTypeCreate) -> MealType:
        """Add a new meal type to the catalog."""
        if self.repository.get_meal_type_by_code(payload.code):
            raise BadRequestError(message=f"Meal type with code '{payload.code}' already exists.")
        
        meal_type = self.repository.create_meal_type(**payload.model_dump())
        self.db.commit()
        return meal_type

    # ============================================================
    # MEAL ORDERING & BILLING
    # ============================================================

    def place_order(
        self, 
        payload: MealOrderCreate, 
        actor_staff_id: Optional[int] = None
    ) -> MealOrder:
        """
        Record a meal request. 
        Initial status is ORDERED. No billing happens until the meal is SERVED.
        """
        meal_type = self.repository.get_meal_type_by_id(payload.meal_type_id)
        if not meal_type:
            raise NotFoundError(message="Meal type not found.")

        # Calculate amounts
        unit_price = meal_type.base_price
        total_amount = unit_price * payload.quantity

        order = self.repository.create_order(
            **payload.model_dump(),
            status=MealStatus.ORDERED,
            unit_price=unit_price,
            total_amount=total_amount,
            ordered_by_staff_id=actor_staff_id,
            ordered_at=datetime.now(timezone.utc)
        )
        self.db.commit()
        return order

    def serve_meal(
        self, 
        order_id: int, 
        actor_staff_id: Optional[int] = None
    ) -> MealOrder:
        """
        Mark a meal as served and trigger automatic billing.
        The charge is added to the patient's active billing session for the visit.
        """
        order = self.repository.get_order_by_id(order_id)
        if not order:
            raise NotFoundError(message="Meal order not found.")
        
        if order.status == MealStatus.SERVED:
            return order  # Idempotent
        
        if order.status == MealStatus.CANCELLED:
            raise BadRequestError(message="Cannot serve a cancelled meal order.")

        # 1. Update order status
        order.status = MealStatus.SERVED
        order.served_at = datetime.now(timezone.utc)
        order.served_by_staff_id = actor_staff_id

        # 2. Integrate with Billing
        # Find or create an open billing session for this visit
        billing = self.billing_repository.get_active_billing_for_visit(order.visit_id)
        if not billing:
            # Fallback: create a new billing session if none exists
            # In a real system, we might want to use a more robust discovery mechanism
            from app.models.all_models import Visit
            visit = self.db.query(Visit).get(order.visit_id)
            if not visit:
                 raise NotFoundError(message="Associated visit not found.")
                 
            billing = Billing(
                patient_id=order.patient_id,
                visit_id=order.visit_id,
                facility_id=visit.facility_id,
                billing_no=f"BILL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{order.id}",
                billing_date=datetime.now(timezone.utc),
                status="OPEN"
            )
            self.db.add(billing)
            self.db.flush()

        # Create the billing item (charge)
        # Construct service name based on recipient
        recipient_label = "Patient" if order.recipient_type == MealRecipient.PATIENT else f"Caregiver ({order.caregiver_name or 'Unknown'})"
        service_name = f"Meal: {order.meal_type.name} for {recipient_label}"
        
        # Ensure the meal maps to an account-bearing billable service so the
        # charge posts to the ledger like every other clinical service.
        billable = resolve_billable_service(
            self.db,
            code=f"MEAL-{order.meal_type.code}",
            name=f"Meal: {order.meal_type.name}",
            default_price=Decimal(order.unit_price or 0),
            category="DIETARY",
            domain="MEALS",
        )
        if order.meal_type.billable_service_id is None:
            order.meal_type.billable_service_id = billable.id
            self.db.add(order.meal_type)

        billing_item = add_charge(
            self.db,
            billing=billing,
            service_name=service_name,
            service_code=order.meal_type.code,
            unit_price=Decimal(order.unit_price or 0),
            quantity=Decimal(order.quantity or 1),
            billable_service_id=billable.id,
            source_reference=f"MEAL-ORDER-{order.id}",
        )
        
        # Link the invoice item (or billing item) back to the order for audit
        order.invoice_item_id = billing_item.id

        # Update billing totals
        self.billing_repository.recompute_totals(billing)
        
        self.db.commit()
        return order

    def cancel_order(self, order_id: int) -> MealOrder:
        """Cancel a meal order before it is served."""
        order = self.repository.get_order_by_id(order_id)
        if not order:
            raise NotFoundError(message="Meal order not found.")
        
        if order.status == MealStatus.SERVED:
            raise BadRequestError(message="Cannot cancel a meal that has already been served.")
            
        order.status = MealStatus.CANCELLED
        self.db.commit()
        return order

    def list_orders(self, **kwargs) -> Tuple[list[MealOrder], int]:
        """List meal orders with optional filtering."""
        return self.repository.list_orders(**kwargs)
