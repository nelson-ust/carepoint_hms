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
HYBRID: pre-paid for lab and pharmacy; post-paid for everything else.

The functions here take the in-process settings into account but accept
explicit overrides so services can short-circuit policy checks during
testing or for VIP / waiver workflows.
"""

from typing import Iterable, Optional

from app.core.config import settings
from app.core.enums import PaymentGatePolicy

LAB_LIKE_SOURCES = {"LAB", "LAB_ORDER", "LAB_TEST", "LABORATORY"}
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
    # HYBRID
    if normalized in LAB_LIKE_SOURCES:
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
