"""Unit tests for AmbulanceService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError
from app.services.ambulance_service import AmbulanceService


def _make_svc():
    db = MagicMock()
    svc = AmbulanceService(db)
    svc.repository = MagicMock()
    svc.dispatch_repository = MagicMock()
    svc.driver_repository = MagicMock()
    svc.equipment_repository = MagicMock()
    svc.maintenance_repository = MagicMock()
    svc.incident_repository = MagicMock()
    return svc


class TestAmbulanceGet:
    def test_delegates_to_repository(self):
        svc = _make_svc()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestAmbulanceSoftDelete:
    @patch("app.services.ambulance_service.record_security_event")
    def test_blocks_with_active_dispatch(self, mock_event):
        svc = _make_svc()
        amb = SimpleNamespace(id=1)
        svc.repository.get_required_by_id.return_value = amb
        svc.dispatch_repository.has_active_for_ambulance.return_value = True
        with pytest.raises(BadRequestError, match="active dispatches"):
            svc.soft_delete(1)

    @patch("app.services.ambulance_service.record_security_event")
    def test_soft_deletes_when_no_dispatch(self, mock_event):
        svc = _make_svc()
        amb = SimpleNamespace(id=1)
        svc.repository.get_required_by_id.return_value = amb
        svc.dispatch_repository.has_active_for_ambulance.return_value = False
        svc.soft_delete(1)
        svc.repository.soft_delete.assert_called_once_with(amb)
        svc.db.commit.assert_called_once()


class TestAmbulanceCreate:
    def test_creates_and_commits(self):
        svc = _make_svc()
        created = SimpleNamespace(id=1)
        svc.repository.create.return_value = created
        svc.repository.get_required_by_id.return_value = created
        payload = MagicMock()
        payload.model_dump.return_value = {"code": "AMB-001"}
        result = svc.create(payload)
        svc.db.commit.assert_called_once()


class TestAmbulanceConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = AmbulanceService(db)
        assert svc.db is db
