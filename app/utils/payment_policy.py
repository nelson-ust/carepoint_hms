# app/utils/payment_policy.py
from __future__ import annotations

"""
Centralized helpers for the hospital's payment gating policy.

Policies
--------
PRE_PAID: every billable service (lab, pharmacy, procedures) is paid before
    execution. Clinical actions check for an OPEN balance and refuse to
    proceed when one exists.
POST_PAID: charges accumulate during the visit; a single invoice is settled
    at the end. No mid-flow gating.
HYBRID: pre-paid for lab, radiology and pharmacy; post-paid otherwise.

Pre-payment gating applies ONLY to self-pay patients — those with no
active HMO or corporate-retainer coverage. Insured / retainership patients
are never blocked or routed cashier-first for a service; their sponsor
settles the bill, so they proceed straight to the service point.

The functions here take the in-process settings into account but accept
explicit overrides so services can short-circuit policy checks during
testing or for VIP / waiver workflows.
"""

from typing import Iterable, Optional

from app.core.config import settings
from app.core.enums import PaymentGatePolicy

LAB_LIKE_SOURCES = {"LAB", "LAB_ORDER", "LAB_TEST", "LABORATORY"}
RADIOLOGY_LIKE_SOURCES = {"RADIOLOGY", "RAD", "RAD_ORDER", "IMAGING"}
PHARMACY_LIKE_SOURCES = {"PHARMACY", "PRESCRIPTION", "DISPENSE", "DRUG"}


def get_active_policy(override: Optional[str] = None) -> PaymentGatePolicy:
    """
    Resolve the active payment gating policy from settings or an override.
    """
    raw = (override or getattr(settings, "PAYMENT_GATE_POLICY", "HYBRID")).strip().upper()
    try:
        return PaymentGatePolicy(raw)
    except ValueError:
        return PaymentGatePolicy.HYBRID


def requires_pre_payment(
    *,
    source: str,
    policy: Optional[PaymentGatePolicy] = None,
) -> bool:
    """
    Decide whether a service originating from `source` (case-insensitive)
    must be paid before it executes.
    """
    active = policy or get_active_policy()
    normalized = source.strip().upper() if source else ""

    if active == PaymentGatePolicy.PRE_PAID:
        return True
    if active == PaymentGatePolicy.POST_PAID:
        return False
    # HYBRID — lab, radiology and pharmacy are cash-and-carry (pay first).
    if normalized in LAB_LIKE_SOURCES:
        return True
    if normalized in RADIOLOGY_LIKE_SOURCES:
        return True
    if normalized in PHARMACY_LIKE_SOURCES:
        return True
    return False


def services_requiring_pre_payment(
    sources: Iterable[str],
    *,
    policy: Optional[PaymentGatePolicy] = None,
) -> list[str]:
    """
    Return the subset of supplied source labels that require pre-payment
    under the active policy.
    """
    return [src for src in sources if requires_pre_payment(source=src, policy=policy)]


def visit_is_self_pay(db, *, visit_id: int) -> bool:
    """
    True when the visit's patient is self-pay — i.e. has **no active policy on
    file** (no HMO or corporate-retainer enrolment with ``policy_status ==
    ACTIVE``). This is the single gate for pre-payment: a patient with an active
    policy is never pay-before-service.

    Coverage is checked strictly against the patient's *active* enrolment via
    :meth:`CoverageEngine.active_insurance_for_patient` — the declared billing
    class is **not** trusted, so a patient marked HMO/retainership whose policy
    has lapsed (status != ACTIVE) or who has no enrolment is treated as self-pay
    and gated. Both HMO and retainership coverage are active ``PatientInsurance``
    records, so this one check covers both. Unknown/unresolvable cases default
    to self-pay (gate on), preserving the cash-and-carry safety stance.
    """
    try:
        from app.models.all_models import Visit
        from app.services.coverage_engine import CoverageEngine

        visit = (
            db.query(Visit)
            .filter(Visit.id == visit_id, Visit.is_deleted.is_(False))
            .first()
        )
        if visit is None:
            return True
        active = CoverageEngine(db).active_insurance_for_patient(visit.patient_id)
        return active is None
    except Exception:
        # Never let a coverage lookup failure crash a clinical action; default
        # to the safe (gating) stance.
        return True


def visit_requires_pre_payment(
    db,
    *,
    visit_id: int,
    source: str,
    policy: Optional[PaymentGatePolicy] = None,
) -> bool:
    """
    Decide whether a ``source`` service on a specific visit must be paid before
    it executes. Combines the hospital's source policy with the payer check:
    pre-payment is required only when the source is pre-paid under the active
    policy AND the patient is self-pay (no active HMO / retainership).
    """
    if not requires_pre_payment(source=source, policy=policy):
        return False
    return visit_is_self_pay(db, visit_id=visit_id)
