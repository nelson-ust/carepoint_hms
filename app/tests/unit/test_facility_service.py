"""Unit tests for FacilityService.

Covers list / get / create / update / delete plus the
subscription-quota guard (max_facilities) and code-uniqueness guard.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.services.facility_service import FacilityService


def _make_svc():
    db = MagicMock()
    return FacilityService(db), db


class TestListAndGet:
    def test_list_returns_all(self):
        svc, db = _make_svc()
        db.query.return_value.all.return_value = ["f1", "f2"]
        assert svc.list_facilities() == ["f1", "f2"]

    def test_get_returns_facility(self):
        svc, db = _make_svc()
        f = SimpleNamespace(id=1, code="HQ")
        db.query.return_value.filter.return_value.first.return_value = f
        assert svc.get_facility(1) is f

    def test_get_raises_when_missing(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundError, match="Facility not found"):
            svc.get_facility(99)


class TestCreateFacility:
    def _payload(self, code="HQ"):
        p = MagicMock()
        p.code = code
        p.name = "Main"
        p.facility_type = "HOSPITAL"
        p.status = "ACTIVE"
        p.phone_number = None
        p.email = None
        p.website = None
        p.address_line_1 = None
        p.address_line_2 = None
        p.city = None
        p.state = None
        p.country = None
        p.postal_code = None
        p.timezone = None
        p.network_id = None
        p.parent_facility_id = None
        return p

    @patch("app.services.facility_service.get_master_db_context")
    @patch("app.services.facility_service.get_current_tenant_id")
    def test_rejects_when_no_active_subscription(self, mock_tenant, mock_master_ctx):
        svc, db = _make_svc()
        mock_tenant.return_value = 7
        master = MagicMock()
        mock_master_ctx.return_value.__enter__.return_value = master
        master.query.return_value.join.return_value.filter.return_value.first.return_value = None
        with pytest.raises(BadRequestError, match="Active subscription required"):
            svc.create_facility(self._payload())

    @patch("app.services.facility_service.get_master_db_context")
    @patch("app.services.facility_service.get_current_tenant_id")
    def test_rejects_when_quota_exceeded(self, mock_tenant, mock_master_ctx):
        svc, db = _make_svc()
        mock_tenant.return_value = 7
        master = MagicMock()
        mock_master_ctx.return_value.__enter__.return_value = master
        plan = SimpleNamespace(max_facilities=2)
        sub = SimpleNamespace(plan=plan)
        master.query.return_value.join.return_value.filter.return_value.first.return_value = sub
        # Tenant DB current count = 2 (== quota)
        db.query.return_value.scalar.return_value = 2
        with pytest.raises(BadRequestError, match="Facility limit reached"):
            svc.create_facility(self._payload())

    @patch("app.services.facility_service.get_master_db_context")
    @patch("app.services.facility_service.get_current_tenant_id")
    def test_rejects_duplicate_code(self, mock_tenant, mock_master_ctx):
        svc, db = _make_svc()
        mock_tenant.return_value = 7
        master = MagicMock()
        mock_master_ctx.return_value.__enter__.return_value = master
        plan = SimpleNamespace(max_facilities=10)
        sub = SimpleNamespace(plan=plan)
        master.query.return_value.join.return_value.filter.return_value.first.return_value = sub
        db.query.return_value.scalar.return_value = 0
        # The duplicate-code lookup goes through self.db.query(Facility).filter(...).first()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=1, code="HQ")
        with pytest.raises(BadRequestError, match="already exists"):
            svc.create_facility(self._payload())

    @patch("app.services.facility_service.get_master_db_context")
    @patch("app.services.facility_service.get_current_tenant_id")
    def test_creates_when_clean(self, mock_tenant, mock_master_ctx):
        svc, db = _make_svc()
        mock_tenant.return_value = 7
        master = MagicMock()
        mock_master_ctx.return_value.__enter__.return_value = master
        plan = SimpleNamespace(max_facilities=10)
        sub = SimpleNamespace(plan=plan)
        master.query.return_value.join.return_value.filter.return_value.first.return_value = sub
        db.query.return_value.scalar.return_value = 0
        db.query.return_value.filter.return_value.first.return_value = None
        svc.create_facility(self._payload())
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

    @patch("app.services.facility_service.get_master_db_context")
    @patch("app.services.facility_service.get_current_tenant_id")
    def test_skips_quota_when_no_tenant(self, mock_tenant, mock_master_ctx):
        svc, db = _make_svc()
        mock_tenant.return_value = None
        db.query.return_value.filter.return_value.first.return_value = None
        svc.create_facility(self._payload())
        # Master DB context never opened
        mock_master_ctx.assert_not_called()
        db.add.assert_called_once()
        db.commit.assert_called_once()


class TestUpdateFacility:
    def test_applies_update(self):
        svc, db = _make_svc()
        f = SimpleNamespace(id=1, name="Old", city="A")
        db.query.return_value.filter.return_value.first.return_value = f
        payload = MagicMock()
        payload.model_dump.return_value = {"name": "New", "city": "B"}
        svc.update_facility(1, payload)
        assert f.name == "New"
        assert f.city == "B"
        db.commit.assert_called_once()

    def test_raises_when_missing(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundError):
            svc.update_facility(1, MagicMock())


class TestDeleteFacility:
    def test_deletes(self):
        svc, db = _make_svc()
        f = SimpleNamespace(id=1)
        db.query.return_value.filter.return_value.first.return_value = f
        svc.delete_facility(1)
        db.delete.assert_called_once_with(f)
        db.commit.assert_called_once()

    def test_raises_when_missing(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundError):
            svc.delete_facility(404)
