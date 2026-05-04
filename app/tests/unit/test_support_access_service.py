"""Unit tests for SupportAccessService."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.core.enums import SupportAccessStatus
from app.core.exceptions import BadRequestError
from app.services.support_access_service import (
    MAX_GRANT_HOURS,
    SupportAccessService,
)


class TestRequestGrantValidation:
    def test_rejects_blank_reason(self):
        admin = MagicMock(id=1, is_superuser=False, platform_role=None)
        db = MagicMock()
        svc = SupportAccessService(db)
        with pytest.raises(BadRequestError):
            svc.request_grant(admin=admin, tenant_id=1, reason="", valid_hours=4)

    def test_rejects_invalid_hours(self):
        admin = MagicMock(id=1, is_superuser=False, platform_role=None)
        db = MagicMock()
        svc = SupportAccessService(db)
        with pytest.raises(BadRequestError):
            svc.request_grant(admin=admin, tenant_id=1, reason="ok valid", valid_hours=0)
        with pytest.raises(BadRequestError):
            svc.request_grant(
                admin=admin,
                tenant_id=1,
                reason="ok valid",
                valid_hours=MAX_GRANT_HOURS + 1,
            )


class TestSupportAccessConstants:
    def test_max_hours_is_one_week(self):
        assert MAX_GRANT_HOURS == 24 * 7


class TestServiceConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = SupportAccessService(db)
        assert svc.db is db


class TestStatusEnum:
    def test_lifecycle_includes_required_values(self):
        codes = {s.value for s in SupportAccessStatus}
        assert {"REQUESTED", "APPROVED", "REVOKED", "EXPIRED"} <= codes
