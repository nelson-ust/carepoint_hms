"""Unit tests for PharmacyService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.pharmacy_service import PharmacyService


class TestPharmacyServiceConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = PharmacyService(db)
        assert svc.db is db


class TestPharmacyServiceWorklist:
    def test_delegates_to_prescription_repository(self):
        db = MagicMock()
        svc = PharmacyService(db)
        svc.prescription_repository = MagicMock()
        svc.worklist()
        svc.prescription_repository.list_pharmacy_worklist.assert_called_once()
