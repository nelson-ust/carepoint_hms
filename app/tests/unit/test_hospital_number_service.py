"""Unit tests for the configurable Hospital Membership Number engine.

These lock in the four numbering schemes from the product spec and the
sequence-reset behaviour, exercising the pure formatting core with lightweight
config stand-ins (no database required).
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.hospital_number_service import HospitalNumberService


def _svc():
    return HospitalNumberService(MagicMock())


def _cfg(**overrides):
    base = dict(
        prefix="HN",
        suffix=None,
        branch_code=None,
        separator="-",
        include_year=False,
        year_format="YYYY",
        include_month=False,
        min_digits=6,
        reset_mode="CONTINUOUS",
        next_sequence=1,
        current_period=None,
        is_active=True,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


NOW = datetime(2026, 3, 14, 9, 30, tzinfo=timezone.utc)


class TestSpecFormats:
    """Every example format quoted in the enhancement spec must reproduce."""

    def test_simple_prefix_sequence(self):
        cfg = _cfg(prefix="HSP", min_digits=6)
        assert _svc()._format(cfg, 1, NOW) == "HSP-000001"

    def test_branch_and_year(self):
        cfg = _cfg(prefix="CPH", branch_code="PHC", include_year=True,
                   year_format="YYYY", min_digits=6)
        assert _svc()._format(cfg, 123, NOW) == "CPH-PHC-2026-000123"

    def test_branch_no_year(self):
        cfg = _cfg(prefix="LAG", branch_code="OPD", include_year=False,
                   min_digits=6)
        assert _svc()._format(cfg, 45, NOW) == "LAG-OPD-000045"

    def test_prefix_year_wide_sequence(self):
        cfg = _cfg(prefix="HOSP", include_year=True, year_format="YYYY",
                   min_digits=6)
        assert _svc()._format(cfg, 1256, NOW) == "HOSP-2026-001256"


class TestFormattingOptions:
    def test_two_digit_year(self):
        cfg = _cfg(prefix="CP", include_year=True, year_format="YY", min_digits=4)
        assert _svc()._format(cfg, 7, NOW) == "CP-26-0007"

    def test_year_and_month(self):
        cfg = _cfg(prefix="CP", include_year=True, include_month=True,
                   year_format="YYYY", min_digits=5)
        assert _svc()._format(cfg, 9, NOW) == "CP-202603-00009"

    def test_month_only(self):
        cfg = _cfg(prefix="CP", include_year=False, include_month=True, min_digits=3)
        assert _svc()._format(cfg, 2, NOW) == "CP-03-002"

    def test_suffix_appended_with_separator(self):
        cfg = _cfg(prefix="CP", suffix="NG", min_digits=4)
        assert _svc()._format(cfg, 5, NOW) == "CP-0005-NG"

    def test_custom_separator(self):
        cfg = _cfg(prefix="CP", branch_code="A", separator="/", min_digits=3)
        assert _svc()._format(cfg, 8, NOW) == "CP/A/008"

    def test_min_digits_does_not_truncate_large_sequence(self):
        cfg = _cfg(prefix="CP", min_digits=3)
        assert _svc()._format(cfg, 123456, NOW) == "CP-123456"


class TestResetKey:
    def test_continuous_has_no_reset_key(self):
        assert HospitalNumberService._reset_key(_cfg(reset_mode="CONTINUOUS"), NOW) is None

    def test_annual_reset_key(self):
        assert HospitalNumberService._reset_key(_cfg(reset_mode="ANNUAL"), NOW) == "2026"

    def test_monthly_reset_key(self):
        assert HospitalNumberService._reset_key(_cfg(reset_mode="MONTHLY"), NOW) == "202603"


class TestPreviewSequence:
    def test_preview_uses_next_sequence(self):
        svc = _svc()
        cfg = _cfg(prefix="HSP", next_sequence=42, min_digits=6)
        svc.get_or_create_config = MagicMock(return_value=cfg)
        svc._now = staticmethod(lambda: NOW)
        assert svc.preview() == "HSP-000042"

    def test_preview_resets_when_period_rolled_over(self):
        svc = _svc()
        # Annual reset, stored period is last year -> preview should show seq 1.
        cfg = _cfg(prefix="HSP", reset_mode="ANNUAL", next_sequence=500,
                   current_period="2025", min_digits=6)
        svc.get_or_create_config = MagicMock(return_value=cfg)
        svc._now = staticmethod(lambda: NOW)
        assert svc.preview() == "HSP-000001"


class TestAllocateNext:
    def test_allocates_and_advances_sequence(self):
        svc = _svc()
        cfg = _cfg(prefix="HSP", next_sequence=10, min_digits=6)
        svc.get_or_create_config = MagicMock(return_value=cfg)
        svc._now = staticmethod(lambda: NOW)
        first = svc.allocate_next()
        assert first == "HSP-000010"
        assert cfg.next_sequence == 11

    def test_skips_taken_numbers(self):
        svc = _svc()
        cfg = _cfg(prefix="HSP", next_sequence=10, min_digits=6)
        svc.get_or_create_config = MagicMock(return_value=cfg)
        svc._now = staticmethod(lambda: NOW)
        taken = {"HSP-000010", "HSP-000011"}
        result = svc.allocate_next(uniqueness_check=lambda c: c in taken)
        assert result == "HSP-000012"
