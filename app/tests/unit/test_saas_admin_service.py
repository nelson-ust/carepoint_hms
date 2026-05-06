"""Unit tests for SaaSAdminService.

Covers list/get/create/update/delete admins, the platform-role coercion
helper, the SUPER_ADMIN superuser invariant, and the self-delete guard.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.enums import SaaSRole, UserStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.services.saas_admin_service import SaaSAdminService, _coerce_platform_role


def _make_svc():
    db = MagicMock()
    return SaaSAdminService(db), db


class TestCoercePlatformRole:
    def test_none_returns_none(self):
        assert _coerce_platform_role(None) is None

    def test_valid_role_normalised(self):
        out = _coerce_platform_role("super_admin")
        assert out == SaaSRole.SUPER_ADMIN

    def test_invalid_role_raises(self):
        with pytest.raises(BadRequestError, match="Unsupported platform_role"):
            _coerce_platform_role("not_a_role")


class TestListAdmins:
    def test_returns_filtered_list(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = ["a1"]
        assert svc.list_admins() == ["a1"]


class TestGetAdmin:
    def test_returns_admin(self):
        svc, db = _make_svc()
        a = SimpleNamespace(id=1)
        db.query.return_value.filter.return_value.first.return_value = a
        assert svc.get_admin(1) is a

    def test_raises_not_found(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundError, match="SaaS Admin not found"):
            svc.get_admin(99)


class TestCreateAdmin:
    def _payload(self, **overrides):
        p = MagicMock()
        p.first_name = "A"
        p.last_name = "B"
        p.email = overrides.get("email", "X@Example.com")
        p.phone_number = "555"
        p.password = "pw"
        p.platform_role = overrides.get("platform_role", "support_admin")
        p.is_superuser = overrides.get("is_superuser", False)
        return p

    @patch("app.services.saas_admin_service.get_password_hash", return_value="HASH")
    def test_rejects_duplicate_email(self, mock_hash):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=1)
        with pytest.raises(BadRequestError, match="already exists"):
            svc.create_admin(self._payload())

    @patch("app.services.saas_admin_service.get_password_hash", return_value="HASH")
    def test_super_admin_promotes_superuser_flag(self, mock_hash):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        payload = self._payload(platform_role="super_admin", is_superuser=False)
        # The service auto-derives is_superuser=True for SUPER_ADMIN.
        svc.create_admin(payload)
        db.add.assert_called_once()
        added = db.add.call_args[0][0]
        assert added.is_superuser is True
        assert added.platform_role == SaaSRole.SUPER_ADMIN
        assert added.email == "x@example.com"
        assert added.password_hash == "HASH"
        assert added.status == UserStatus.ACTIVE

    @patch("app.services.saas_admin_service.get_password_hash", return_value="HASH")
    def test_default_role_is_support_admin(self, mock_hash):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        payload = self._payload(platform_role=None, is_superuser=False)
        svc.create_admin(payload)
        added = db.add.call_args[0][0]
        assert added.platform_role == SaaSRole.SUPPORT_ADMIN
        assert added.is_superuser is False

    @patch("app.services.saas_admin_service.get_password_hash", return_value="HASH")
    def test_lowercases_email(self, mock_hash):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        payload = self._payload(email="MIXEDCase@Test.IO")
        svc.create_admin(payload)
        added = db.add.call_args[0][0]
        assert added.email == "mixedcase@test.io"


class TestUpdateAdminStatus:
    def test_updates_status(self):
        svc, db = _make_svc()
        admin = SimpleNamespace(id=1, status=UserStatus.ACTIVE, is_deleted=False)
        db.query.return_value.filter.return_value.first.return_value = admin
        svc.update_admin_status(1, "suspended")
        assert admin.status == UserStatus.SUSPENDED
        db.commit.assert_called_once()

    def test_rejects_invalid_status(self):
        svc, db = _make_svc()
        admin = SimpleNamespace(id=1, status=UserStatus.ACTIVE, is_deleted=False)
        db.query.return_value.filter.return_value.first.return_value = admin
        with pytest.raises(BadRequestError, match="Invalid status"):
            svc.update_admin_status(1, "BOGUS")


class TestUpdateAdmin:
    def test_rejects_email_collision(self):
        svc, db = _make_svc()
        admin = SimpleNamespace(id=1, email="me@x.com", is_superuser=False, platform_role=SaaSRole.SUPPORT_ADMIN)
        # First filter().first() => admin, second => collision row
        db.query.return_value.filter.return_value.first.side_effect = [
            admin,
            SimpleNamespace(id=2),
        ]
        payload = MagicMock()
        payload.model_dump.return_value = {"email": "OTHER@x.com"}
        with pytest.raises(BadRequestError, match="Another SaaS Admin"):
            svc.update_admin(1, payload)

    def test_lowercases_email_on_update(self):
        svc, db = _make_svc()
        admin = SimpleNamespace(id=1, email="me@x.com", is_superuser=False, platform_role=SaaSRole.SUPPORT_ADMIN)
        db.query.return_value.filter.return_value.first.side_effect = [admin, None]
        payload = MagicMock()
        payload.model_dump.return_value = {"email": "NEW@X.io"}
        svc.update_admin(1, payload)
        assert admin.email == "new@x.io"

    def test_promoting_to_super_admin_sets_superuser(self):
        svc, db = _make_svc()
        admin = SimpleNamespace(
            id=1,
            email="me@x.com",
            is_superuser=False,
            platform_role=SaaSRole.SUPPORT_ADMIN,
        )
        db.query.return_value.filter.return_value.first.return_value = admin
        payload = MagicMock()
        payload.model_dump.return_value = {"platform_role": "super_admin"}
        svc.update_admin(1, payload)
        assert admin.platform_role == SaaSRole.SUPER_ADMIN
        assert admin.is_superuser is True

    def test_demoting_super_admin_clears_superuser(self):
        svc, db = _make_svc()
        admin = SimpleNamespace(
            id=1,
            email="me@x.com",
            is_superuser=True,
            platform_role=SaaSRole.SUPER_ADMIN,
        )
        db.query.return_value.filter.return_value.first.return_value = admin
        payload = MagicMock()
        payload.model_dump.return_value = {"platform_role": "support_admin"}
        svc.update_admin(1, payload)
        assert admin.platform_role == SaaSRole.SUPPORT_ADMIN
        assert admin.is_superuser is False


class TestDeleteAdmin:
    def test_rejects_self_delete(self):
        svc, db = _make_svc()
        admin = SimpleNamespace(id=5, is_deleted=False, status=UserStatus.ACTIVE,
                                date_deleted=None, deleted_by_id=None)
        db.query.return_value.filter.return_value.first.return_value = admin
        with pytest.raises(BadRequestError, match="cannot delete your own"):
            svc.delete_admin(5, 5)

    @patch("app.services.saas_admin_service.utc_now")
    def test_soft_deletes(self, mock_now):
        svc, db = _make_svc()
        mock_now.return_value = "NOW"
        admin = SimpleNamespace(id=2, is_deleted=False, status=UserStatus.ACTIVE,
                                date_deleted=None, deleted_by_id=None)
        db.query.return_value.filter.return_value.first.return_value = admin
        out = svc.delete_admin(2, current_admin_id=1)
        assert admin.is_deleted is True
        assert admin.status == UserStatus.SUSPENDED
        assert admin.deleted_by_id == 1
        assert admin.date_deleted == "NOW"
        assert out["success"] is True
        db.commit.assert_called_once()
