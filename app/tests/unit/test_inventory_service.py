"""Unit tests for InventoryStoreService and InventoryStockItemService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.inventory_service import InventoryStoreService, InventoryStockItemService


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


class TestInventoryConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = InventoryStoreService(db)
        assert svc.db is db
