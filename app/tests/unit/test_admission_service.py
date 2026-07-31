"""Unit tests for AdmissionService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.enums import AdmissionStatus, BedStatus, VisitStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.services.admission_service import AdmissionService


def _make_svc():
    db = MagicMock()
    svc = AdmissionService(db)
    svc.repository = MagicMock()
    return svc


class TestAdmissionGet:
    def test_delegates_to_repository(self):
        svc = _make_svc()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestListAdmissions:
    def test_rejects_invalid_status_filter(self):
        svc = _make_svc()
        with pytest.raises(BadRequestError, match="Invalid admission status"):
            svc.list_admissions(status="NOT_A_STATUS")

    def test_accepts_valid_status(self):
        svc = _make_svc()
        svc.list_admissions(status="ADMITTED")
        svc.repository.list_admissions.assert_called_once()


class TestAdmit:
    @patch("app.services.admission_service.record_security_event")
    @patch("app.services.admission_service.capture_bed_day_charges_for_admission")
    def test_rejects_missing_ward(self, mock_capture, mock_event):
        svc = _make_svc()
        # Admit now checks for a pre-existing active admission first; make that
        # lookup return None so execution reaches the ward-validation branch.
        svc.repository.get_active_for_patient.return_value = None
        svc.repository.get_ward.return_value = None
        payload = MagicMock(ward_id=99, bed_id=None, visit_id=None)
        with pytest.raises(NotFoundError, match="Ward not found"):
            svc.admit(payload)

    @patch("app.services.admission_service.record_security_event")
    @patch("app.services.admission_service.capture_bed_day_charges_for_admission")
    def test_rejects_unavailable_bed(self, mock_capture, mock_event):
        svc = _make_svc()
        svc.repository.get_active_for_patient.return_value = None
        ward = SimpleNamespace(id=1)
        svc.repository.get_ward.return_value = ward
        bed = SimpleNamespace(id=5, ward_id=1, bed_status=BedStatus.OCCUPIED)
        svc.repository.get_bed.return_value = bed
        payload = MagicMock(ward_id=1, bed_id=5, visit_id=None)
        with pytest.raises(BadRequestError, match="not currently available"):
            svc.admit(payload)

    @patch("app.services.admission_service.record_security_event")
    @patch("app.services.admission_service.capture_bed_day_charges_for_admission")
    def test_rejects_no_available_beds(self, mock_capture, mock_event):
        svc = _make_svc()
        svc.repository.get_active_for_patient.return_value = None
        ward = SimpleNamespace(id=1)
        svc.repository.get_ward.return_value = ward
        svc.repository.first_available_bed.return_value = None
        payload = MagicMock(ward_id=1, bed_id=None, visit_id=None)
        with pytest.raises(BadRequestError, match="No available beds"):
            svc.admit(payload)

    @patch("app.services.admission_service.record_security_event")
    @patch("app.services.admission_service.capture_bed_day_charges_for_admission")
    def test_rejects_closed_visit(self, mock_capture, mock_event):
        svc = _make_svc()
        svc.repository.get_active_for_patient.return_value = None
        ward = SimpleNamespace(id=1)
        bed = SimpleNamespace(id=5, ward_id=1, bed_status=BedStatus.AVAILABLE)
        svc.repository.get_ward.return_value = ward
        svc.repository.get_bed.return_value = bed
        visit = SimpleNamespace(id=10, status=VisitStatus.COMPLETED)
        svc.repository.get_visit.return_value = visit
        payload = MagicMock(ward_id=1, bed_id=5, visit_id=10)
        with pytest.raises(BadRequestError, match="closed visit"):
            svc.admit(payload)


class TestTransferBed:
    def test_rejects_non_open_admission(self):
        svc = _make_svc()
        adm = SimpleNamespace(id=1, admission_status=AdmissionStatus.DISCHARGED, bed_id=5)
        svc.repository.get_required_by_id.return_value = adm
        payload = MagicMock(new_bed_id=10, new_ward_id=None)
        with pytest.raises(BadRequestError, match="not active"):
            svc.transfer_bed(1, payload)

    @patch("app.services.admission_service.record_security_event")
    def test_rejects_unavailable_target_bed(self, mock_event):
        svc = _make_svc()
        adm = SimpleNamespace(id=1, admission_status=AdmissionStatus.ADMITTED, bed_id=5, ward_id=1)
        svc.repository.get_required_by_id.return_value = adm
        target = SimpleNamespace(id=10, bed_status=BedStatus.OUT_OF_SERVICE, ward_id=1)
        svc.repository.get_bed.return_value = target
        payload = MagicMock(new_bed_id=10, new_ward_id=None)
        with pytest.raises(BadRequestError, match="not available"):
            svc.transfer_bed(1, payload)


class TestUpdateStatus:
    def test_rejects_status_change_on_closed_admission(self):
        svc = _make_svc()
        adm = SimpleNamespace(id=1, admission_status=AdmissionStatus.DISCHARGED)
        svc.repository.get_required_by_id.return_value = adm
        payload = MagicMock(new_status="CANCELLED", reason="test")
        with pytest.raises(BadRequestError, match="no longer in an open state"):
            svc.update_status(1, payload)
