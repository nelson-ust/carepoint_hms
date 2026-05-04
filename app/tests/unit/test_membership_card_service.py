"""Unit tests for MembershipCardService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import NotFoundError
from app.services.membership_card_service import MembershipCardService


def _make_svc():
    db = MagicMock()
    svc = MembershipCardService(db)
    svc.repository = MagicMock()
    svc.notification_service = MagicMock()
    return svc


class TestMembershipCardGet:
    def test_raises_not_found(self):
        svc = _make_svc()
        svc.repository.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            svc.get_card(999)

    def test_returns_card(self):
        svc = _make_svc()
        card = SimpleNamespace(id=1, card_number="CARD-001")
        svc.repository.get_by_id.return_value = card
        assert svc.get_card(1) is card


class TestMembershipCardGetByNumber:
    def test_raises_not_found(self):
        svc = _make_svc()
        svc.repository.get_by_card_number.return_value = None
        with pytest.raises(NotFoundError):
            svc.get_card_by_number("CARD-MISSING")

    def test_returns_card(self):
        svc = _make_svc()
        card = SimpleNamespace(id=1, card_number="CARD-001")
        svc.repository.get_by_card_number.return_value = card
        assert svc.get_card_by_number("CARD-001") is card


class TestMembershipCardConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = MembershipCardService(db)
        assert svc.db is db
