"""Unit tests for ReferralService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.referral_service import ReferralService


class TestReferralGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = ReferralService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestReferralConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = ReferralService(db)
        assert svc.db is db


class TestReferralListReferrals:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = ReferralService(db)
        svc.repository = MagicMock()
        svc.list_referrals(skip=0, limit=10)
        svc.repository.list_referrals.assert_called_once()
