# app/services/billing_interval.py
"""
Helpers for monthly vs. annual subscription billing.

Centralizes the two decisions that differ by billing cycle so every flow
(change-plan, trial, checkout, manual payment, invoice issuing) stays
consistent:

- how much a period costs (``effective_price``)
- how long a period lasts (``period_end_for_interval``)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

MONTHLY = "MONTHLY"
YEARLY = "YEARLY"

# Days per period — matches the existing convention in the billing service
# (30-day month, 365-day year) so renewal arithmetic is unchanged for monthly.
_MONTH_DAYS = 30
_YEAR_DAYS = 365


def normalize_interval(value: Any, default: str = MONTHLY) -> str:
    """Coerce any interval representation to ``MONTHLY`` or ``YEARLY``."""
    raw = str(getattr(value, "value", value) or default).strip().upper()
    if raw in {"YEARLY", "ANNUAL", "ANNUALLY", "YEAR", "YR"}:
        return YEARLY
    if raw in {"MONTHLY", "MONTH", "MO"}:
        return MONTHLY
    return default if default in {MONTHLY, YEARLY} else MONTHLY


def annual_price(plan: Any) -> Decimal:
    """
    Effective yearly price for a plan: the explicit ``annual_price`` when set,
    otherwise 12 x the monthly price.
    """
    explicit = getattr(plan, "annual_price", None)
    if explicit is not None:
        try:
            return Decimal(str(explicit))
        except Exception:  # pragma: no cover - defensive
            pass
    monthly = Decimal(str(getattr(plan, "price", 0) or 0))
    return monthly * 12


def effective_price(plan: Any, interval: Any) -> Decimal:
    """Price for one billing period at the given interval."""
    if normalize_interval(interval) == YEARLY:
        return annual_price(plan)
    return Decimal(str(getattr(plan, "price", 0) or 0))


def period_end_for_interval(interval: Any, start: datetime) -> datetime:
    """End of a single billing period starting at ``start``."""
    if normalize_interval(interval) == YEARLY:
        return start + timedelta(days=_YEAR_DAYS)
    return start + timedelta(days=_MONTH_DAYS)


def annual_savings(plan: Any) -> Decimal:
    """How much a tenant saves per year by paying annually vs. 12 monthly."""
    monthly = Decimal(str(getattr(plan, "price", 0) or 0))
    saved = (monthly * 12) - annual_price(plan)
    return saved if saved > 0 else Decimal("0")
