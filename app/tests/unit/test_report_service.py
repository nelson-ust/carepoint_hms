"""Unit tests for ReportService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.report_service import ReportService


class TestReportServiceConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = ReportService(db)
        assert svc.db is db


class TestGetTenantOperationalSummary:
    def test_returns_summary(self):
        """ReportService queries db directly, not via a repository."""
        db = MagicMock()
        svc = ReportService(db)
        # get_tenant_operational_summary calls db.query(...).count() multiple times.
        # With MagicMock all queries return MagicMock objects, so we just verify
        # the method runs without error and returns something.
        result = svc.get_tenant_operational_summary()
        assert result is not None
