"""Unit tests for UserService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.user_service import UserService


class TestUserServiceGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = UserService(db)
        svc.repository = MagicMock()
        svc.get_user(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestUserServiceConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = UserService(db)
        assert svc.db is db


class TestUserServiceListUsers:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = UserService(db)
        svc.repository = MagicMock()
        svc.list_users()
        svc.repository.list_users.assert_called_once()
