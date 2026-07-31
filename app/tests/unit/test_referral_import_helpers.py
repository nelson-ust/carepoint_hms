"""Unit tests for the pure helpers behind cross-hospital referral import:
date/enum coercion and the 'two most recent visits' selection.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from unittest.mock import MagicMock

from app.services.referral_import_service import (
    ReferralImportService,
    _coerce_enum,
    _parse_date,
    _parse_dt,
)


class TestParseDt:
    def test_passthrough_datetime(self):
        dt = datetime(2026, 1, 2, 3, 4, 5)
        assert _parse_dt(dt) is dt

    def test_iso_with_micros(self):
        assert _parse_dt("2026-03-14T09:30:00.123456") == datetime(2026, 3, 14, 9, 30, 0, 123456)

    def test_iso_without_micros(self):
        assert _parse_dt("2026-03-14T09:30:00") == datetime(2026, 3, 14, 9, 30, 0)

    def test_space_separated(self):
        assert _parse_dt("2026-03-14 09:30:00") == datetime(2026, 3, 14, 9, 30, 0)

    def test_date_only(self):
        assert _parse_dt("2026-03-14") == datetime(2026, 3, 14, 0, 0, 0)

    def test_garbage_returns_none(self):
        assert _parse_dt("not-a-date") is None
        assert _parse_dt(None) is None
        assert _parse_dt("") is None


class TestParseDate:
    def test_passthrough_date(self):
        d = date(2026, 3, 14)
        assert _parse_date(d) is d

    def test_extracts_date_from_datetime_string(self):
        assert _parse_date("2026-03-14T09:30:00") == date(2026, 3, 14)

    def test_none_on_garbage(self):
        assert _parse_date("xyz") is None


class Color(Enum):
    RED = "red"
    BLUE = "blue"


class TestCoerceEnum:
    def test_by_value(self):
        assert _coerce_enum(Color, "red") is Color.RED

    def test_by_name(self):
        assert _coerce_enum(Color, "BLUE") is Color.BLUE

    def test_unknown_returns_none(self):
        assert _coerce_enum(Color, "green") is None

    def test_none_inputs(self):
        assert _coerce_enum(Color, None) is None
        assert _coerce_enum(None, "red") is None


class TestRecentVisits:
    def _svc(self):
        return ReferralImportService.__new__(ReferralImportService)

    def test_picks_two_most_recent_by_date(self):
        payload = {
            "sections": {
                "Visit": [
                    {"id": 1, "visit_date": "2026-01-01"},
                    {"id": 2, "visit_date": "2026-03-01"},
                    {"id": 3, "visit_date": "2026-02-01"},
                ]
            }
        }
        recent = self._svc()._recent_visits(payload, limit=2)
        assert [v["id"] for v in recent] == [2, 3]

    def test_handles_missing_section(self):
        assert self._svc()._recent_visits({}, limit=2) == []

    def test_respects_limit(self):
        payload = {"sections": {"Visit": [
            {"id": i, "check_in_time": f"2026-03-{i:02d}T08:00:00"} for i in range(1, 6)
        ]}}
        recent = self._svc()._recent_visits(payload, limit=2)
        assert [v["id"] for v in recent] == [5, 4]
