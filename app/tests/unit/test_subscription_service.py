"""Unit tests for SubscriptionService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.subscription_service import SubscriptionService


class TestSubscriptionService:
    def test_holds_session(self):
        db = MagicMock()
        svc = SubscriptionService(db)
        assert svc.db is db

    def test_get_active_plan_recognizes_trialing(self):
        from app.core.enums import SubscriptionStatus
        from app.models.all_models import TenantSubscription, SubscriptionPlan
        
        db = MagicMock()
        svc = SubscriptionService(db)
        
        mock_plan = SubscriptionPlan(name="Trial Plan", code="TRIAL")
        mock_sub = TenantSubscription(status=SubscriptionStatus.TRIALING, is_active=True)
        mock_sub.plan = mock_plan
        
        db.query.return_value.filter.return_value.first.return_value = mock_sub
        
        plan = svc.get_active_plan(1)
        assert plan is mock_plan

    def test_check_feature_access_honors_override(self):
        from app.models.all_models import TenantSubscription, SubscriptionPlan, TenantModuleAccess
        from app.core.enums import SubscriptionStatus
        
        db = MagicMock()
        svc = SubscriptionService(db)
        
        # 1. Setup plan that HAS pharmacy
        mock_plan = SubscriptionPlan(name="Pro", code="PRO", has_pharmacy=True)
        mock_sub = TenantSubscription(status=SubscriptionStatus.ACTIVE, is_active=True)
        mock_sub.plan = mock_plan
        
        # Setup query chain for get_active_plan
        db.query.return_value.filter.return_value.first.side_effect = [
            mock_sub,  # First call for get_active_plan
            TenantModuleAccess(module_code="pharmacy", is_enabled=False) # Second call for override check
        ]
        
        # Should return False because of override
        assert svc.check_feature_access(1, "pharmacy") is False

    def test_require_feature_raises_forbidden_with_custom_message(self):
        from app.core.exceptions import ForbiddenError
        db = MagicMock()
        svc = SubscriptionService(db)
        
        # Mock check_feature_access to return False
        svc.check_feature_access = MagicMock(return_value=False)
        
        with pytest.raises(ForbiddenError, match="not enabled for your tenant"):
            svc.require_feature(1, "restricted_module")

