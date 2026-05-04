"""Unit tests for DispenseService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.dispense_service import DispenseService


class TestDispenseGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = DispenseService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestDispenseListForVisit:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = DispenseService(db)
        svc.repository = MagicMock()
        svc.list_for_visit(1)
        svc.repository.list_for_visit.assert_called_once()

    def test_list_for_prescription(self):
        db = MagicMock()
        svc = DispenseService(db)
        svc.repository = MagicMock()
        svc.list_for_prescription(5)
        svc.repository.list_for_prescription.assert_called_once_with(5)


class TestDispenseConstruction:
    def test_initializes_with_session(self):
        db = MagicMock()
        svc = DispenseService(db)
        assert svc.db is db
