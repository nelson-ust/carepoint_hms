"""Unit tests for BedService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import AlreadyExistsError, BadRequestError, NotFoundError
from app.services.bed_service import BedService


def _make_svc():
    db = MagicMock()
    svc = BedService(db)
    svc.repository = MagicMock()
    return svc


class TestGetBed:
    def test_raises_not_found_when_missing(self):
        svc = _make_svc()
        svc.repository.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            svc.get_bed(999)

    def test_returns_bed_when_found(self):
        svc = _make_svc()
        bed = SimpleNamespace(id=1, bed_no="B-001")
        svc.repository.get_by_id.return_value = bed
        assert svc.get_bed(1) is bed


class TestCreateBed:
    def test_rejects_duplicate_bed_number_in_ward(self):
        svc = _make_svc()
        svc.repository.ward_exists = MagicMock(return_value=True)
        svc.repository.get_by_ward_and_bed_no.return_value = SimpleNamespace(id=99)
        payload = MagicMock(ward_id=1, bed_no="B-001")
        with pytest.raises(AlreadyExistsError):
            svc.create_bed(payload)

    def test_rejects_missing_ward(self):
        svc = _make_svc()
        svc.repository.ward_exists = MagicMock(return_value=False)
        payload = MagicMock(ward_id=999, bed_no="B-001")
        with pytest.raises(NotFoundError):
            svc.create_bed(payload)


class TestUpdateBed:
    def test_raises_not_found_when_bed_missing(self):
        svc = _make_svc()
        svc.repository.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            svc.update_bed(999, MagicMock())

    def test_blocks_ward_move_with_admissions(self):
        svc = _make_svc()
        bed = SimpleNamespace(id=1, ward_id=10, bed_no="B-001")
        svc.repository.get_by_id.return_value = bed
        svc.repository.ward_exists = MagicMock(return_value=True)
        svc.repository.has_admissions.return_value = True
        payload = MagicMock(ward_id=20, bed_no=None, bed_status=None, bed_type=None, notes=None)
        with pytest.raises(BadRequestError, match="cannot be moved"):
            svc.update_bed(1, payload)


class TestDeleteBed:
    def test_raises_not_found(self):
        svc = _make_svc()
        svc.repository.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            svc.delete_bed(999)

    def test_blocks_delete_with_active_admission(self):
        svc = _make_svc()
        bed = SimpleNamespace(id=1)
        svc.repository.get_by_id.return_value = bed
        svc.repository.has_active_admission.return_value = True
        with pytest.raises(BadRequestError, match="active admission"):
            svc.delete_bed(1)

    def test_soft_deletes_successfully(self):
        svc = _make_svc()
        bed = SimpleNamespace(id=1)
        svc.repository.get_by_id.return_value = bed
        svc.repository.has_active_admission.return_value = False
        svc.repository.soft_delete_bed.return_value = bed
        result = svc.delete_bed(1)
        assert result is bed
        svc.db.commit.assert_called_once()
