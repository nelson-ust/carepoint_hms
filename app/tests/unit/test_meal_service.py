# app/tests/unit/test_meal_service.py
from __future__ import annotations

"""Unit tests for MealService."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.core.enums import MealRecipient, MealStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import MealOrder, MealType, Visit, Billing
from app.services.meal_service import MealService


class TestMealService:
    def setup_method(self):
        self.db = MagicMock()
        self.service = MealService(self.db)

    def test_list_meal_types(self):
        # Mock repository list call
        self.service.repository.list_meal_types = MagicMock(return_value=[])
        res = self.service.list_meal_types()
        assert res == []
        self.service.repository.list_meal_types.assert_called_once()

    def test_place_order_success(self):
        from app.schemas.meal_schemas import MealOrderCreate
        
        mock_meal_type = MealType(id=1, name="Lunch", base_price=Decimal("500.00"))
        self.service.repository.get_meal_type_by_id = MagicMock(return_value=mock_meal_type)
        self.service.repository.create_order = MagicMock(return_value=MealOrder(id=101))
        
        payload = MealOrderCreate(
            visit_id=1,
            patient_id=1,
            meal_type_id=1,
            recipient_type=MealRecipient.PATIENT,
            quantity=Decimal("1.0")
        )
        
        order = self.service.place_order(payload)
        
        assert order.id == 101
        self.service.repository.create_order.assert_called_once()
        # Verify unit_price was pulled from meal_type
        args, kwargs = self.service.repository.create_order.call_args
        assert kwargs["unit_price"] == Decimal("500.00")

    def test_serve_meal_triggers_billing(self):
        # 1. Setup mock order
        mock_meal_type = MealType(name="Breakfast", code="BKT")
        mock_order = MealOrder(
            id=101, 
            visit_id=1, 
            patient_id=1, 
            status=MealStatus.ORDERED,
            quantity=Decimal("1.0"),
            unit_price=Decimal("300.00"),
            total_amount=Decimal("300.00"),
            recipient_type=MealRecipient.PATIENT
        )
        mock_order.meal_type = mock_meal_type
        
        self.service.repository.get_order_by_id = MagicMock(return_value=mock_order)
        
        # 2. Setup mock billing
        mock_billing = Billing(id=50, status="OPEN")
        self.service.billing_repository.get_active_billing_for_visit = MagicMock(return_value=mock_billing)
        
        # 3. Serve the meal
        order = self.service.serve_meal(101, actor_staff_id=9)
        
        # 4. Assertions
        assert order.status == MealStatus.SERVED
        assert order.served_by_staff_id == 9
        
        # Check if billing repository was asked to recompute
        self.service.billing_repository.recompute_totals.assert_called_once_with(mock_billing)
        self.db.commit.assert_called()

    def test_cancel_order_prevents_served_meal_cancellation(self):
        mock_order = MealOrder(id=101, status=MealStatus.SERVED)
        self.service.repository.get_order_by_id = MagicMock(return_value=mock_order)
        
        with pytest.raises(BadRequestError, match="already been served"):
            self.service.cancel_order(101)
