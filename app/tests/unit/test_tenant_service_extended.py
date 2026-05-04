"""Unit tests for TenantService helpers."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from app.services.tenant_service import _period_end_for_plan


class FakePlan:
    def __init__(self, interval: str | None):
        self.interval = interval


class TestPeriodEndForPlan:
    def test_monthly_default(self):
        plan = FakePlan(None)
        start = datetime(2026, 1, 1)
        assert _period_end_for_plan(plan, start) == start + timedelta(days=30)

    def test_yearly(self):
        assert (
            _period_end_for_plan(FakePlan("YEARLY"), datetime(2026, 1, 1))
            == datetime(2027, 1, 1)
        )

    def test_weekly(self):
        assert (
            _period_end_for_plan(FakePlan("WEEKLY"), datetime(2026, 1, 1))
            == datetime(2026, 1, 8)
        )

    def test_daily(self):
        assert (
            _period_end_for_plan(FakePlan("DAILY"), datetime(2026, 1, 1))
            == datetime(2026, 1, 2)
        )

    def test_unknown_falls_back(self):
        # Falls back to monthly.
        assert (
            _period_end_for_plan(FakePlan("CUSTOM"), datetime(2026, 1, 1))
            == datetime(2026, 1, 31)
        )
