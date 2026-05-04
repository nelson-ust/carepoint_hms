"""Unit tests for InvitationService."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.core.enums import InvitationStatus
from app.core.exceptions import BadRequestError
from app.services.invitation_service import (
    DEFAULT_EXPIRY_DAYS,
    TOKEN_BYTES,
    InvitationService,
    _build_accept_url,
    _hash_token,
)


class TestTokenHashing:
    def test_deterministic(self):
        assert _hash_token("hello") == _hash_token("hello")

    def test_distinct_for_different_input(self):
        assert _hash_token("a") != _hash_token("b")

    def test_returns_hex(self):
        h = _hash_token("x")
        assert all(c in "0123456789abcdef" for c in h)


class TestBuildAcceptUrl:
    def test_appends_token_query(self):
        url = _build_accept_url("https://acme.example", "tok123")
        assert "token=tok123" in url
        assert url.startswith("https://acme.example/")

    def test_handles_trailing_slash(self):
        url = _build_accept_url("https://acme.example/", "tok")
        assert "//invitations" not in url
        assert url.count("invitations") == 1


class TestServiceConstants:
    def test_token_bytes_strong(self):
        assert TOKEN_BYTES >= 16

    def test_default_expiry_one_week(self):
        assert DEFAULT_EXPIRY_DAYS == 7


class TestCreateInvitationValidation:
    def test_requires_email_or_phone(self):
        svc = InvitationService(MagicMock())
        with pytest.raises(BadRequestError):
            svc.create_invitation()


class TestStatusEnum:
    def test_lifecycle_includes_required(self):
        codes = {s.value for s in InvitationStatus}
        assert {"PENDING", "ACCEPTED", "EXPIRED", "CANCELLED"} <= codes
