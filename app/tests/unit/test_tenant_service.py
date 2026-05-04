"""Unit tests for TenantService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.tenant_service import TenantService


class TestTenantServiceConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = TenantService(db)
        assert svc.db is db
