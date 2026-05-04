"""Unit tests for StockMovementService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.stock_movement_service import StockMovementService


class TestStockMovementGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = StockMovementService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestStockMovementConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = StockMovementService(db)
        assert svc.db is db
