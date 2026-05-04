"""Unit tests for SubscriptionService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.subscription_service import SubscriptionService


class TestSubscriptionConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = SubscriptionService(db)
        assert svc.db is db


class TestRequireFeature:
    def test_raises_forbidden_when_feature_missing(self):
        from app.core.exceptions import ForbiddenError
        db = MagicMock()
        svc = SubscriptionService(db)
        # Make get_active_plan return None (no subscription)
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ForbiddenError, match="not included"):
            svc.require_feature(1, "some_feature")
