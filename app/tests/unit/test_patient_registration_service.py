"""Unit tests for PatientRegistrationService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.patient_registration_service import PatientRegistrationService


class TestPatientRegistrationConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = PatientRegistrationService(db)
        assert svc.db is db
