"""Unit tests for WardService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import AlreadyExistsError, BadRequestError, NotFoundError
from app.services.ward_service import WardService


def _make_svc():
    db = MagicMock()
    svc = WardService(db)
    svc.repository = MagicMock()
    return svc


class TestGetWard:
    def test_raises_not_found(self):
        svc = _make_svc()
        svc.repository.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            svc.get_ward(999)

    def test_returns_ward(self):
        svc = _make_svc()
        ward = SimpleNamespace(id=1, name="ICU")
        svc.repository.get_by_id.return_value = ward
        assert svc.get_ward(1) is ward


class TestCreateWard:
    def test_rejects_duplicate_code(self):
        svc = _make_svc()
        svc.repository.get_by_code.return_value = SimpleNamespace(id=1)
        payload = MagicMock(code="ICU", name="Intensive Care")
        with pytest.raises(AlreadyExistsError, match="code"):
            svc.create_ward(payload)

    def test_rejects_duplicate_name(self):
        svc = _make_svc()
        svc.repository.get_by_code.return_value = None
        svc.repository.get_by_name.return_value = SimpleNamespace(id=1)
        payload = MagicMock(code="ICU2", name="ICU")
        with pytest.raises(AlreadyExistsError, match="name"):
            svc.create_ward(payload)


class TestUpdateWard:
    def test_raises_not_found(self):
        svc = _make_svc()
        svc.repository.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            svc.update_ward(999, MagicMock())

    def test_rejects_duplicate_code_on_update(self):
        svc = _make_svc()
        ward = SimpleNamespace(id=1, code="ICU", name="ICU Ward")
        svc.repository.get_by_id.return_value = ward
        svc.repository.get_by_code.return_value = SimpleNamespace(id=2)
        payload = MagicMock(code="WARD-B", name=None, ward_type=None, description=None)
        with pytest.raises(AlreadyExistsError):
            svc.update_ward(1, payload)


class TestDeleteWard:
    def test_raises_not_found(self):
        svc = _make_svc()
        svc.repository.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            svc.delete_ward(999)

    def test_blocks_delete_with_beds(self):
        svc = _make_svc()
        svc.repository.get_by_id.return_value = SimpleNamespace(id=1)
        svc.repository.has_beds.return_value = True
        with pytest.raises(BadRequestError, match="bed"):
            svc.delete_ward(1)

    def test_blocks_delete_with_admissions(self):
        svc = _make_svc()
        svc.repository.get_by_id.return_value = SimpleNamespace(id=1)
        svc.repository.has_beds.return_value = False
        svc.repository.has_admissions.return_value = True
        with pytest.raises(BadRequestError, match="admission"):
            svc.delete_ward(1)

    def test_deletes_successfully(self):
        svc = _make_svc()
        ward = SimpleNamespace(id=1)
        svc.repository.get_by_id.return_value = ward
        svc.repository.has_beds.return_value = False
        svc.repository.has_admissions.return_value = False
        svc.repository.soft_delete_ward.return_value = ward
        result = svc.delete_ward(1)
        assert result is ward
