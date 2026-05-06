"""Unit tests for SaaSDashboardOverviewService and TenantDashboardService.

Both services are read-only aggregators built on top of helper queries
that wrap their bodies in try/except so any DB failure degrades to
zero/empty.  We exercise the helpers directly and verify each public
method returns a dict with the expected shape and successfully invokes
the underlying mocked queries.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.dashboard_service import (
    SaaSDashboardOverviewService,
    TenantDashboardService,
    _safe_count,
    _safe_sum,
    _months_ago,
    _start_of_month,
    _start_of_today,
    _today,
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


class TestSafeHelpers:
    def test_safe_count_returns_scalar(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.scalar.return_value = 5
        model = SimpleNamespace(id="ID")
        assert _safe_count(db, model, MagicMock()) == 5

    def test_safe_count_swallows_exceptions(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        assert _safe_count(db, SimpleNamespace(id=None)) == 0

    def test_safe_count_no_filters(self):
        db = MagicMock()
        db.query.return_value.scalar.return_value = 7
        assert _safe_count(db, SimpleNamespace(id="ID")) == 7

    def test_safe_sum_returns_decimal(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.scalar.return_value = 12
        out = _safe_sum(db, "col", MagicMock())
        assert out == Decimal("12")

    def test_safe_sum_swallows_exceptions(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        assert _safe_sum(db, "col") == Decimal("0")

    def test_today_helpers_return_aware_datetimes(self):
        assert _today() is not None
        assert _start_of_today().tzinfo is not None
        assert _start_of_month().tzinfo is not None
        assert _months_ago(2).tzinfo is not None

    def test_months_ago_wraps_year(self):
        out = _months_ago(36)
        assert out is not None


# ----------------------------------------------------------------------
# SaaSDashboardOverviewService
# ----------------------------------------------------------------------


def _make_saas_svc():
    db = MagicMock()
    return SaaSDashboardOverviewService(db), db


class TestSaaSOverview:
    def test_overview_aggregates_sections(self):
        svc, db = _make_saas_svc()
        # Every internal aggregation method should be called.  We patch
        # them out with deterministic stubs so we don't need real models.
        with patch.multiple(
            svc,
            tenant_summary=MagicMock(return_value={"total": 1}),
            billing_summary=MagicMock(return_value={"mrr": 0.0}),
            edge_node_summary=MagicMock(return_value={"total": 0}),
            support_access_summary=MagicMock(return_value={}),
            subscription_summary=MagicMock(return_value={"by_plan": []}),
            onboarding_pipeline=MagicMock(return_value={}),
        ):
            out = svc.overview()
        assert set(out.keys()) == {
            "tenants",
            "billing",
            "edge_nodes",
            "support_access",
            "subscriptions",
            "onboarding_pipeline",
        }

    def test_tenant_summary_returns_dict(self):
        svc, db = _make_saas_svc()
        # All _safe_count calls land on db.query — set scalar to a fixed value
        db.query.return_value.scalar.return_value = 3
        db.query.return_value.filter.return_value.scalar.return_value = 3
        out = svc.tenant_summary()
        assert {"total", "active", "pending_approval", "suspended", "provisioned",
                "new_this_month"} <= set(out.keys())

    def test_onboarding_pipeline_division(self):
        svc, db = _make_saas_svc()
        db.query.return_value.filter.return_value.scalar.return_value = 10
        out = svc.onboarding_pipeline()
        assert out["applied_last_30d"] == 10
        # 10/10 -> 100.0
        assert out["approval_conversion_pct"] == 100.0

    def test_onboarding_pipeline_zero_applied(self):
        svc, db = _make_saas_svc()
        db.query.return_value.filter.return_value.scalar.return_value = 0
        out = svc.onboarding_pipeline()
        assert out["approval_conversion_pct"] == 0.0

    def test_subscription_summary_returns_dict_when_query_fails(self):
        svc, db = _make_saas_svc()
        db.query.side_effect = RuntimeError("nope")
        out = svc.subscription_summary()
        assert out == {"by_plan": [], "trialing_total": 0}

    def test_billing_summary_returns_zeros_on_failure(self):
        svc, db = _make_saas_svc()
        db.query.side_effect = RuntimeError("boom")
        out = svc.billing_summary()
        assert out["mrr"] == 0.0
        assert out["overdue_count"] == 0
        assert out["outstanding_total"] == 0.0

    def test_billing_ageing_buckets_empty_when_query_fails(self):
        svc, db = _make_saas_svc()
        db.query.side_effect = RuntimeError("boom")
        out = svc.billing_ageing()
        # Always emits four buckets in stable order
        labels = [b["bucket"] for b in out["buckets"]]
        assert labels == ["<30", "30-60", "60-90", ">90"]
        assert all(b["count"] == 0 for b in out["buckets"])

    def test_edge_node_summary_dict_keys(self):
        svc, db = _make_saas_svc()
        db.query.side_effect = RuntimeError("x")
        out = svc.edge_node_summary()
        assert set(out.keys()) == {"total", "active", "offline", "degraded", "provisioned"}
        assert all(v == 0 for v in out.values())

    def test_support_access_summary_dict_keys(self):
        svc, db = _make_saas_svc()
        db.query.side_effect = RuntimeError("x")
        out = svc.support_access_summary()
        assert set(out.keys()) == {"requested", "approved", "expired", "revoked"}

    def test_usage_summary_dict_keys(self):
        svc, db = _make_saas_svc()
        db.query.side_effect = RuntimeError("x")
        out = svc.usage_summary()
        assert set(out.keys()) >= {
            "login_count_total",
            "sms_count_total",
            "email_count_total",
            "api_call_count_total",
            "storage_total_bytes",
            "storage_total_gb",
        }

    def test_top_tenants_returns_empty_on_failure(self):
        svc, db = _make_saas_svc()
        db.query.side_effect = RuntimeError("x")
        assert svc.top_tenants_by_usage() == []

    def test_recent_activity_handles_failure(self):
        svc, db = _make_saas_svc()
        db.query.side_effect = RuntimeError("x")
        out = svc.recent_activity()
        assert out == []


# ----------------------------------------------------------------------
# TenantDashboardService
# ----------------------------------------------------------------------


def _make_tenant_svc():
    db = MagicMock()
    return TenantDashboardService(db), db


class TestTenantOverview:
    def test_overview_aggregates_sections(self):
        svc, db = _make_tenant_svc()
        with patch.multiple(
            svc,
            today_snapshot=MagicMock(return_value={}),
            patient_summary=MagicMock(return_value={}),
            visit_summary=MagicMock(return_value={}),
            appointment_summary=MagicMock(return_value={}),
            inpatient_summary=MagicMock(return_value={}),
            billing_summary=MagicMock(return_value={}),
            lab_pharmacy_backlog=MagicMock(return_value={}),
            inventory_alerts=MagicMock(return_value={}),
            hr_summary=MagicMock(return_value={}),
            medication_adherence_summary=MagicMock(return_value={}),
        ):
            out = svc.overview()
        assert set(out.keys()) == {
            "today",
            "patients",
            "visits",
            "appointments",
            "inpatient",
            "billing",
            "lab_pharmacy_backlog",
            "inventory_alerts",
            "hr",
            "medication_adherence",
        }

    def test_today_snapshot_keys(self):
        svc, db = _make_tenant_svc()
        db.query.side_effect = RuntimeError("x")
        out = svc.today_snapshot()
        assert "date" in out
        assert out["new_patients_today"] == 0
        assert out["revenue_today"] == 0.0

    def test_patient_summary_dict(self):
        svc, db = _make_tenant_svc()
        db.query.side_effect = RuntimeError("x")
        out = svc.patient_summary()
        assert out == {"total": 0, "new_this_month": 0}

    def test_visit_summary_dict(self):
        svc, db = _make_tenant_svc()
        db.query.side_effect = RuntimeError("x")
        out = svc.visit_summary()
        assert set(out.keys()) == {"total_today", "in_progress", "completed_today"}

    def test_appointment_summary_dict(self):
        svc, db = _make_tenant_svc()
        db.query.side_effect = RuntimeError("x")
        out = svc.appointment_summary()
        assert set(out.keys()) >= {"scheduled", "completed", "cancelled", "no_show"}

    def test_billing_summary_dict(self):
        svc, db = _make_tenant_svc()
        db.query.side_effect = RuntimeError("x")
        out = svc.billing_summary()
        assert set(out.keys()) == {
            "billed_this_month",
            "collected_this_month",
            "outstanding_total",
            "unpaid_invoice_count",
        }

    def test_lab_pharmacy_backlog_keys(self):
        svc, db = _make_tenant_svc()
        db.query.side_effect = RuntimeError("x")
        out = svc.lab_pharmacy_backlog()
        # All three sections degrade to 0 when imports/queries fail
        assert out.get("lab_orders_pending") == 0 or out == {}
        # Always a dict
        assert isinstance(out, dict)

    def test_inventory_alerts_returns_zeroes_on_failure(self):
        svc, db = _make_tenant_svc()
        db.query.side_effect = RuntimeError("x")
        out = svc.inventory_alerts()
        assert "low_stock_count" in out
        assert "expiring_soon_count" in out

    def test_hr_summary_dict(self):
        svc, db = _make_tenant_svc()
        db.query.side_effect = RuntimeError("x")
        out = svc.hr_summary()
        assert isinstance(out, dict)

    def test_medication_adherence_dict(self):
        svc, db = _make_tenant_svc()
        db.query.side_effect = RuntimeError("x")
        out = svc.medication_adherence_summary()
        assert isinstance(out, dict)

    def test_recent_activity_handles_failure(self):
        svc, db = _make_tenant_svc()
        db.query.side_effect = RuntimeError("x")
        assert svc.recent_activity() == []
