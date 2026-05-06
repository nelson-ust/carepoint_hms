"""Unit tests for TenantUsageService.

Covers the static helpers: get_or_create_usage, increment_api_usage,
increment_login_usage and sync_tenant_metrics (with both the
no-connection-string short-circuit and the happy aggregation path).
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.tenant_usage_service import TenantUsageService


class TestGetOrCreateUsage:
    def test_returns_existing(self):
        master = MagicMock()
        existing = SimpleNamespace(tenant_id=1)
        master.query.return_value.filter.return_value.first.return_value = existing
        result = TenantUsageService.get_or_create_usage(master, 1)
        assert result is existing
        master.add.assert_not_called()

    def test_creates_when_missing(self):
        master = MagicMock()
        master.query.return_value.filter.return_value.first.return_value = None
        result = TenantUsageService.get_or_create_usage(master, 7)
        master.add.assert_called_once()
        master.commit.assert_called_once()
        master.refresh.assert_called_once()
        assert result is not None


class TestIncrementApiUsage:
    @patch("app.services.tenant_usage_service.get_master_db_context")
    def test_executes_update_under_master_context(self, mock_ctx):
        master = MagicMock()
        mock_ctx.return_value.__enter__.return_value = master
        TenantUsageService.increment_api_usage(99)
        master.execute.assert_called_once()
        master.commit.assert_called_once()


class TestIncrementLoginUsage:
    @patch("app.services.tenant_usage_service.get_master_db_context")
    def test_executes_update_under_master_context(self, mock_ctx):
        master = MagicMock()
        mock_ctx.return_value.__enter__.return_value = master
        TenantUsageService.increment_login_usage(99)
        master.execute.assert_called_once()
        master.commit.assert_called_once()


class TestSyncTenantMetrics:
    @patch("app.services.tenant_usage_service.get_master_db_context")
    def test_raises_when_tenant_missing(self, mock_ctx):
        master = MagicMock()
        mock_ctx.return_value.__enter__.return_value = master
        master.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError, match="not found"):
            TenantUsageService.sync_tenant_metrics(123)

    @patch("app.services.tenant_usage_service.get_master_db_context")
    def test_skips_when_no_connection_string(self, mock_ctx):
        master = MagicMock()
        mock_ctx.return_value.__enter__.return_value = master
        tenant = SimpleNamespace(id=1, code="ACME", db_connection_string=None)
        master.query.return_value.filter.return_value.first.side_effect = [tenant, None]
        # No usage record yet => create one
        out = TenantUsageService.sync_tenant_metrics(1)
        assert out is not None
        # Tenant DB sessionmaker NOT used; only master.add called for new usage
        master.add.assert_called_once()

    # ``sessionmaker`` is imported *inside* sync_tenant_metrics
    # (``from sqlalchemy.orm import sessionmaker``), so we patch the source
    # location rather than the service module's namespace.
    @patch("sqlalchemy.orm.sessionmaker")
    @patch("app.services.tenant_usage_service.get_engine_for_url")
    @patch("app.services.tenant_usage_service.decrypt_string", return_value="postgresql://x")
    @patch("app.services.tenant_usage_service.get_master_db_context")
    def test_aggregates_metrics_happy_path(
        self, mock_ctx, mock_decrypt, mock_engine_for_url, mock_sessionmaker
    ):
        master = MagicMock()
        mock_ctx.return_value.__enter__.return_value = master
        tenant = SimpleNamespace(id=1, code="ACME", db_connection_string="ENC")
        # First filter().first() => tenant lookup, second => existing usage row
        usage = SimpleNamespace(
            tenant_id=1,
            user_count=0,
            transaction_count=0,
            last_sync_at=None,
        )
        master.query.return_value.filter.return_value.first.side_effect = [
            tenant,
            usage,
        ]
        # Simulate tenant_db.query(...).scalar() returning counts
        tenant_db = MagicMock()
        # Three .scalar() calls: users, invoices, payments
        tenant_db.query.return_value.scalar.side_effect = [12, 3, 4]
        SessionLocal = MagicMock(return_value=tenant_db)
        mock_sessionmaker.return_value = SessionLocal

        out = TenantUsageService.sync_tenant_metrics(1)
        assert out is usage
        assert usage.user_count == 12
        assert usage.transaction_count == 7  # 3 invoices + 4 payments
        assert usage.last_sync_at is not None
        # Tenant DB session must always be closed
        tenant_db.close.assert_called_once()
        master.commit.assert_called()
