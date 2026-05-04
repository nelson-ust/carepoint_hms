"""Unit tests for DischargeService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.enums import AdmissionStatus
from app.core.exceptions import BadRequestError
from app.services.discharge_service import DischargeService


def _make_svc():
    db = MagicMock()
    svc = DischargeService(db)
    svc.repository = MagicMock()
    svc.admission_repository = MagicMock()
    return svc


class TestDischargeGet:
    def test_delegates_to_repository(self):
        svc = _make_svc()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestDischarge:
    @patch("app.services.discharge_service.record_security_event")
    @patch("app.services.discharge_service.check_admission_ready_to_discharge")
    def test_rejects_non_open_admission(self, mock_readiness, mock_event):
        svc = _make_svc()
        adm = SimpleNamespace(id=1, admission_status=AdmissionStatus.DISCHARGED)
        svc.admission_repository.get_required_by_id.return_value = adm
        payload = MagicMock(admission_id=1)
        with pytest.raises(BadRequestError, match="no longer in an open state"):
            svc.discharge(payload)

    @patch("app.services.discharge_service.record_security_event")
    @patch("app.services.discharge_service.check_admission_ready_to_discharge")
    def test_rejects_double_discharge(self, mock_readiness, mock_event):
        svc = _make_svc()
        adm = SimpleNamespace(id=1, admission_status=AdmissionStatus.ADMITTED)
        svc.admission_repository.get_required_by_id.return_value = adm
        svc.repository.get_for_admission.return_value = SimpleNamespace(id=99)
        payload = MagicMock(admission_id=1)
        with pytest.raises(BadRequestError, match="already been discharged"):
            svc.discharge(payload)

    @patch("app.services.discharge_service.record_security_event")
    @patch("app.services.discharge_service.check_admission_ready_to_discharge")
    def test_blocks_discharge_with_open_orders(self, mock_readiness, mock_event):
        svc = _make_svc()
        adm = SimpleNamespace(id=1, admission_status=AdmissionStatus.ADMITTED, visit_id=10, bed_id=5, patient_id=100)
        svc.admission_repository.get_required_by_id.return_value = adm
        svc.repository.get_for_admission.return_value = None
        mock_readiness.return_value = (False, ["Open lab order #42"])
        payload = MagicMock(admission_id=1, force=False)
        with pytest.raises(BadRequestError, match="open clinical orders"):
            svc.discharge(payload)


class TestReadiness:
    def test_returns_readiness_dict(self):
        svc = _make_svc()
        adm = SimpleNamespace(id=1, visit_id=10)
        svc.admission_repository.get_required_by_id.return_value = adm
        with patch("app.services.discharge_service.check_admission_ready_to_discharge") as mock_check:
            mock_check.return_value = (True, [])
            result = svc.readiness_for_admission(1)
        assert result["is_ready"] is True
        assert result["blockers"] == []
