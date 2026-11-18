# app/services/posting_rules_service.py
from __future__ import annotations

"""
Extended idempotent auto-posting sweep — the insurance/capitation, payroll-
liability, pharmacy-COGS and tax sources added by the HMO & full-accounting
build. Runs alongside ``AccountingService.auto_post_operations`` (which keeps
handling billing payments, reimbursements, salary advances and net payroll)
and uses the same ``JournalEntry.source_ref`` dedup key, so running either or
both, any number of times, never double-books.

Postings (all via ``SystemAccountMapping``):

| Event                          | Dr                        | Cr                      |
|--------------------------------|---------------------------|-------------------------|
| Claim adjudicated/approved     | HMO_AR                    | INSURANCE_REVENUE       |
| Claim payment received         | Bank (or BANK_DEFAULT)    | HMO_AR                  |
| Disallowance write-off         | DISALLOWANCE_EXPENSE*     | HMO_AR                  |
| Capitation schedule confirmed  | CAPITATION_AR             | CAPITATION_INCOME       |
| Capitation payment             | Bank (or BANK_DEFAULT)    | CAPITATION_AR           |
| Payroll statutory deductions   | SALARY_EXP (delta)        | PAYE/PENSION/NHF/OTHER  |
| Pharmacy dispense (COGS)       | PHARMACY_COGS             | INVENTORY_ASSET         |
| Invoice VAT lines              | PATIENT_REVENUE (contra)  | VAT_PAYABLE             |
| Withholding tax records        | WHT receivable treatment  | WHT_PAYABLE             |

*or DISALLOWANCE_CONTRA when the tenant configures contra-revenue treatment.
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import InsuranceClaimStatus, JournalSourceType
from app.models.all_models import (
    Dispense,
    DispenseItem,
    InsuranceClaim,
    InventoryStockItem,
    InvoiceTaxLine,
    JournalEntry,
    PayrollRun,
)
from app.models.finance_models import (
    BankAccount,
    CapitationPayment,
    CapitationScheduleLine,
    ClaimWriteOff,
)
from app.services.accounting_service import AccountingService, _d
from app.services.system_accounts_service import (
    get_accounting_config,
    resolve_system_account,
)


class PostingRulesService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounting = AccountingService(db)

    # ------------------------------------------------------------------

    def _posted(self, ref: str) -> bool:
        return (self.db.query(JournalEntry.id)
                .filter(JournalEntry.source_ref == ref,
                        JournalEntry.is_deleted.is_(False)).first() is not None)

    def _bank_ledger_id(self, bank_account_id: Optional[int]):
        if bank_account_id:
            b = (self.db.query(BankAccount)
                 .filter(BankAccount.id == bank_account_id).first())
            if b is not None:
                return b.account_id
        return resolve_system_account(self.db, "BANK_DEFAULT").id

    def _cost_center_for_sdp(self, sdp_id: Optional[int]) -> Optional[int]:
        if not sdp_id:
            return None
        try:
            from app.models.all_models import ServiceDeliveryPoint
            from app.models.finance_models import CostCenter
            sdp = (self.db.query(ServiceDeliveryPoint)
                   .filter(ServiceDeliveryPoint.id == sdp_id).first())
            if sdp is None or not getattr(sdp, "department_id", None):
                return None
            cc = (self.db.query(CostCenter)
                  .filter(CostCenter.department_id == sdp.department_id,
                          CostCenter.is_deleted.is_(False)).first())
            return cc.id if cc else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Master sweep
    # ------------------------------------------------------------------

    def sweep_extended(self, *, user_id: Optional[int] = None,
                       limit: int = 500) -> dict:
        created: list[str] = []
        skipped = 0

        hmo_ar = resolve_system_account(self.db, "HMO_AR")
        ins_rev = resolve_system_account(self.db, "INSURANCE_REVENUE")
        cap_ar = resolve_system_account(self.db, "CAPITATION_AR")
        cap_inc = resolve_system_account(self.db, "CAPITATION_INCOME")
        cfg = get_accounting_config(self.db)
        disallow = resolve_system_account(
            self.db, "DISALLOWANCE_EXPENSE" if cfg.disallowance_as_expense
            else "DISALLOWANCE_CONTRA")

        # ---- 1) Approved claims -> HMO receivable at APPROVED amount ----
        claims = (self.db.query(InsuranceClaim)
                  .filter(InsuranceClaim.is_deleted.is_(False),
                          InsuranceClaim.status.in_([
                              InsuranceClaimStatus.APPROVED,
                              InsuranceClaimStatus.PARTIALLY_APPROVED,
                              InsuranceClaimStatus.PAID]))
                  .order_by(InsuranceClaim.id.asc()).limit(limit).all())
        for c in claims:
            ref = f"insurance_claim:{c.id}"
            amount = _d(c.approved_amount)
            if amount <= 0:
                continue
            if self._posted(ref):
                skipped += 1
                continue
            when = (c.service_date or c.date_created.date())
            self.accounting.create_entry(
                entry_date=when,
                memo=f"Claim {c.claim_no} approved — "
                     f"{c.insurance_provider.name if c.insurance_provider else ''}".strip(),
                lines=[
                    {"account_id": hmo_ar.id, "debit": amount, "credit": 0,
                     "description": f"HMO receivable {c.claim_no}"},
                    {"account_id": ins_rev.id, "debit": 0, "credit": amount,
                     "description": "Insurance fee-for-service revenue"},
                ],
                source_type=JournalSourceType.INSURANCE_CLAIM, source_ref=ref,
                user_id=user_id, auto_post=True)
            created.append(ref)

        # ---- 2) Claim payments -> bank in, receivable cleared ----
        from app.models.all_models import ClaimPayment
        for p in (self.db.query(ClaimPayment)
                  .filter(ClaimPayment.is_deleted.is_(False))
                  .order_by(ClaimPayment.id.asc()).limit(limit).all()):
            ref = f"claim_payment:{p.id}"
            amount = _d(p.amount)
            if amount <= 0:
                continue
            if self._posted(ref):
                skipped += 1
                continue
            bank_id = resolve_system_account(self.db, "BANK_DEFAULT").id
            self.accounting.create_entry(
                entry_date=p.paid_at.date() if p.paid_at else date.today(),
                memo=f"Claim payment {p.payment_reference}",
                lines=[
                    {"account_id": bank_id, "debit": amount, "credit": 0,
                     "description": f"Receipt {p.payment_reference}"},
                    {"account_id": hmo_ar.id, "debit": 0, "credit": amount,
                     "description": "HMO receivable settled"},
                ],
                source_type=JournalSourceType.CLAIM_PAYMENT, source_ref=ref,
                user_id=user_id, auto_post=True)
            created.append(ref)

        # ---- 3) Disallowance write-offs ----
        for w in (self.db.query(ClaimWriteOff)
                  .filter(ClaimWriteOff.is_deleted.is_(False))
                  .order_by(ClaimWriteOff.id.asc()).limit(limit).all()):
            ref = f"claim_write_off:{w.id}"
            amount = _d(w.amount)
            if amount <= 0:
                continue
            if self._posted(ref):
                skipped += 1
                continue
            self.accounting.create_entry(
                entry_date=w.written_off_at.date(),
                memo=f"Disallowance write-off (claim #{w.claim_id})",
                lines=[
                    {"account_id": disallow.id, "debit": amount, "credit": 0,
                     "description": w.reason_code or "Disallowance"},
                    {"account_id": hmo_ar.id, "debit": 0, "credit": amount,
                     "description": "HMO receivable written off"},
                ],
                source_type=JournalSourceType.DISALLOWANCE, source_ref=ref,
                user_id=user_id, auto_post=True)
            created.append(ref)

        # ---- 4) Confirmed capitation schedules ----
        for l in (self.db.query(CapitationScheduleLine)
                  .filter(CapitationScheduleLine.is_deleted.is_(False),
                          CapitationScheduleLine.confirmed_at.isnot(None))
                  .order_by(CapitationScheduleLine.id.asc()).limit(limit).all()):
            ref = f"capitation_schedule:{l.id}"
            amount = _d(l.expected_amount)
            if amount <= 0:
                continue
            if self._posted(ref):
                skipped += 1
                continue
            self.accounting.create_entry(
                entry_date=l.confirmed_at.date(),
                memo=f"Capitation {l.period_code} ({l.enrollee_count} enrollees)",
                lines=[
                    {"account_id": cap_ar.id, "debit": amount, "credit": 0,
                     "description": f"Capitation receivable {l.period_code}"},
                    {"account_id": cap_inc.id, "debit": 0, "credit": amount,
                     "description": "Capitation income"},
                ],
                source_type=JournalSourceType.CAPITATION, source_ref=ref,
                user_id=user_id, auto_post=True)
            created.append(ref)

        # ---- 5) Capitation payments ----
        for p in (self.db.query(CapitationPayment)
                  .filter(CapitationPayment.is_deleted.is_(False))
                  .order_by(CapitationPayment.id.asc()).limit(limit).all()):
            ref = f"capitation_payment:{p.id}"
            amount = _d(p.amount)
            if amount <= 0:
                continue
            if self._posted(ref):
                skipped += 1
                continue
            self.accounting.create_entry(
                entry_date=p.paid_at,
                memo=f"Capitation receipt {p.reference or p.id}",
                lines=[
                    {"account_id": self._bank_ledger_id(p.bank_account_id),
                     "debit": amount, "credit": 0,
                     "description": f"Capitation receipt {p.reference or ''}".strip()},
                    {"account_id": cap_ar.id, "debit": 0, "credit": amount,
                     "description": "Capitation receivable settled"},
                ],
                source_type=JournalSourceType.CAPITATION_PAYMENT, source_ref=ref,
                user_id=user_id, auto_post=True)
            created.append(ref)

        # ---- 6) Payroll statutory liabilities (deduction side) ----
        # The legacy sweep posts net pay; this adds Dr Salaries (deductions
        # delta) / Cr PAYE + Pension + NHF + Other payables per run.
        salary_exp = resolve_system_account(self.db, "SALARY_EXP")
        paye = resolve_system_account(self.db, "PAYE_PAYABLE")
        pension = resolve_system_account(self.db, "PENSION_PAYABLE")
        nhf = resolve_system_account(self.db, "NHF_PAYABLE")
        other = resolve_system_account(self.db, "OTHER_DEDUCTIONS_PAYABLE")
        runs = (self.db.query(PayrollRun)
                .filter(PayrollRun.is_deleted.is_(False))
                .order_by(PayrollRun.id.asc()).limit(limit).all())
        for r in runs:
            status_val = str(getattr(getattr(r, "status", None), "value",
                                     getattr(r, "status", "")) or "").upper()
            if status_val not in {"APPROVED", "PAID", "COMPLETED", "DISBURSED"}:
                continue
            ref = f"payroll_liabilities:{r.id}"
            if self._posted(ref):
                skipped += 1
                continue
            from app.models.all_models import PayrollLine
            lines = (self.db.query(PayrollLine)
                     .filter(PayrollLine.payroll_run_id == r.id,
                             PayrollLine.is_deleted.is_(False)).all())
            t_paye = sum((_d(l.paye_amount) for l in lines), Decimal("0"))
            t_pen = sum((_d(l.pension_amount) for l in lines), Decimal("0"))
            t_nhf = sum((_d(l.nhf_amount) for l in lines), Decimal("0"))
            t_oth = sum((_d(l.health_insurance_amount) + _d(l.other_deductions)
                         for l in lines), Decimal("0"))
            total = t_paye + t_pen + t_nhf + t_oth
            if total <= 0:
                continue
            je_lines = [{"account_id": salary_exp.id, "debit": total, "credit": 0,
                         "description": f"Statutory deductions — run {r.code}"}]
            for acct, amt, label in ((paye, t_paye, "PAYE withheld"),
                                     (pension, t_pen, "Pension withheld"),
                                     (nhf, t_nhf, "NHF withheld"),
                                     (other, t_oth, "Other deductions withheld")):
                if amt > 0:
                    je_lines.append({"account_id": acct.id, "debit": 0,
                                     "credit": amt, "description": label})
            self.accounting.create_entry(
                entry_date=r.period_end or date.today(),
                memo=f"Payroll statutory liabilities — {r.code}",
                lines=je_lines,
                source_type=JournalSourceType.PAYROLL, source_ref=ref,
                user_id=user_id, auto_post=True)
            created.append(ref)

        # ---- 7) Pharmacy COGS on completed dispenses ----
        cogs = resolve_system_account(self.db, "PHARMACY_COGS")
        inventory = resolve_system_account(self.db, "INVENTORY_ASSET")
        dispenses = (self.db.query(Dispense)
                     .filter(Dispense.is_deleted.is_(False))
                     .order_by(Dispense.id.asc()).limit(limit).all())
        for d in dispenses:
            status_val = str(getattr(d.status, "value", d.status) or "").upper()
            if status_val not in {"COMPLETED", "DISPENSED", "PARTIALLY_DISPENSED"}:
                continue
            ref = f"dispense_cogs:{d.id}"
            if self._posted(ref):
                skipped += 1
                continue
            cost_total = Decimal("0")
            for item in (d.items or []):
                if item.is_deleted:
                    continue
                drug_id = (item.prescription_item.drug_id
                           if item.prescription_item is not None else None)
                if drug_id is None:
                    continue
                stock = (self.db.query(InventoryStockItem)
                         .filter(InventoryStockItem.drug_id == drug_id,
                                 InventoryStockItem.is_deleted.is_(False),
                                 InventoryStockItem.unit_cost.isnot(None))
                         .all())
                if not stock:
                    continue
                # weighted-average cost across batches
                qty = sum((_d(s.quantity_on_hand) for s in stock), Decimal("0"))
                if qty > 0:
                    avg = sum((_d(s.unit_cost) * _d(s.quantity_on_hand)
                               for s in stock), Decimal("0")) / qty
                else:
                    avg = _d(stock[0].unit_cost)
                cost_total += (avg * _d(item.quantity_dispensed)).quantize(Decimal("0.01"))
            if cost_total <= 0:
                continue
            when = d.dispensed_at.date() if d.dispensed_at else d.date_created.date()
            self.accounting.create_entry(
                entry_date=when, memo=f"Pharmacy COGS — dispense {d.dispense_no}",
                lines=[
                    {"account_id": cogs.id, "debit": cost_total, "credit": 0,
                     "description": f"COGS {d.dispense_no}"},
                    {"account_id": inventory.id, "debit": 0, "credit": cost_total,
                     "description": "Inventory issued"},
                ],
                source_type=JournalSourceType.INVENTORY, source_ref=ref,
                user_id=user_id, auto_post=True)
            created.append(ref)

        # ---- 8) Invoice VAT lines -> VAT payable ----
        vat = resolve_system_account(self.db, "VAT_PAYABLE")
        rev = resolve_system_account(self.db, "PATIENT_REVENUE")
        for t in (self.db.query(InvoiceTaxLine)
                  .filter(InvoiceTaxLine.is_deleted.is_(False))
                  .order_by(InvoiceTaxLine.id.asc()).limit(limit).all()):
            code = (t.tax_type_code_snapshot or "").upper()
            if "VAT" not in code:
                continue
            ref = f"invoice_tax_line:{t.id}"
            amount = _d(t.tax_amount)
            if amount <= 0:
                continue
            if self._posted(ref):
                skipped += 1
                continue
            self.accounting.create_entry(
                entry_date=t.date_created.date(),
                memo=f"VAT on invoice #{t.invoice_id}",
                lines=[
                    {"account_id": rev.id, "debit": amount, "credit": 0,
                     "description": "VAT portion reclassified"},
                    {"account_id": vat.id, "debit": 0, "credit": amount,
                     "description": f"VAT payable ({t.rate_percent_snapshot}%)"},
                ],
                source_type=JournalSourceType.TAX, source_ref=ref,
                user_id=user_id, auto_post=True)
            created.append(ref)

        # ---- 9) Patient cash-billing payments -> revenue (per service account) ----
        try:
            from app.core.config import settings as _settings
            _recognise = bool(getattr(_settings, "RECOGNIZE_PATIENT_REVENUE", True))
        except Exception:
            _recognise = True
        if _recognise:
            from app.models.all_models import BillingPayment as _BillingPayment, PaymentStatus as _PaymentStatus

            for p in (self.db.query(_BillingPayment)
                      .filter(_BillingPayment.is_deleted.is_(False),
                              _BillingPayment.payment_status == _PaymentStatus.SUCCESSFUL)
                      .order_by(_BillingPayment.id.asc()).limit(limit).all()):
                ref = f"billing_payment:{p.id}"
                if _d(p.amount) <= 0:
                    continue
                if self._posted(ref):
                    skipped += 1
                    continue
                try:
                    if self._recognise_billing_payment(p, user_id=user_id):
                        created.append(ref)
                except Exception:
                    # One bad receipt (e.g. a closed period) must not abort the
                    # whole sweep; it will be retried on the next run.
                    self.db.rollback()
                    skipped += 1

        # ---- 10) Ambulance trip charges (PAID) -> revenue ----
        try:
            from app.core.config import settings as _settings_amb
            _recognise_amb = bool(getattr(_settings_amb, "RECOGNISE_AMBULANCE_REVENUE", True))
        except Exception:
            _recognise_amb = True
        if _recognise_amb:
            from app.models.all_models import (
                AmbulanceTripCharge as _AmbCharge,
                AmbulanceChargeStatus as _AmbStatus,
            )
            from app.utils.charge_capture import resolve_cash_account, resolve_revenue_account

            for c in (self.db.query(_AmbCharge)
                      .filter(_AmbCharge.is_deleted.is_(False),
                              _AmbCharge.status == _AmbStatus.PAID)
                      .order_by(_AmbCharge.id.asc()).limit(limit).all()):
                ref = f"ambulance_trip_charge:{c.id}"
                amount = _d(c.amount)
                if amount <= 0:
                    continue
                if self._posted(ref):
                    skipped += 1
                    continue
                try:
                    cash_acct = (resolve_cash_account(self.db, payment_method=None)
                                 or resolve_system_account(self.db, "CASH_ON_HAND"))
                    rev_acct = (resolve_revenue_account(self.db, category="AMBULANCE")
                                or resolve_system_account(self.db, "PATIENT_REVENUE"))
                    self.accounting.create_entry(
                        entry_date=(c.charged_at.date() if c.charged_at else date.today()),
                        memo=f"Ambulance charge #{c.id}" + (f" - {c.payer_name}" if c.payer_name else ""),
                        lines=[
                            {"account_id": cash_acct.id, "debit": amount, "credit": 0,
                             "description": "Ambulance trip receipt"},
                            {"account_id": rev_acct.id, "debit": 0, "credit": amount,
                             "description": "Ambulance revenue"},
                        ],
                        source_type=JournalSourceType.BILLING_PAYMENT,
                        source_ref=ref, user_id=user_id, auto_post=True)
                    created.append(ref)
                except Exception:
                    self.db.rollback()
                    skipped += 1

        return {"created": len(created), "skipped_existing": skipped,
                "refs": created[:100]}

    def _recognise_billing_payment(self, p, *, user_id: Optional[int] = None) -> bool:
        """
        Post one patient cash-billing payment to the GL, routed per service
        account code: Dr Cash/Bank, Cr each charge line's revenue account
        (allocated across the payment by the self-pay share of each line).
        Returns True when an entry was posted.
        """
        from app.models.all_models import Account as _Account, BillingItem as _BillingItem
        from app.utils.charge_capture import resolve_cash_account, resolve_revenue_account

        CENT = Decimal("0.01")
        amount = _d(p.amount)

        cash_acct = None
        if p.account_code:
            cash_acct = (self.db.query(_Account)
                         .filter(_Account.code == p.account_code,
                                 _Account.is_deleted.is_(False)).first())
        if cash_acct is None:
            cash_acct = resolve_cash_account(self.db, payment_method=p.payment_method)
        if cash_acct is None:
            cash_acct = resolve_system_account(self.db, "CASH_ON_HAND")

        items = (self.db.query(_BillingItem)
                 .filter(_BillingItem.billing_id == p.billing_id,
                         _BillingItem.is_deleted.is_(False)).all())
        groups: dict[str, Decimal] = {}
        base = Decimal("0.00")
        for it in items:
            share = _d(it.patient_amount) if it.patient_amount is not None else _d(it.line_total)
            if share <= 0:
                continue
            code = it.account_code
            if not code:
                cat = getattr(getattr(it, "billable_service", None), "category", None)
                acct = resolve_revenue_account(self.db, category=cat)
                code = acct.code if acct is not None else None
            if not code:
                continue
            groups[code] = groups.get(code, Decimal("0.00")) + share
            base += share

        rev_lines: list[dict] = []
        if base > 0 and groups:
            allocated = Decimal("0.00")
            codes = list(groups.keys())
            for idx, code in enumerate(codes):
                acct = (self.db.query(_Account)
                        .filter(_Account.code == code,
                                _Account.is_deleted.is_(False)).first())
                if acct is None:
                    continue
                alloc = (amount - allocated) if idx == len(codes) - 1 else (amount * groups[code] / base).quantize(CENT)
                if idx != len(codes) - 1:
                    allocated += alloc
                if alloc > 0:
                    rev_lines.append({"account_id": acct.id, "debit": 0, "credit": alloc,
                                      "description": f"Revenue {code}"})

        if not rev_lines:
            rev = resolve_system_account(self.db, "PATIENT_REVENUE")
            rev_lines = [{"account_id": rev.id, "debit": 0, "credit": amount,
                          "description": "Patient services revenue"}]

        credit_sum = sum((_d(l["credit"]) for l in rev_lines), Decimal("0.00"))
        if credit_sum != amount:
            rev_lines[-1]["credit"] = _d(rev_lines[-1]["credit"]) + (amount - credit_sum)

        lines = [{"account_id": cash_acct.id, "debit": amount, "credit": 0,
                  "description": f"Receipt {p.payment_reference}"}] + rev_lines
        self.accounting.create_entry(
            entry_date=p.paid_at.date() if p.paid_at else date.today(),
            memo=f"Patient payment {p.payment_reference}",
            lines=lines,
            source_type=JournalSourceType.BILLING_PAYMENT,
            source_ref=f"billing_payment:{p.id}",
            user_id=user_id, auto_post=True)
        return True
