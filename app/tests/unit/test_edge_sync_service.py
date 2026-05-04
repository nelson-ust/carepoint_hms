"""Unit tests for EdgeSyncService helpers."""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.edge_sync_service import (
    _generate_token,
    _hash_token,
    _parse_dt,
)


class TestTokenGeneration:
    def test_token_has_prefix(self):
        assert _generate_token().startswith("edge_")

    def test_tokens_unique(self):
        a = _generate_token()
        b = _generate_token()
        assert a != b


class TestTokenHashing:
    def test_deterministic(self):
        assert _hash_token("hello") == _hash_token("hello")

    def test_different_tokens_different_hashes(self):
        assert _hash_token("a") != _hash_token("b")


class TestParseDt:
    def test_handles_iso_string(self):
        dt = _parse_dt("2026-05-02T12:34:56+00:00")
        assert isinstance(dt, datetime)
        assert dt.tzinfo is not None

    def test_handles_z_suffix(self):
        dt = _parse_dt("2026-05-02T12:34:56Z")
        assert isinstance(dt, datetime)

    def test_handles_datetime_passthrough(self):
        now = datetime.now(timezone.utc)
        assert _parse_dt(now) is now

    def test_returns_none_on_invalid(self):
        assert _parse_dt("not a date") is None

    def test_returns_none_on_empty(self):
        assert _parse_dt(None) is None
