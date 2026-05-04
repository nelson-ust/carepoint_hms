"""Unit tests for TriageService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.enums import VisitStatus
from app.core.exceptions import BadRequestError
from app.services.triage_service import TriageService


def _make_svc():
    db = MagicMock()
    svc = TriageService(db)
    svc.repository = MagicMock()
    return svc


class TestTriageCreate:
    def test_rejects_closed_visit(self):
        svc = _make_svc()
        visit = SimpleNamespace(id=1, status=VisitStatus.CANCELLED)
        svc.repository.get_required_visit.return_value = visit
        payload = MagicMock(visit_id=1, priority="NORMAL", update_visit_priority=False)
        with pytest.raises(BadRequestError, match="closed visit"):
            svc.create(payload)


class TestTriageGet:
    def test_delegates_to_repository(self):
        svc = _make_svc()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestTriageUpdate:
    def test_updates_chief_complaint(self):
        svc = _make_svc()
        triage = SimpleNamespace(id=1, chief_complaint="Old", triage_note=None, priority="NORMAL", visit_id=1)
        svc.repository.get_required_by_id.return_value = triage
        payload = MagicMock(chief_complaint="New complaint", triage_note=None, priority=None, update_visit_priority=False)
        svc.update(1, payload)
        assert triage.chief_complaint == "New complaint"
        svc.db.commit.assert_called_once()
