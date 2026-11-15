# app/tests/unit/test_trial_and_incentives.py
"""Tests for the 30-day full-feature trial and SaaS-admin incentives
(extend subscription / grant complimentary subscription).

Runs against an in-memory SQLite master+tenant schema and exercises
SubscriptionService.check_feature_access and TenantService's incentive methods
directly (no FastAPI layer needed)."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.enums import SubscriptionStatus
from app.models.base import MasterBase, TenantBase
from app.models.all_models import (
    SubscriptionPlan, Tenant, TenantModuleAccess, TenantSubscription,
)
from app.services.subscription_service import SubscriptionService
from app.services.tenant_service import TenantService


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    MasterBase.metadata.create_all(engine)
    TenantBase.metadata.create_all(engine)
    S = sessionmaker(bind=engine, expire_on_commit=False)
    s = S()
    try:
        yield s
    finally:
        s.close()


def _aware(dt):
    """SQLite returns naive datetimes; treat them as UTC for comparisons."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _plan(s, code="STD", **flags):
    defaults = dict(has_clinical=True, has_pharmacy=False)
    defaults.update(flags)
    p = SubscriptionPlan(name=f"Plan {code}", code=code, **defaults)
    s.add(p); s.flush()
    return p


def _tenant(s, code="t1"):
    t = Tenant(name=f"Hosp {code}", code=code,
               domain_url=f"https://{code}.example.com", db_name=f"db_{code}")
    s.add(t); s.flush()
    return t


def _sub(s, tenant, plan, status, trial_end=None):
    sub = TenantSubscription(tenant_id=tenant.id, plan_id=plan.id,
                             status=status, trial_end_date=trial_end,
                             current_period_end=trial_end)
    s.add(sub); s.commit()
    return sub


# ----------------------------------------------------------------------
# Trial = ALL features for the trial window
# ----------------------------------------------------------------------
def test_active_trial_grants_every_feature(session):
    plan = _plan(session, "BASIC", has_pharmacy=False)   # plan lacks pharmacy
    t = _tenant(session, "trialfull")
    _sub(session, t, plan, SubscriptionStatus.TRIALING,
         trial_end=datetime.now(timezone.utc) + timedelta(days=20))
    svc = SubscriptionService(session)
    # Even a feature the chosen plan does NOT include is available in trial.
    assert svc.check_feature_access(t.id, "pharmacy") is True
    assert svc.check_feature_access(t.id, "clinical") is True


def test_expired_trial_blocks_access(session):
    plan = _plan(session, "BASIC2")
    t = _tenant(session, "trialexpired")
    _sub(session, t, plan, SubscriptionStatus.TRIALING,
         trial_end=datetime.now(timezone.utc) - timedelta(days=1))
    svc = SubscriptionService(session)
    assert svc.check_feature_access(t.id, "pharmacy") is False
    assert svc.check_feature_access(t.id, "clinical") is False


def test_active_paid_subscription_gates_on_plan_flags(session):
    plan = _plan(session, "STD3", has_clinical=True, has_pharmacy=False)
    t = _tenant(session, "paid")
    _sub(session, t, plan, SubscriptionStatus.ACTIVE)
    svc = SubscriptionService(session)
    assert svc.check_feature_access(t.id, "clinical") is True
    assert svc.check_feature_access(t.id, "pharmacy") is False


def test_tenant_override_wins_even_during_trial(session):
    plan = _plan(session, "BASIC4")
    t = _tenant(session, "override")
    _sub(session, t, plan, SubscriptionStatus.TRIALING,
         trial_end=datetime.now(timezone.utc) + timedelta(days=20))
    session.add(TenantModuleAccess(tenant_id=t.id, module_code="pharmacy", is_enabled=False))
    session.commit()
    svc = SubscriptionService(session)
    assert svc.check_feature_access(t.id, "pharmacy") is False     # explicitly disabled
    assert svc.check_feature_access(t.id, "clinical") is True       # still trial-granted


# ----------------------------------------------------------------------
# _add_months helper
# ----------------------------------------------------------------------
def test_add_months_handles_month_end():
    out = TenantService._add_months(datetime(2026, 1, 31, tzinfo=timezone.utc), 1)
    assert (out.year, out.month) == (2026, 2)
    assert out.day == 28  # Feb 2026 has 28 days
    out2 = TenantService._add_months(datetime(2026, 11, 15, tzinfo=timezone.utc), 3)
    assert (out2.year, out2.month, out2.day) == (2027, 2, 15)


