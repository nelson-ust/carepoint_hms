# app/services/coverage_engine.py
from __future__ import annotations

"""
CoverageEngine — the heart of the HMO module.

Given a patient's insurance enrollment and a chargeable item, it decides:

* the price to charge (per-plan negotiated tariff first, catalog price after),
* how much the HMO covers vs how much the patient pays (co-pay),
* whether the item needs a pre-authorization,
* whether the item is excluded (100% patient-payable).

Benefit-rule resolution order (first match wins):
    1. Exact ``HmoPlanBenefit`` for the billable service (or drug),
    2. ``HmoPlanBenefit`` for the item's category,
    3. Plan defaults (``default_coverage_percent`` / co-pays).

Limits (`limit_amount` per visit / annum / lifetime) are enforced by summing
what the plan has already covered in the period; anything above the remaining
headroom shifts to the patient's side. Excluded items and enrollments that are
not ACTIVE cover nothing.

All maths is Decimal, rounded half-up to 2 dp at the boundary.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import BenefitLimitPeriod, InsurancePolicyStatus, PlanCoverageType
from app.models.all_models import (
    Billing,
    BillingItem,
    BillableService,
    PatientInsurance,
)
from app.models.finance_models import HmoPlan, HmoPlanBenefit, HmoTariff

TWO_DP = Decimal("0.01")


def _q(v) -> Decimal:
    return (Decimal(str(v or 0))).quantize(TWO_DP, rounding=ROUND_HALF_UP)


@dataclass
class CoverageDecision:
    """Outcome of a coverage evaluation for one chargeable item."""

    unit_price: Decimal                 # price actually charged (tariff-aware)
    line_total: Decimal                 # unit_price * quantity
    covered_amount: Decimal             # HMO portion
    patient_amount: Decimal             # patient co-pay portion
    is_covered: bool
    requires_preauth: bool
    coverage_source: str                # which rule matched, for audit
    plan_id: Optional[int] = None
    notes: list[str] = field(default_factory=list)


class CoverageEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------------- enrollment lookup ----------------

    def active_insurance_for_patient(self, patient_id: int) -> Optional[PatientInsurance]:
        """The patient's primary ACTIVE enrollment (falls back to any active)."""
        q = (self.db.query(PatientInsurance)
             .filter(PatientInsurance.patient_id == patient_id,
                     PatientInsurance.is_deleted.is_(False),
                     PatientInsurance.policy_status == InsurancePolicyStatus.ACTIVE))
        today = date.today()
        candidates = [pi for pi in q.all()
                      if (pi.valid_to or pi.coverage_end_date) is None
                      or (pi.valid_to or pi.coverage_end_date) >= today]
        if not candidates:
            return None
        primaries = [pi for pi in candidates if pi.is_primary]
        return (primaries or candidates)[0]

    def plan_for(self, enrollment: PatientInsurance) -> Optional[HmoPlan]:
        if not enrollment or not enrollment.hmo_plan_id:
            return None
        return (self.db.query(HmoPlan)
                .filter(HmoPlan.id == enrollment.hmo_plan_id,
                        HmoPlan.is_deleted.is_(False),
                        HmoPlan.is_active.is_(True)).first())

    # ---------------- pricing ----------------

    def tariff_price(self, plan_id: int, *, billable_service_id: Optional[int] = None,
                     drug_id: Optional[int] = None, service_code: Optional[str] = None,
                     on: Optional[date] = None) -> Optional[Decimal]:
        on = on or date.today()
        q = (self.db.query(HmoTariff)
             .filter(HmoTariff.hmo_plan_id == plan_id,
                     HmoTariff.is_deleted.is_(False)))
        if billable_service_id is not None:
            q = q.filter(HmoTariff.billable_service_id == billable_service_id)
        elif drug_id is not None:
            q = q.filter(HmoTariff.drug_id == drug_id)
        elif service_code:
            q = q.filter(HmoTariff.service_code == service_code)
        else:
            return None
        for t in q.order_by(HmoTariff.id.desc()).all():
            if t.effective_from and t.effective_from > on:
                continue
            if t.effective_to and t.effective_to < on:
                continue
            return _q(t.agreed_price)
        return None

    # ---------------- benefit resolution ----------------

    def _benefit_for(self, plan: HmoPlan, *, billable_service_id: Optional[int],
                     drug_id: Optional[int], category: Optional[str]) -> Optional[HmoPlanBenefit]:
        benefits = (self.db.query(HmoPlanBenefit)
                    .filter(HmoPlanBenefit.hmo_plan_id == plan.id,
                            HmoPlanBenefit.is_deleted.is_(False),
                            HmoPlanBenefit.is_active.is_(True)).all())
        if billable_service_id is not None:
            for b in benefits:
                if b.billable_service_id == billable_service_id:
                    return b
        if drug_id is not None:
            for b in benefits:
                if b.drug_id == drug_id:
                    return b
        if category:
            cat = category.strip().upper()
            for b in benefits:
                if b.billable_service_id is None and b.drug_id is None \
                        and (b.category or "").strip().upper() == cat:
                    return b
        return None

    # ---------------- utilization for limits ----------------

    def _covered_in_period(self, enrollment: PatientInsurance, *,
                           limit_period: BenefitLimitPeriod,
                           visit_billing_id: Optional[int]) -> Decimal:
        """Sum of ``covered_amount`` the plan has already granted this
        enrollee within the limit period."""
        q = (self.db.query(func.coalesce(func.sum(BillingItem.covered_amount), 0))
             .join(Billing, Billing.id == BillingItem.billing_id)
             .filter(Billing.patient_insurance_id == enrollment.id,
                     BillingItem.is_deleted.is_(False)))
        if limit_period == BenefitLimitPeriod.PER_VISIT:
            if visit_billing_id is None:
                return Decimal("0")
            q = q.filter(BillingItem.billing_id == visit_billing_id)
        elif limit_period == BenefitLimitPeriod.PER_ANNUM:
            year_start = date(date.today().year, 1, 1)
            q = q.filter(Billing.billing_date >= datetime(
                year_start.year, 1, 1, tzinfo=timezone.utc))
        # LIFETIME: no extra filter
        return _q(q.scalar() or 0)

    # ---------------- the decision ----------------

    def evaluate(self, *, enrollment: Optional[PatientInsurance],
                 unit_price: Decimal, quantity: Decimal = Decimal("1"),
                 billable_service_id: Optional[int] = None,
                 drug_id: Optional[int] = None,
                 service_code: Optional[str] = None,
                 category: Optional[str] = None,
                 visit_billing_id: Optional[int] = None) -> CoverageDecision:
        quantity = Decimal(str(quantity or 1))
        base_price = _q(unit_price)

        # Uninsured / inactive -> full self-pay at the catalog price.
        plan = self.plan_for(enrollment) if enrollment else None
        if plan is None:
            total = _q(base_price * quantity)
            return CoverageDecision(
                unit_price=base_price, line_total=total,
                covered_amount=Decimal("0.00"), patient_amount=total,
                is_covered=False, requires_preauth=False,
                coverage_source="SELF_PAY")

        # Category default: infer from the billable service catalog if absent.
        if category is None and billable_service_id is not None:
            svc = (self.db.query(BillableService)
                   .filter(BillableService.id == billable_service_id).first())
            category = svc.category if svc is not None else None
        if category is None and drug_id is not None:
            category = "PHARMACY"

        # 1) Price: negotiated tariff first.
        tariff = self.tariff_price(plan.id, billable_service_id=billable_service_id,
                                   drug_id=drug_id, service_code=service_code)
        price = tariff if tariff is not None else base_price
        total = _q(price * quantity)

        benefit = self._benefit_for(plan, billable_service_id=billable_service_id,
                                    drug_id=drug_id, category=category)
        source = (f"benefit:{benefit.id}" if benefit is not None else f"plan_default:{plan.id}")
        if tariff is not None:
            source += "|tariff"

        # 2) Exclusions -> 100% patient.
        if benefit is not None and benefit.is_excluded:
            return CoverageDecision(
                unit_price=price, line_total=total,
                covered_amount=Decimal("0.00"), patient_amount=total,
                is_covered=False, requires_preauth=False,
                coverage_source=source + "|excluded", plan_id=plan.id)

        # 3) Coverage % and co-pays.
        coverage_percent = _q(benefit.coverage_percent) if (benefit is not None and benefit.coverage_percent is not None) \
            else _q(plan.default_coverage_percent)
        copay_flat = _q(benefit.copay_flat) if (benefit is not None and benefit.copay_flat is not None) \
            else _q(plan.default_copay_flat)
        copay_percent = _q(plan.default_copay_percent)

        covered = _q(total * coverage_percent / Decimal("100"))
        # Flat co-pay comes out of the covered side first (standard NHIA/HMO
        # treatment: the enrollee pays the flat amount at the point of care).
        if copay_flat > 0:
            covered = max(Decimal("0.00"), _q(covered - copay_flat))
        if copay_percent > 0:
            covered = max(Decimal("0.00"), _q(covered - total * copay_percent / Decimal("100")))

        notes: list[str] = []

        # 4) Benefit-level limit headroom.
        if benefit is not None and benefit.limit_amount is not None and benefit.limit_period is not None:
            used = self._covered_in_period(enrollment, limit_period=benefit.limit_period,
                                           visit_billing_id=visit_billing_id)
            headroom = max(Decimal("0.00"), _q(benefit.limit_amount) - used)
            if covered > headroom:
                notes.append(f"benefit limit reached (used {used}, cap {benefit.limit_amount})")
                covered = headroom

        # 5) Plan-level limits.
        if plan.per_visit_limit is not None:
            used = self._covered_in_period(enrollment, limit_period=BenefitLimitPeriod.PER_VISIT,
                                           visit_billing_id=visit_billing_id)
            headroom = max(Decimal("0.00"), _q(plan.per_visit_limit) - used)
            if covered > headroom:
                notes.append("per-visit plan limit reached")
                covered = headroom
        if plan.annual_limit is not None:
            used = self._covered_in_period(enrollment, limit_period=BenefitLimitPeriod.PER_ANNUM,
                                           visit_billing_id=visit_billing_id)
            headroom = max(Decimal("0.00"), _q(plan.annual_limit) - used)
            if covered > headroom:
                notes.append("annual plan limit reached")
                covered = headroom

        covered = min(covered, total)
        patient = _q(total - covered)
        requires_preauth = bool(benefit.requires_preauth) if benefit is not None else False

        return CoverageDecision(
            unit_price=price, line_total=total,
            covered_amount=covered, patient_amount=patient,
            is_covered=covered > 0, requires_preauth=requires_preauth,
            coverage_source=source, plan_id=plan.id, notes=notes)

    # ---------------- pre-auth check used at ordering points ----------------

    def has_valid_preauth(self, enrollment: PatientInsurance, *,
                          service_name: Optional[str] = None) -> bool:
        from app.core.enums import AuthorizationStatus
        from app.models.all_models import ClaimAuthorization
        now = datetime.now(timezone.utc)
        q = (self.db.query(ClaimAuthorization)
             .filter(ClaimAuthorization.patient_insurance_id == enrollment.id,
                     ClaimAuthorization.is_deleted.is_(False),
                     ClaimAuthorization.status.in_([
                         AuthorizationStatus.APPROVED,
                         AuthorizationStatus.PARTIALLY_APPROVED])))
        for a in q.all():
            if a.valid_until is not None and a.valid_until < now:
                continue
            if service_name and a.requested_service and \
                    service_name.strip().lower() not in a.requested_service.strip().lower() and \
                    a.requested_service.strip().lower() not in service_name.strip().lower():
                continue
            return True
        return False
