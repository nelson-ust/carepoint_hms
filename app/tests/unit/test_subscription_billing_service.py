"""Unit tests for SubscriptionBillingService."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.services.subscription_billing_service import (
    DEFAULT_PAYMENT_TERMS_DAYS,
    DEFAULT_PRE_ISSUE_DAYS,
    SubscriptionBillingService,
    _generate_invoice_number,
    _generate_receipt_number,
    _period_end,
    _resolve_billing_recipients,
)


class FakePlan:
    def __init__(self, interval: str = "MONTHLY"):
        self.interval = interval


class TestPeriodEnd:
    def test_monthly(self):
        plan = FakePlan("MONTHLY")
        start = datetime(2026, 1, 1)
        assert _period_end(plan, start) == start + timedelta(days=30)

    def test_yearly(self):
        plan = FakePlan("YEARLY")
        start = datetime(2026, 1, 1)
        assert _period_end(plan, start) == start + timedelta(days=365)

    def test_quarterly(self):
        plan = FakePlan("QUARTERLY")
        start = datetime(2026, 1, 1)
        assert _period_end(plan, start) == start + timedelta(days=91)

    def test_weekly(self):
        plan = FakePlan("WEEKLY")
        start = datetime(2026, 1, 1)
        assert _period_end(plan, start) == start + timedelta(days=7)

    def test_unknown_falls_back_to_monthly(self):
        plan = FakePlan("UNKNOWN")
        start = datetime(2026, 1, 1)
        assert _period_end(plan, start) == start + timedelta(days=30)


class TestNumberGenerators:
    def test_invoice_number_format(self):
        tenant = MagicMock(code="acme")
        n = _generate_invoice_number(tenant)
        assert n.startswith("INV-ACME-")

    def test_receipt_number_format(self):
        tenant = MagicMock(code="acme")
        n = _generate_receipt_number(tenant)
        assert n.startswith("RCT-ACME-")

    def test_handles_missing_code(self):
        tenant = MagicMock()
        tenant.code = None
        assert _generate_invoice_number(tenant).startswith("INV-TNT-")


class TestResolveBillingRecipients:
    def test_dedupes_case_insensitively(self):
        tenant = MagicMock(billing_email="Billing@Acme.COM")
        recs = _resolve_billing_recipients(tenant)
        assert recs == ["billing@acme.com"]

    def test_empty_when_no_billing_email(self):
        tenant = MagicMock(billing_email=None)
        recs = _resolve_billing_recipients(tenant)
        assert recs == []


class TestServiceConstants:
    def test_default_pre_issue_days_is_a_week(self):
        assert DEFAULT_PRE_ISSUE_DAYS == 7

    def test_default_terms_two_weeks(self):
        assert DEFAULT_PAYMENT_TERMS_DAYS == 14


class TestServiceConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = SubscriptionBillingService(db)
        assert svc.db is db