# ----------------------------------------------------------------------
# Extend subscription / trial
# ----------------------------------------------------------------------
def test_extend_trial_pushes_trial_end_and_logs_incentive(session):
    plan = _plan(session, "STD5")
    t = _tenant(session, "extend")
    end = datetime.now(timezone.utc) + timedelta(days=5)
    _sub(session, t, plan, SubscriptionStatus.TRIALING, trial_end=end)
    svc = TenantService(session)

    sub = svc.extend_subscription(t.id, days=10, reason="Goodwill")
    te = _aware(sub.trial_end_date)
    assert te > end
    # ~10 days later
    assert round((te - end).total_seconds() / 86400) == 10

    incentives = svc.list_incentives(t.id)
    assert len(incentives) == 1
    assert incentives[0]["incentive_type"] == "TRIAL_EXTENSION"
    assert incentives[0]["days"] == 10


def test_extend_requires_a_duration(session):
    from app.core.exceptions import BadRequestError
    plan = _plan(session, "STD6")
    t = _tenant(session, "extend0")
    _sub(session, t, plan, SubscriptionStatus.ACTIVE)
    svc = TenantService(session)
    with pytest.raises(BadRequestError):
        svc.extend_subscription(t.id, days=0, months=0)


# ----------------------------------------------------------------------
# Grant complimentary subscription
# ----------------------------------------------------------------------
def test_grant_free_subscription_sets_comp_and_logs(session):
    plan = _plan(session, "STD7")
    t = _tenant(session, "comp")
    _sub(session, t, plan, SubscriptionStatus.TRIALING,
         trial_end=datetime.now(timezone.utc) + timedelta(days=2))
    svc = TenantService(session)

    sub = svc.grant_complimentary_subscription(t.id, months=1, reason="Launch partner")
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.is_complimentary is True
    assert _aware(sub.current_period_end) > datetime.now(timezone.utc)

    incentives = svc.list_incentives(t.id)
    assert any(i["incentive_type"] == "COMPLIMENTARY_SUBSCRIPTION" for i in incentives)


def test_grant_free_can_switch_plan(session):
    basic = _plan(session, "BASIC8", has_pharmacy=False)
    pro = _plan(session, "PRO8", has_pharmacy=True)
    t = _tenant(session, "compplan")
    _sub(session, t, basic, SubscriptionStatus.ACTIVE)
    svc = TenantService(session)

    sub = svc.grant_complimentary_subscription(t.id, days=30, plan_code="PRO8")
    assert sub.plan_id == pro.id
    # Now on PRO (active, comp) -> pharmacy available
    assert SubscriptionService(session).check_feature_access(t.id, "pharmacy") is True


# ----------------------------------------------------------------------
# A free month can be granted to ANY tenant — even one with no live
# subscription (the grant creates one).
# ----------------------------------------------------------------------
def test_grant_free_creates_subscription_when_none(session):
    plan = _plan(session, "ONLY9", price=5000)  # the only active plan
    t = _tenant(session, "nosub")
    svc = TenantService(session)

    sub = svc.grant_complimentary_subscription(t.id, months=1, reason="Goodwill")
    assert sub.id is not None
    assert sub.plan_id == plan.id
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.is_complimentary is True
    assert _aware(sub.current_period_end) > datetime.now(timezone.utc)
    assert any(i["incentive_type"] == "COMPLIMENTARY_SUBSCRIPTION"
               for i in svc.list_incentives(t.id))


def test_grant_free_no_sub_uses_cheapest_active_plan(session):
    cheap = _plan(session, "CHEAP9", price=1000)
    _pricey = _plan(session, "PRICEY9", price=9000)
    t = _tenant(session, "nosub2")
    svc = TenantService(session)

    sub = svc.grant_complimentary_subscription(t.id, months=1)
    assert sub.plan_id == cheap.id
    assert sub.is_complimentary is True


def test_grant_free_no_sub_honours_explicit_plan_code(session):
    _cheap = _plan(session, "CHEAP10", price=1000)
    pro = _plan(session, "PRO10", price=9000, has_pharmacy=True)
    t = _tenant(session, "nosub3")
    svc = TenantService(session)

    sub = svc.grant_complimentary_subscription(t.id, months=1, plan_code="PRO10")
    assert sub.plan_id == pro.id
