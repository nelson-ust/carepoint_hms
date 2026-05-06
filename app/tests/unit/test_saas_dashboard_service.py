"""Unit tests for SaaSDashboardService.

A small read-only aggregator: a single ``get_dashboard_metrics`` method
that issues several count/sum queries and produces a metrics schema.
The schema constructors and underlying ORM queries are mocked so the
test is hermetic.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.saas_dashboard_service import SaaSDashboardService


def _make_svc():
    db = MagicMock()
    return SaaSDashboardService(db), db


class TestConstruction:
    def test_holds_session(self):
        svc, db = _make_svc()
        assert svc.db is db


class TestGetDashboardMetrics:
    @patch("app.services.saas_dashboard_service.SaaSDashboardMetricsSchema")
    @patch("app.services.saas_dashboard_service.RecentNotificationSchema")
    @patch("app.services.saas_dashboard_service.MetricBreakdown")
    def test_aggregates_metrics(self, mock_breakdown, mock_recent_schema, mock_metrics_schema):
        svc, db = _make_svc()

        # The service issues five distinct query() chains in order.
        # Each call to self.db.query(...) returns a fresh chain so that
        # we can configure scalar() / .all() per section independently.
        chains = [MagicMock() for _ in range(6)]
        # 0: total_tenants — query(func.count).scalar()
        chains[0].scalar.return_value = 10
        # 1: active_tenants — query(...).filter(...).scalar()
        chains[1].filter.return_value.scalar.return_value = 7
        # 2: pending_tenants
        chains[2].filter.return_value.scalar.return_value = 2
        # 3: suspended_tenants
        chains[3].filter.return_value.scalar.return_value = 1
        # 4: MRR — query(func.sum).join(...).filter(...).scalar()
        chains[4].join.return_value.filter.return_value.scalar.return_value = Decimal("123.45")
        # 5: subscription breakdown — query(...).join(...).filter(...).group_by(...).all()
        chains[5].join.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("Pro", 5),
            ("Enterprise", 2),
        ]
        # We'll need a 7th chain for the recent_notifs query
        notif_chain = MagicMock()
        notif_chain.order_by.return_value.limit.return_value.all.return_value = [
            SimpleNamespace(
                id=1,
                subject="hello",
                body="b",
                status=SimpleNamespace(name="UNREAD"),
                is_read=False,
                date_created=SimpleNamespace(isoformat=lambda: "T"),
            )
        ]
        db.query.side_effect = chains + [notif_chain]

        svc.get_dashboard_metrics()

        # Two MetricBreakdown rows constructed
        assert mock_breakdown.call_count == 2
        # One RecentNotificationSchema row constructed
        assert mock_recent_schema.call_count == 1
        # Final metrics schema invoked once
        mock_metrics_schema.assert_called_once()
        kwargs = mock_metrics_schema.call_args.kwargs
        assert kwargs["total_tenants"] == 10
        assert kwargs["active_tenants"] == 7
        assert kwargs["pending_tenants"] == 2
        assert kwargs["suspended_tenants"] == 1
        assert kwargs["total_mrr"] == Decimal("123.45")

    @patch("app.services.saas_dashboard_service.SaaSDashboardMetricsSchema")
    @patch("app.services.saas_dashboard_service.RecentNotificationSchema")
    @patch("app.services.saas_dashboard_service.MetricBreakdown")
    def test_defaults_when_counts_none(self, mock_breakdown, mock_recent_schema, mock_metrics_schema):
        svc, db = _make_svc()
        chains = [MagicMock() for _ in range(6)]
        # All scalar/filter+scalar return None
        chains[0].scalar.return_value = None
        for i in (1, 2, 3):
            chains[i].filter.return_value.scalar.return_value = None
        chains[4].join.return_value.filter.return_value.scalar.return_value = None
        chains[5].join.return_value.filter.return_value.group_by.return_value.all.return_value = []
        notif_chain = MagicMock()
        notif_chain.order_by.return_value.limit.return_value.all.return_value = []
        db.query.side_effect = chains + [notif_chain]

        svc.get_dashboard_metrics()
        kwargs = mock_metrics_schema.call_args.kwargs
        assert kwargs["total_tenants"] == 0
        assert kwargs["active_tenants"] == 0
        assert kwargs["pending_tenants"] == 0
        assert kwargs["suspended_tenants"] == 0
        # Default zero MRR
        assert kwargs["total_mrr"] == Decimal("0.00")
        assert kwargs["subscription_breakdown"] == []
        assert kwargs["recent_notifications"] == []
        # No breakdown / notification rows constructed
        mock_breakdown.assert_not_called()
        mock_recent_schema.assert_not_called()

    @patch("app.services.saas_dashboard_service.SaaSDashboardMetricsSchema")
    @patch("app.services.saas_dashboard_service.RecentNotificationSchema")
    @patch("app.services.saas_dashboard_service.MetricBreakdown")
    def test_status_without_name_falls_back_to_str(
        self, mock_breakdown, mock_recent_schema, mock_metrics_schema
    ):
        svc, db = _make_svc()
        chains = [MagicMock() for _ in range(6)]
        chains[0].scalar.return_value = 0
        for i in (1, 2, 3):
            chains[i].filter.return_value.scalar.return_value = 0
        chains[4].join.return_value.filter.return_value.scalar.return_value = None
        chains[5].join.return_value.filter.return_value.group_by.return_value.all.return_value = []
        notif_chain = MagicMock()
        # status is a plain string (no .name)
        notif_chain.order_by.return_value.limit.return_value.all.return_value = [
            SimpleNamespace(
                id=42,
                subject="s",
                body="b",
                status="UNREAD",
                is_read=False,
                date_created=None,
            )
        ]
        db.query.side_effect = chains + [notif_chain]

        svc.get_dashboard_metrics()
        # The recent-notification helper was called with status as a string
        kwargs = mock_recent_schema.call_args.kwargs
        assert kwargs["status"] == "UNREAD"
        # date_created is None → empty string
        assert kwargs["created_at"] == ""
