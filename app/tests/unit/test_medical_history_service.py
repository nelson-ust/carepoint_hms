"""Unit tests for PatientMedicalHistoryService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.medical_history_service import PatientMedicalHistoryService


class TestMedicalHistoryConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = PatientMedicalHistoryService(db)
        assert svc.db is db
