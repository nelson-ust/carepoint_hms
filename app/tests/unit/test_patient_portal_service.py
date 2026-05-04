"""Unit tests for PatientPortalService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.patient_portal_service import PatientPortalService


class TestPatientPortalConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = PatientPortalService(db)
        assert svc.db is db
