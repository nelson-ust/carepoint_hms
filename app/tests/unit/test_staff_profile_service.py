"""Unit tests for StaffProfileService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import NotFoundError
from app.services.staff_profile_service import StaffProfileService


def _make_svc():
    db = MagicMock()
    svc = StaffProfileService(db)
    svc.repository = MagicMock()
    return svc


class TestStaffProfileGet:
    def test_raises_not_found(self):
        svc = _make_svc()
        svc.repository.get_staff_profile_by_id.return_value = None
        with pytest.raises(NotFoundError):
            svc.get_staff_profile(999)

    def test_returns_profile(self):
        svc = _make_svc()
        profile = SimpleNamespace(id=1, staff_no="STF-001")
        svc.repository.get_staff_profile_by_id.return_value = profile
        assert svc.get_staff_profile(1) is profile


class TestStaffProfileGetUser:
    def test_raises_not_found(self):
        svc = _make_svc()
        svc.repository.get_user_by_id.return_value = None
        with pytest.raises(NotFoundError):
            svc.get_user(999)

    def test_returns_user(self):
        svc = _make_svc()
        user = SimpleNamespace(id=1, username="test")
        svc.repository.get_user_by_id.return_value = user
        assert svc.get_user(1) is user


class TestStaffProfileConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = StaffProfileService(db)
        assert svc.db is db
