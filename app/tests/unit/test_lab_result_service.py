"""Unit tests for LabResultService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.lab_result_service import LabResultService


class TestLabResultGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = LabResultService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestLabResultGetByOrderItem:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = LabResultService(db)
        svc.repository = MagicMock()
        svc.get_by_order_item(5)
        svc.repository.get_by_order_item.assert_called_once_with(5)


class TestLabResultConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = LabResultService(db)
        assert svc.db is db
