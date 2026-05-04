"""Unit tests for PermissionService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.permission_service import PermissionService


def _make_svc():
    db = MagicMock()
    svc = PermissionService(db)
    svc.repository = MagicMock()
    return svc


class TestPermissionGet:
    def test_delegates_to_repository(self):
        svc = _make_svc()
        svc.get_permission(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestPermissionDelete:
    def test_delegates_to_repository(self):
        svc = _make_svc()
        perm = SimpleNamespace(id=1)
        svc.repository.get_required_by_id.return_value = perm
        svc.delete_permission(1)
        svc.repository.soft_delete_permission.assert_called_once_with(perm)
        svc.db.commit.assert_called_once()


class TestPermissionUserHasPermission:
    def test_delegates_to_repository(self):
        svc = _make_svc()
        svc.repository.user_has_permission.return_value = True
        assert svc.user_has_permission(1, "READ_PATIENTS") is True
        svc.repository.user_has_permission.assert_called_once_with(1, "READ_PATIENTS")
