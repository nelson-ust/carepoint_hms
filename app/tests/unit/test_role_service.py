"""Unit tests for RoleService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.role_service import RoleService


def _make_svc():
    db = MagicMock()
    svc = RoleService(db)
    svc.repository = MagicMock()
    return svc


class TestRoleServiceGet:
    def test_delegates_to_repository(self):
        svc = _make_svc()
        svc.get_role(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestRoleServiceDeleteRole:
    def test_delegates_to_repository(self):
        svc = _make_svc()
        role = SimpleNamespace(id=1, user_roles=[])
        svc.repository.get_required_by_id.return_value = role
        svc.delete_role(1)
        svc.repository.soft_delete_role.assert_called_once_with(role)
        svc.db.commit.assert_called_once()


class TestRoleServiceConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = RoleService(db)
        assert svc.db is db
