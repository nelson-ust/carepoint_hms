"""Unit tests for ConsultationService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.enums import EncounterStatus, VisitStatus
from app.core.exceptions import BadRequestError
from app.services.consultation_service import ConsultationService


def _make_svc():
    db = MagicMock()
    svc = ConsultationService(db)
    svc.repository = MagicMock()
    return svc


class TestConsultationGet:
    def test_delegates_to_repository(self):
        svc = _make_svc()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestConsultationCreate:
    def test_rejects_closed_visit(self):
        svc = _make_svc()
        visit = SimpleNamespace(id=1, status=VisitStatus.COMPLETED)
        svc.repository.get_required_visit.return_value = visit
        payload = MagicMock(visit_id=1)
        with pytest.raises(BadRequestError, match="closed visit"):
            svc.create(payload)

    def test_rejects_duplicate_open_consultation(self):
        svc = _make_svc()
        visit = SimpleNamespace(id=1, status=VisitStatus.IN_PROGRESS)
        svc.repository.get_required_visit.return_value = visit
        svc.repository.get_open_for_visit.return_value = SimpleNamespace(id=99)
        payload = MagicMock(visit_id=1)
        with pytest.raises(BadRequestError, match="open consultation already exists"):
            svc.create(payload)


class TestConsultationFinalize:
    def test_rejects_cancelled_consultation(self):
        svc = _make_svc()
        consultation = SimpleNamespace(id=1, status=EncounterStatus.CANCELLED)
        svc.repository.get_required_by_id.return_value = consultation
        payload = MagicMock()
        with pytest.raises(BadRequestError, match="Cancelled"):
            svc.finalize(1, payload)


class TestConsultationCancel:
    def test_rejects_already_closed(self):
        svc = _make_svc()
        consultation = SimpleNamespace(id=1, status=EncounterStatus.CLOSED)
        svc.repository.get_required_by_id.return_value = consultation
        with pytest.raises(BadRequestError, match="no longer open"):
            svc.cancel(1)

    def test_rejects_already_cancelled(self):
        svc = _make_svc()
        consultation = SimpleNamespace(id=1, status=EncounterStatus.CANCELLED)
        svc.repository.get_required_by_id.return_value = consultation
        with pytest.raises(BadRequestError, match="no longer open"):
            svc.cancel(1)
