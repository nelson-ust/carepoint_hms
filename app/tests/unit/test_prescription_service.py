"""Unit tests for PrescriptionService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.prescription_service import PrescriptionService


class TestPrescriptionGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = PrescriptionService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestPrescriptionListForVisit:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = PrescriptionService(db)
        svc.repository = MagicMock()
        svc.list_for_visit(1)
        svc.repository.list_for_visit.assert_called_once()


class TestPrescriptionConstruction:
    def test_initializes_with_session(self):
        db = MagicMock()
        svc = PrescriptionService(db)
        assert svc.db is db
