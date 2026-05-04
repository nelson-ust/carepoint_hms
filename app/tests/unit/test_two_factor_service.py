"""Unit tests for TwoFactorService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.two_factor_service import TwoFactorService


def _make_svc():
    db = MagicMock()
    svc = TwoFactorService(db)
    svc.repository = MagicMock()
    return svc


class TestTwoFactorGetChallenge:
    def test_delegates_to_repository(self):
        svc = _make_svc()
        svc.get_challenge(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestTwoFactorConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = TwoFactorService(db)
        assert svc.db is db
