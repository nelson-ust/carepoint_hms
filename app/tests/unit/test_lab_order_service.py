"""Unit tests for LabOrderService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.lab_order_service import LabOrderService


class TestLabOrderGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = LabOrderService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestLabOrderListForVisit:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = LabOrderService(db)
        svc.repository = MagicMock()
        svc.list_for_visit(1)
        svc.repository.list_for_visit.assert_called_once()


class TestLabOrderConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = LabOrderService(db)
        assert svc.db is db
