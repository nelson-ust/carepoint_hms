# app/services/capitation_service.py
from __future__ import annotations

"""
Capitation management: contracts, monthly schedule runs (enrollee snapshots),
HMO enrollee-list variance, capitation receipts and the capitation-vs-
utilization (loss ratio) report.

Ledger integration (idempotent via ``JournalEntry.source_ref``):
* schedule CONFIRMED  -> Dr Capitation Receivable / Cr Capitation Income
                         (source_ref = "capitation_schedule:{id}")
* payment recorded    -> Dr Bank / Cr Capitation Receivable
                         (source_ref = "capitation_payment:{id}")
Actual posting happens in ``posting_rules_service.sweep_extended`` so it obeys
the same auto-post pipeline as every other money event.
"""

import csv
import io
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import (
    CapitationContractStatus,
    CapitationScheduleStatus,
    InsurancePolicyStatus,
    PlanCoverageType,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import Billing, BillingItem, InsuranceProvider, PatientInsurance
from app.models.finance_models import (
    CapitationContract,
    CapitationPayment,
    CapitationScheduleLine,
    HmoPlan,
)


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


def _contract_read(c: CapitationContract) -> dict:
    return {
        "id": c.id,
        "insurance_provider_id": c.insurance_provider_id,
        "provider_name": c.insurance_provider.name if c.insurance_provider else None,
        "hmo_plan_id": c.hmo_plan_id,
        "plan_name": c.plan.name if c.plan else None,
        "rate_per_enrollee": str(c.rate_per_enrollee),
        "effective_from": c.effective_from.isoformat(),
        "effective_to": c.effective_to.isoformat() if c.effective_to else None,
        "payment_day": c.payment_day,
        "status": c.status.value if hasattr(c.status, "value") else c.status,
        "notes": c.notes,
    }


def _line_read(l: CapitationScheduleLine) -> dict:
    expected, received = _d(l.expected_amount), _d(l.received_amount)
    return {
        "id": l.id, "contract_id": l.contract_id, "period_code": l.period_code,
        "enrollee_count": l.enrollee_count,
        "rate_per_enrollee": str(l.rate_per_enrollee),
        "expected_amount": str(expected), "received_amount": str(received),
        "outstanding": str(expected - received),
        "status": l.status.value if hasattr(l.status, "value") else l.status,
        "confirmed_at": l.confirmed_at.isoformat() if l.confirmed_at else None,
        "has_hmo_list": bool(l.hmo_list_snapshot),
        "variance": (l.hmo_list_snapshot or {}).get("variance_summary"),
        "notes": l.notes,
    }


class CapitationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------------- contracts ----------------

    def _get_contract(self, contract_id: int) -> CapitationContract:
        c = (self.db.query(CapitationContract)
             .filter(CapitationContract.id == contract_id,
                     CapitationContract.is_deleted.is_(False)).first())
        if c is None:
            raise NotFoundError("Capitation contract not found.")
        return c

    def list_contracts(self, *, provider_id: Optional[int] = None) -> list[dict]:
        q = (self.db.query(CapitationContract)
             .filter(CapitationContract.is_deleted.is_(False)))
        if provider_id:
            q = q.filter(CapitationContract.insurance_provider_id == provider_id)
        return [_contract_read(c) for c in q.order_by(CapitationContract.id.desc()).all()]

    def upsert_contract(self, *, contract_id: Optional[int] = None, **fields) -> dict:
        if fields.get("status"):
            try:
                fields["status"] = CapitationContractStatus(fields["status"])
            except ValueError:
                raise BadRequestError(f"Invalid status '{fields['status']}'.")
        if contract_id:
            c = self._get_contract(contract_id)
        else:
            required = {"insurance_provider_id", "rate_per_enrollee", "effective_from"}
            if not required.issubset({k for k, v in fields.items() if v is not None}):
                raise BadRequestError(
                    "insurance_provider_id, rate_per_enrollee and effective_from are required.")
            c = CapitationContract(
                insurance_provider_id=fields["insurance_provider_id"],
                rate_per_enrollee=_d(fields["rate_per_enrollee"]),
                effective_from=fields["effective_from"])
            self.db.add(c)
        allowed = {"hmo_plan_id", "rate_per_enrollee", "effective_from", "effective_to",
                   "payment_day", "status", "notes", "is_active"}
        for k, v in fields.items():
            if k in allowed and v is not None:
                setattr(c, k, v)
        self.db.flush()
        self.db.commit()
        return _contract_read(c)

    # ---------------- enrollee register ----------------

    def _enrollee_query(self, contract: CapitationContract):
        q = (self.db.query(PatientInsurance)
             .filter(PatientInsurance.is_deleted.is_(False),
                     PatientInsurance.policy_status == InsurancePolicyStatus.ACTIVE,
                     PatientInsurance.insurance_provider_id == contract.insurance_provider_id))
        if contract.hmo_plan_id:
            q = q.filter(PatientInsurance.hmo_plan_id == contract.hmo_plan_id)
        else:
            cap_plan_ids = [p.id for p in self.db.query(HmoPlan)
                            .filter(HmoPlan.insurance_provider_id == contract.insurance_provider_id,
                                    HmoPlan.is_deleted.is_(False),
                                    HmoPlan.coverage_type.in_([
                                        PlanCoverageType.CAPITATION, PlanCoverageType.HYBRID]))
                            .all()]
            if cap_plan_ids:
                q = q.filter(PatientInsurance.hmo_plan_id.in_(cap_plan_ids))
        return q

    # ---------------- monthly run ----------------

    def run_month(self, *, contract_id: int, period_code: str) -> dict:
        """(Re)generate the schedule line for YYYY-MM from the live register.
        A CONFIRMED line is immutable — rerunning is rejected."""
        c = self._get_contract(contract_id)
        try:
            datetime.strptime(period_code, "%Y-%m")
        except ValueError:
            raise BadRequestError("period_code must be YYYY-MM.")
        line = (self.db.query(CapitationScheduleLine)
                .filter(CapitationScheduleLine.contract_id == c.id,
                        CapitationScheduleLine.period_code == period_code,
                        CapitationScheduleLine.is_deleted.is_(False)).first())
        if line is not None and line.status not in (
                CapitationScheduleStatus.DRAFT, CapitationScheduleStatus.CANCELLED):
            raise BadRequestError(
                f"Schedule for {period_code} is already {line.status.value}; it cannot be regenerated.")
        enrollees = self._enrollee_query(c).all()
        count = len(enrollees)
        rate = _d(c.rate_per_enrollee)
        expected = rate * count
        snapshot = {"enrollee_ids": [e.id for e in enrollees],
                    "member_ids": [e.member_id or e.policy_number for e in enrollees]}
        if line is None:
            line = CapitationScheduleLine(contract_id=c.id, period_code=period_code)
            self.db.add(line)
        line.enrollee_count = count
        line.rate_per_enrollee = rate
        line.expected_amount = expected
        line.enrollee_snapshot = snapshot
        line.status = CapitationScheduleStatus.DRAFT
        self.db.flush()
        self.db.commit()
        return _line_read(line)

    def confirm_schedule(self, line_id: int) -> dict:
        line = self._get_line(line_id)
        if line.status != CapitationScheduleStatus.DRAFT:
            raise BadRequestError(f"Only DRAFT schedules can be confirmed (now {line.status.value}).")
        line.status = CapitationScheduleStatus.CONFIRMED
        line.confirmed_at = datetime.now(timezone.utc)
        self.db.commit()
        return _line_read(line)

    def _get_line(self, line_id: int) -> CapitationScheduleLine:
        line = (self.db.query(CapitationScheduleLine)
                .filter(CapitationScheduleLine.id == line_id,
                        CapitationScheduleLine.is_deleted.is_(False)).first())
        if line is None:
            raise NotFoundError("Capitation schedule line not found.")
        return line

    def list_schedule(self, *, contract_id: Optional[int] = None,
                      provider_id: Optional[int] = None,
                      period_code: Optional[str] = None) -> list[dict]:
        q = (self.db.query(CapitationScheduleLine)
             .join(CapitationContract,
                   CapitationContract.id == CapitationScheduleLine.contract_id)
             .filter(CapitationScheduleLine.is_deleted.is_(False)))
        if contract_id:
            q = q.filter(CapitationScheduleLine.contract_id == contract_id)
        if provider_id:
            q = q.filter(CapitationContract.insurance_provider_id == provider_id)
        if period_code:
            q = q.filter(CapitationScheduleLine.period_code == period_code)
        return [_line_read(l) for l in
                q.order_by(CapitationScheduleLine.period_code.desc()).all()]

    # ---------------- HMO enrollee list import + variance ----------------

    def import_hmo_list(self, line_id: int, *, content: bytes) -> dict:
        """Upload the HMO's own enrollee list (CSV with a ``member_id`` or
        ``policy_number`` column) and compute the variance against our
        snapshot — the classic source of capitation underpayment."""
        line = self._get_line(line_id)
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise BadRequestError("Empty CSV file.")
        headers = {h.strip().lower(): h for h in reader.fieldnames}
        key = headers.get("member_id") or headers.get("policy_number")
        if key is None:
            raise BadRequestError("CSV needs a 'member_id' or 'policy_number' column.")
        hmo_ids = {(row.get(key) or "").strip() for row in reader}
        hmo_ids.discard("")

        ours = set((line.enrollee_snapshot or {}).get("member_ids") or [])
        ours = {str(m).strip() for m in ours if m}
        only_ours = sorted(ours - hmo_ids)
        only_hmo = sorted(hmo_ids - ours)
        line.hmo_list_snapshot = {
            "hmo_count": len(hmo_ids),
            "our_count": len(ours),
            "only_in_our_register": only_ours[:500],
            "only_in_hmo_list": only_hmo[:500],
            "variance_summary": {
                "hmo_count": len(hmo_ids), "our_count": len(ours),
                "missing_from_hmo": len(only_ours), "unknown_to_us": len(only_hmo),
                "disputed_value": str(_d(line.rate_per_enrollee) * len(only_ours)),
            },
        }
        self.db.commit()
        return {"id": line.id, **line.hmo_list_snapshot}

    # ---------------- payments ----------------

    def record_payment(self, *, line_id: int, amount, paid_at: date,
                       reference: Optional[str] = None,
                       bank_account_id: Optional[int] = None,
                       remittance_advice_id: Optional[int] = None,
                       notes: Optional[str] = None) -> dict:
        line = self._get_line(line_id)
        if line.status == CapitationScheduleStatus.DRAFT:
            raise BadRequestError("Confirm the schedule before recording payments.")
        if line.status == CapitationScheduleStatus.CANCELLED:
            raise BadRequestError("Schedule is cancelled.")
        amount = _d(amount)
        if amount <= 0:
            raise BadRequestError("Amount must be positive.")
        p = CapitationPayment(schedule_line_id=line.id, amount=amount, paid_at=paid_at,
                              reference=reference, bank_account_id=bank_account_id,
                              remittance_advice_id=remittance_advice_id, notes=notes)
        self.db.add(p)
        line.received_amount = _d(line.received_amount) + amount
        if line.received_amount >= _d(line.expected_amount):
            line.status = CapitationScheduleStatus.PAID
        else:
            line.status = CapitationScheduleStatus.PARTIALLY_PAID
        self.db.flush()
        self.db.commit()
        return {"id": p.id, "schedule_line": _line_read(line)}

    def list_payments(self, *, line_id: Optional[int] = None) -> list[dict]:
        q = (self.db.query(CapitationPayment)
             .filter(CapitationPayment.is_deleted.is_(False)))
        if line_id:
            q = q.filter(CapitationPayment.schedule_line_id == line_id)
        return [{
            "id": p.id, "schedule_line_id": p.schedule_line_id,
            "amount": str(_d(p.amount)), "paid_at": p.paid_at.isoformat(),
            "reference": p.reference, "bank_account_id": p.bank_account_id,
            "notes": p.notes,
        } for p in q.order_by(CapitationPayment.id.desc()).all()]

    # ---------------- capitation vs utilization ----------------

    def utilization_report(self, *, provider_id: int,
                           period_from: str, period_to: str) -> dict:
        """Expected vs received capitation, and the fee-for-service value of
        care actually delivered to capitated enrollees — the loss ratio."""
        provider = (self.db.query(InsuranceProvider)
                    .filter(InsuranceProvider.id == provider_id).first())
        if provider is None:
            raise NotFoundError("Insurance provider not found.")
        lines = (self.db.query(CapitationScheduleLine)
                 .join(CapitationContract,
                       CapitationContract.id == CapitationScheduleLine.contract_id)
                 .filter(CapitationContract.insurance_provider_id == provider_id,
                         CapitationScheduleLine.period_code >= period_from,
                         CapitationScheduleLine.period_code <= period_to,
                         CapitationScheduleLine.is_deleted.is_(False),
                         CapitationScheduleLine.status != CapitationScheduleStatus.CANCELLED)
                 .all())
        expected = sum((_d(l.expected_amount) for l in lines), Decimal("0"))
        received = sum((_d(l.received_amount) for l in lines), Decimal("0"))

        enrollee_ids: set[int] = set()
        for l in lines:
            enrollee_ids.update((l.enrollee_snapshot or {}).get("enrollee_ids") or [])

        utilization = Decimal("0")
        if enrollee_ids:
            y1, m1 = (int(x) for x in period_from.split("-"))
            y2, m2 = (int(x) for x in period_to.split("-"))
            start = datetime(y1, m1, 1, tzinfo=timezone.utc)
            end = (datetime(y2 + 1, 1, 1, tzinfo=timezone.utc) if m2 == 12
                   else datetime(y2, m2 + 1, 1, tzinfo=timezone.utc))
            utilization = _d(
                self.db.query(func.coalesce(func.sum(BillingItem.line_total), 0))
                .join(Billing, Billing.id == BillingItem.billing_id)
                .filter(Billing.patient_insurance_id.in_(enrollee_ids),
                        Billing.billing_date >= start,
                        Billing.billing_date < end,
                        BillingItem.is_deleted.is_(False)).scalar() or 0)

        loss_ratio = (utilization / expected * 100) if expected > 0 else None
        return {
            "provider_id": provider_id, "provider_name": provider.name,
            "period_from": period_from, "period_to": period_to,
            "expected_capitation": str(expected),
            "received_capitation": str(received),
            "outstanding": str(expected - received),
            "enrollee_months": sum(l.enrollee_count for l in lines),
            "utilization_value": str(utilization),
            "loss_ratio_percent": str(loss_ratio.quantize(Decimal('0.01'))) if loss_ratio is not None else None,
            "profitable": (utilization <= expected) if expected > 0 else None,
            "periods": [_line_read(l) for l in lines],
        }
