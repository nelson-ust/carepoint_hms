"""Unit tests for DiagnosisService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.enums import VisitStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.services.diagnosis_service import DiagnosisService


def _make_svc():
    db = MagicMock()
    svc = DiagnosisService(db)
    svc.repository = MagicMock()
    return svc


class TestDiagnosisGet:
    def test_delegates_to_repository(self):
        svc = _make_svc()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestDiagnosisCreate:
    def test_rejects_missing_visit(self):
        svc = _make_svc()
        svc.repository.get_visit.return_value = None
        payload = MagicMock(visit_id=999)
        with pytest.raises(NotFoundError, match="Visit not found"):
            svc.create(payload)

    def test_rejects_closed_visit(self):
        svc = _make_svc()
        visit = SimpleNamespace(id=1, status=VisitStatus.CANCELLED)
        svc.repository.get_visit.return_value = visit
        payload = MagicMock(visit_id=1)
        with pytest.raises(BadRequestError, match="closed visit"):
            svc.create(payload)

    def test_creates_on_open_visit(self):
        svc = _make_svc()
        visit = SimpleNamespace(id=1, status=VisitStatus.IN_PROGRESS)
        svc.repository.get_visit.return_value = visit
        created = SimpleNamespace(id=10)
        svc.repository.create.return_value = created
        svc.repository.get_required_by_id.return_value = created
        payload = MagicMock(
            visit_id=1,
            consultation_id=None,
            diagnosis_name="Malaria",
            diagnosis_code="B50",
            diagnosis_type="PRIMARY",
            diagnosis_note="Test",
        )
        result = svc.create(payload)
        assert result is created
        svc.db.commit.assert_called_once()


class TestDiagnosisUpdate:
    def test_updates_fields(self):
        svc = _make_svc()
        diag = SimpleNamespace(id=1, diagnosis_name="Old")
        svc.repository.get_required_by_id.return_value = diag
        payload = MagicMock()
        payload.model_dump.return_value = {"diagnosis_name": "New"}
        svc.update(1, payload)
        assert diag.diagnosis_name == "New"
        svc.db.commit.assert_called_once()
