"""Unit tests for InventoryStoreService and InventoryStockItemService."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.inventory_service import (
    InventoryStoreService,
    InventoryStockItemService,
    StockMovementService,
)


class TestInventoryStoreGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = InventoryStoreService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestInventoryStoreSoftDelete:
    def test_soft_deletes(self):
        db = MagicMock()
        svc = InventoryStoreService(db)
        svc.repository = MagicMock()
        svc.repository.get_required_by_id.return_value = SimpleNamespace(id=1)
        svc.soft_delete(1)
        db.commit.assert_called_once()


class TestInventoryStockItemGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = InventoryStockItemService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestStockMovementService:
    def test_create_delegates_to_repository_and_adjusts_quantity(self):
        db = MagicMock()
        svc = StockMovementService(db)
        svc.repository = MagicMock()
        svc.item_repository = MagicMock()
        
        item = SimpleNamespace(id=1, store_id=10, quantity_on_hand=Decimal("10.0"))
        svc.item_repository.get_required_by_id.return_value = item
        svc.item_repository.adjust_quantity.return_value = item
        
        payload = MagicMock()
        payload.stock_item_id = 1
        payload.store_id = 10
        payload.movement_type = "PURCHASE"
        payload.quantity = Decimal("5.0")
        payload.model_dump.return_value = {"quantity": Decimal("5.0"), "movement_type": "PURCHASE"}
        
        svc.create(payload)
        
        svc.item_repository.adjust_quantity.assert_called_once()
        svc.repository.create.assert_called_once()
        db.commit.assert_called_once()


class TestInventoryConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = InventoryStoreService(db)
        assert svc.db is db
