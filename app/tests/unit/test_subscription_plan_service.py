"""Unit tests for SubscriptionPlanService.

Covers list / get / create / update flows and the uniqueness guards on
``code`` and ``name``.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.services.subscription_plan_service import SubscriptionPlanService


def _make_svc():
    db = MagicMock()
    return SubscriptionPlanService(db), db


class TestListPlans:
    def test_active_only_by_default(self):
        svc, db = _make_svc()
        chain = db.query.return_value
        chain.filter.return_value.order_by.return_value.all.return_value = ["plan_a"]
        result = svc.list_plans()
        assert result == ["plan_a"]
        chain.filter.assert_called_once()

    def test_include_inactive_skips_filter(self):
        svc, db = _make_svc()
        chain = db.query.return_value
        chain.order_by.return_value.all.return_value = ["plan_a", "plan_b"]
        result = svc.list_plans(include_inactive=True)
        assert result == ["plan_a", "plan_b"]
        # Filter not called when including inactive
        chain.filter.assert_not_called()


class TestGetPlan:
    def test_returns_plan(self):
        svc, db = _make_svc()
        plan = SimpleNamespace(id=5, name="Pro")
        db.query.return_value.filter.return_value.first.return_value = plan
        assert svc.get_plan(5) is plan

    def test_raises_not_found(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundError, match="Subscription plan not found"):
            svc.get_plan(99)


class TestCreatePlan:
    def test_rejects_duplicate_code_or_name(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=1)
        payload = MagicMock()
        payload.code = "PRO"
        payload.name = "Pro"
        with pytest.raises(BadRequestError, match="already exists"):
            svc.create_plan(payload)

    def test_creates_when_unique(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        payload = MagicMock()
        payload.code = "PRO"
        payload.name = "Pro"
        payload.model_dump.return_value = {"code": "PRO", "name": "Pro", "price": 99}
        svc.create_plan(payload)
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()


class TestUpdatePlan:
    def test_rejects_unknown_plan(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        payload = MagicMock()
        payload.model_dump.return_value = {"name": "New"}
        with pytest.raises(NotFoundError):
            svc.update_plan(1, payload)

    def test_rejects_duplicate_name(self):
        svc, db = _make_svc()
        plan = SimpleNamespace(id=1, name="Old")
        # First .filter().first() resolves the plan, second one finds a dup
        db.query.return_value.filter.return_value.first.side_effect = [
            plan,  # get_plan
            SimpleNamespace(id=2, name="Pro"),  # duplicate name
        ]
        payload = MagicMock()
        payload.model_dump.return_value = {"name": "Pro"}
        with pytest.raises(BadRequestError, match="already exists"):
            svc.update_plan(1, payload)

    def test_applies_update_when_clean(self):
        svc, db = _make_svc()
        plan = SimpleNamespace(id=1, name="Old", price=10)
        db.query.return_value.filter.return_value.first.side_effect = [plan, None]
        payload = MagicMock()
        payload.model_dump.return_value = {"name": "Pro", "price": 99}
        result = svc.update_plan(1, payload)
        assert result.name == "Pro"
        assert result.price == 99
        db.commit.assert_called_once()

    def test_update_without_name_skips_uniqueness_check(self):
        svc, db = _make_svc()
        plan = SimpleNamespace(id=1, name="Old", price=10)
        db.query.return_value.filter.return_value.first.return_value = plan
        payload = MagicMock()
        payload.model_dump.return_value = {"price": 50}
        svc.update_plan(1, payload)
        assert plan.price == 50


class TestConstruction:
    def test_holds_session(self):
        svc, db = _make_svc()
        assert svc.db is db
