# app/services/accounting_ext_service.py
from __future__ import annotations

"""
Accounting-module completeness on top of ``accounting_service``:

* Cost centers (departmental accounting) + one-click generation from
  departments; departmental P&L.
* Chart-of-accounts hierarchy tree + opening balances.
* Cash flow statement (indirect, from ``Account.cash_flow_category``,
  plus a direct cash-movement summary).
* General ledger report (+ XLSX export) and AR segmentation.
* Pre-close checklist and posting-rules status.
"""

import io
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import (
    AccountType,
    AccountingPeriodStatus,
    InsuranceClaimStatus,
    JournalEntryStatus,
    JournalSourceType,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    Account,
    AccountingPeriod,
    Department,
    InsuranceClaim,
    Invoice,
    JournalEntry,
    JournalEntryLine,
)
from app.models.finance_models import (
    BankAccount,
    BankStatementLine,
    CapitationScheduleLine,
    CostCenter,
    PettyCashFloat,
)
from app.services.accounting_service import AccountingService, _d
from app.services.system_accounts_service import (
    audit,
    get_accounting_config,
    resolve_system_account,
)


class AccountingExtService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounting = AccountingService(db)

    # ------------------------------------------------------------------
    # Cost centers
    # ------------------------------------------------------------------

    def list_cost_centers(self) -> list[dict]:
        rows = (self.db.query(CostCenter)
                .filter(CostCenter.is_deleted.is_(False))
                .order_by(CostCenter.code).all())
        return [{"id": c.id, "code": c.code, "name": c.name,
                 "department_id": c.department_id, "facility_id": c.facility_id,
                 "is_active": c.is_active, "description": c.description}
                for c in rows]

    def upsert_cost_center(self, *, cost_center_id: Optional[int] = None,
                           **fields) -> dict:
        if cost_center_id:
            c = (self.db.query(CostCenter)
                 .filter(CostCenter.id == cost_center_id,
                         CostCenter.is_deleted.is_(False)).first())
            if c is None:
                raise NotFoundError("Cost center not found.")
        else:
            if not fields.get("code") or not fields.get("name"):
                raise BadRequestError("code and name are required.")
            c = CostCenter(code=fields["code"].upper(), name=fields["name"])
            self.db.add(c)
        for k in ("code", "name", "department_id", "facility_id",
                  "description", "is_active"):
            if k in fields and fields[k] is not None:
                setattr(c, k, fields[k].upper() if k == "code" else fields[k])
        self.db.flush()
        self.db.commit()
        return {"id": c.id, "code": c.code, "name": c.name}

    def generate_from_departments(self) -> dict:
        """One-click: a cost center per department that lacks one."""
        created = 0
        existing_dept_ids = {c.department_id for c in
                             self.db.query(CostCenter)
                             .filter(CostCenter.is_deleted.is_(False)).all()
                             if c.department_id}
        for d in (self.db.query(Department)
                  .filter(Department.is_deleted.is_(False)).all()):
            if d.id in existing_dept_ids:
                continue
            code = f"CC-{(d.code or d.name or str(d.id))[:12].upper().replace(' ', '_')}"
            n = 1
            base = code
            while (self.db.query(CostCenter)
                   .filter(CostCenter.code == code).first() is not None):
                n += 1
                code = f"{base}{n}"
            self.db.add(CostCenter(code=code, name=d.name, department_id=d.id))
            created += 1
        self.db.commit()
        return {"created": created}

    def cost_center_for_department(self, department_id: Optional[int]) -> Optional[int]:
        if not department_id:
            return None
        c = (self.db.query(CostCenter)
             .filter(CostCenter.department_id == department_id,
                     CostCenter.is_deleted.is_(False)).first())
        return c.id if c else None

    # ------------------------------------------------------------------
    # Chart-of-accounts tree + opening balances
    # ------------------------------------------------------------------

    def account_tree(self) -> list[dict]:
        accounts = (self.db.query(Account)
                    .filter(Account.is_deleted.is_(False))
                    .order_by(Account.code).all())
        by_id = {a.id: {"id": a.id, "code": a.code, "name": a.name,
                        "account_type": a.account_type.value
                            if hasattr(a.account_type, "value") else a.account_type,
                        "parent_account_id": a.parent_account_id,
                        "is_postable": a.is_postable, "is_system": a.is_system,
                        "cash_flow_category": a.cash_flow_category,
                        "is_active": a.is_active, "children": []}
                 for a in accounts}
        roots = []
        for node in by_id.values():
            pid = node["parent_account_id"]
            if pid and pid in by_id:
                by_id[pid]["children"].append(node)
            else:
                roots.append(node)
        return roots

    def update_account(self, account_id: int, **fields) -> dict:
        a = (self.db.query(Account)
             .filter(Account.id == account_id, Account.is_deleted.is_(False)).first())
        if a is None:
            raise NotFoundError("Account not found.")
        if fields.get("parent_account_id") == a.id:
            raise BadRequestError("An account cannot be its own parent.")
        for k in ("name", "description", "parent_account_id", "is_postable",
                  "cash_flow_category", "is_active"):
            if k in fields and fields[k] is not None:
                setattr(a, k, fields[k])
        self.db.commit()
        return {"id": a.id, "code": a.code, "name": a.name,
                "parent_account_id": a.parent_account_id,
                "is_postable": a.is_postable,
                "cash_flow_category": a.cash_flow_category}

    def set_opening_balances(self, *, as_of: date, balances: list[dict],
                             user_id: Optional[int] = None) -> dict:
        """balances: [{account_id, debit?, credit?}] — one balanced OPENING
        entry against Opening Balance Equity. Sets the go-live date."""
        if not balances:
            raise BadRequestError("Provide at least one opening balance line.")
        equity = resolve_system_account(self.db, "OPENING_BALANCE_EQUITY")
        lines = []
        net = Decimal("0")
        for b in balances:
            debit, credit = _d(b.get("debit")), _d(b.get("credit"))
            if debit < 0 or credit < 0 or (debit > 0 and credit > 0):
                raise BadRequestError("Each line must be a non-negative debit OR credit.")
            if debit == 0 and credit == 0:
                continue
            lines.append({"account_id": b["account_id"], "debit": debit,
                          "credit": credit, "description": "Opening balance"})
            net += debit - credit
        if not lines:
            raise BadRequestError("All lines were zero.")
        if net > 0:
            lines.append({"account_id": equity.id, "debit": 0, "credit": net,
                          "description": "Opening balance equity"})
        elif net < 0:
            lines.append({"account_id": equity.id, "debit": -net, "credit": 0,
                          "description": "Opening balance equity"})
        entry = self.accounting.create_entry(
            entry_date=as_of, memo="Opening balances (go-live)",
            lines=lines, source_type=JournalSourceType.OPENING_BALANCE,
            user_id=user_id, auto_post=True)
        cfg = get_accounting_config(self.db)
        cfg.opening_balance_date = as_of
        audit(self.db, action="OPENING_BALANCES_SET", entity_type="journal_entry",
              entity_id=entry.get("id"), user_id=user_id,
              summary=f"Opening balances as of {as_of}")
        self.db.commit()
        return entry

    # ------------------------------------------------------------------
    # Cash flow statement
    # ------------------------------------------------------------------

    def cash_flow_statement(self, *, date_from: date, date_to: date) -> dict:
        """Movement-based cash flow: every POSTED line in the period is
        classified by its account — cash/bank accounts form the cash total,
        every other account contributes to its ``cash_flow_category``
        section (sign-flipped, since a credit to revenue means cash in)."""
        cash_ids = {b.account_id for b in
                    self.db.query(BankAccount).filter(BankAccount.is_deleted.is_(False)).all()}
        cash_ids |= {f.account_id for f in
                     self.db.query(PettyCashFloat).filter(PettyCashFloat.is_deleted.is_(False)).all()}
        for key in ("CASH_ON_HAND", "UNDEPOSITED_FUNDS"):
            cash_ids.add(resolve_system_account(self.db, key).id)

        q = (self.db.query(JournalEntryLine, JournalEntry, Account)
             .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
             .join(Account, Account.id == JournalEntryLine.account_id)
             .filter(JournalEntry.status == JournalEntryStatus.POSTED,
                     JournalEntry.is_deleted.is_(False),
                     JournalEntry.entry_date >= date_from,
                     JournalEntry.entry_date <= date_to))
        sections = {"OPERATING": {}, "INVESTING": {}, "FINANCING": {}, "NONE": {}}
        cash_delta = Decimal("0")
        for line, entry, acct in q.all():
            amt = _d(line.debit) - _d(line.credit)
            if acct.id in cash_ids:
                cash_delta += amt
                continue
            cat = (acct.cash_flow_category or "").upper()
            if cat not in sections or cat == "NONE":
                # classify by account type when uncategorised
                t = acct.account_type.value if hasattr(acct.account_type, "value") else str(acct.account_type)
                cat = ("INVESTING" if t == "ASSET" and str(acct.code).startswith("15")
                       else "FINANCING" if t == "EQUITY"
                       else "OPERATING")
            slot = sections[cat].setdefault(acct.id, {
                "code": acct.code, "name": acct.name, "amount": Decimal("0")})
            # A debit to a non-cash account uses cash -> negative cash effect.
            slot["amount"] -= amt
        opening_cash = Decimal("0")
        q0 = (self.db.query(
                func.coalesce(func.sum(JournalEntryLine.debit - JournalEntryLine.credit), 0))
              .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
              .filter(JournalEntry.status == JournalEntryStatus.POSTED,
                      JournalEntry.is_deleted.is_(False),
                      JournalEntry.entry_date < date_from,
                      JournalEntryLine.account_id.in_(cash_ids)))
        if cash_ids:
            opening_cash = _d(q0.scalar() or 0)

        def _rows(cat):
            rows = [r for r in sections[cat].values() if r["amount"] != 0]
            rows.sort(key=lambda r: r["code"])
            return ([{"code": r["code"], "name": r["name"], "amount": str(r["amount"])}
                     for r in rows],
                    sum((r["amount"] for r in rows), Decimal("0")))

        op_rows, op_total = _rows("OPERATING")
        inv_rows, inv_total = _rows("INVESTING")
        fin_rows, fin_total = _rows("FINANCING")
        return {
            "date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
            "operating": {"rows": op_rows, "total": str(op_total)},
            "investing": {"rows": inv_rows, "total": str(inv_total)},
            "financing": {"rows": fin_rows, "total": str(fin_total)},
            "net_cash_flow": str(op_total + inv_total + fin_total),
            "cash_movement_check": str(cash_delta),
            "opening_cash": str(opening_cash),
            "closing_cash": str(opening_cash + cash_delta),
        }

    # ------------------------------------------------------------------
    # General ledger report
    # ------------------------------------------------------------------

    def general_ledger(self, *, date_from: date, date_to: date,
                       account_id: Optional[int] = None,
                       cost_center_id: Optional[int] = None) -> dict:
        q = (self.db.query(JournalEntryLine, JournalEntry)
             .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
             .filter(JournalEntry.status == JournalEntryStatus.POSTED,
                     JournalEntry.is_deleted.is_(False),
                     JournalEntry.entry_date >= date_from,
                     JournalEntry.entry_date <= date_to))
        if account_id:
            q = q.filter(JournalEntryLine.account_id == account_id)
        if cost_center_id:
            q = q.filter(JournalEntryLine.cost_center_id == cost_center_id)
        rows = []
        td = tc = Decimal("0")
        for line, entry in q.order_by(JournalEntry.entry_date,
                                      JournalEntry.id).all():
            td += _d(line.debit)
            tc += _d(line.credit)
            rows.append({
                "entry_no": entry.entry_no,
                "date": entry.entry_date.isoformat(),
                "account_code": line.account_code, "account_name": line.account_name,
                "description": line.description or entry.memo,
                "source": entry.source_type.value if hasattr(entry.source_type, "value") else entry.source_type,
                "cost_center_id": line.cost_center_id,
                "debit": str(_d(line.debit)), "credit": str(_d(line.credit)),
            })
        return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
                "rows": rows, "total_debit": str(td), "total_credit": str(tc)}

    def general_ledger_xlsx(self, *, date_from: date, date_to: date,
                            account_id: Optional[int] = None) -> tuple[str, bytes]:
        from openpyxl import Workbook
        data = self.general_ledger(date_from=date_from, date_to=date_to,
                                   account_id=account_id)
        wb = Workbook()
        ws = wb.active
        ws.title = "General Ledger"
        ws.append(["Entry", "Date", "Account", "Name", "Description",
                   "Source", "Debit", "Credit"])
        for r in data["rows"]:
            ws.append([r["entry_no"], r["date"], r["account_code"], r["account_name"],
                       r["description"], r["source"],
                       float(r["debit"]), float(r["credit"])])
        ws.append(["", "", "", "", "", "TOTAL",
                   float(data["total_debit"]), float(data["total_credit"])])
        buf = io.BytesIO()
        wb.save(buf)
        return f"general_ledger_{date_from}_{date_to}.xlsx", buf.getvalue()

    # ------------------------------------------------------------------
    # Departmental P&L
    # ------------------------------------------------------------------

    def departmental_pnl(self, *, date_from: date, date_to: date) -> dict:
        centers = {c.id: c for c in
                   self.db.query(CostCenter).filter(CostCenter.is_deleted.is_(False)).all()}
        q = (self.db.query(JournalEntryLine, JournalEntry, Account)
             .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
             .join(Account, Account.id == JournalEntryLine.account_id)
             .filter(JournalEntry.status == JournalEntryStatus.POSTED,
                     JournalEntry.is_deleted.is_(False),
                     JournalEntry.entry_date >= date_from,
                     JournalEntry.entry_date <= date_to,
                     Account.account_type.in_([AccountType.REVENUE, AccountType.EXPENSE])))
        cols: dict[Optional[int], dict] = {}
        for line, entry, acct in q.all():
            cc = line.cost_center_id if line.cost_center_id in centers else None
            slot = cols.setdefault(cc, {"revenue": Decimal("0"), "expense": Decimal("0")})
            t = acct.account_type
            if t == AccountType.REVENUE:
                slot["revenue"] += _d(line.credit) - _d(line.debit)
            else:
                slot["expense"] += _d(line.debit) - _d(line.credit)
        out = []
        for cc_id, vals in cols.items():
            c = centers.get(cc_id)
            out.append({
                "cost_center_id": cc_id,
                "cost_center": f"{c.code} · {c.name}" if c else "Unallocated",
                "revenue": str(vals["revenue"]), "expense": str(vals["expense"]),
                "surplus": str(vals["revenue"] - vals["expense"]),
            })
        out.sort(key=lambda r: (r["cost_center_id"] is None, r["cost_center"]))
        return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
                "columns": out,
                "total_revenue": str(sum((Decimal(r["revenue"]) for r in out), Decimal("0"))),
                "total_expense": str(sum((Decimal(r["expense"]) for r in out), Decimal("0")))}

    # ------------------------------------------------------------------
    # AR segmentation (patient vs HMO FFS vs capitation)
    # ------------------------------------------------------------------

    def ar_segments(self) -> dict:
        patient = _d(self.db.query(func.coalesce(func.sum(Invoice.balance_due), 0))
                     .filter(Invoice.is_deleted.is_(False),
                             Invoice.balance_due > 0).scalar() or 0)
        hmo = _d(self.db.query(func.coalesce(
                    func.sum(InsuranceClaim.approved_amount - InsuranceClaim.paid_amount), 0))
                 .filter(InsuranceClaim.is_deleted.is_(False),
                         InsuranceClaim.status.in_([InsuranceClaimStatus.APPROVED,
                                                    InsuranceClaimStatus.PARTIALLY_APPROVED]))
                 .scalar() or 0)
        capitation = Decimal("0")
        for l in (self.db.query(CapitationScheduleLine)
                  .filter(CapitationScheduleLine.is_deleted.is_(False)).all()):
            if str(getattr(l.status, "value", l.status)) in ("CONFIRMED", "PARTIALLY_PAID"):
                capitation += _d(l.expected_amount) - _d(l.received_amount)
        return {"patient_self_pay": str(patient),
                "hmo_fee_for_service": str(max(hmo, Decimal('0'))),
                "capitation": str(capitation),
                "total": str(patient + max(hmo, Decimal('0')) + capitation)}

    # ------------------------------------------------------------------
    # Pre-close checklist + posting status
    # ------------------------------------------------------------------

    def pre_close_checklist(self, period_id: int) -> dict:
        period = (self.db.query(AccountingPeriod)
                  .filter(AccountingPeriod.id == period_id).first())
        if period is None:
            raise NotFoundError("Period not found.")
        drafts = (self.db.query(JournalEntry)
                  .filter(JournalEntry.is_deleted.is_(False),
                          JournalEntry.status.in_([JournalEntryStatus.DRAFT,
                                                   JournalEntryStatus.PENDING_APPROVAL]),
                          JournalEntry.entry_date >= period.start_date,
                          JournalEntry.entry_date <= period.end_date).count())
        unmatched_bank = (self.db.query(BankStatementLine)
                          .filter(BankStatementLine.is_deleted.is_(False),
                                  BankStatementLine.matched_journal_line_id.is_(None),
                                  BankStatementLine.line_date >= period.start_date,
                                  BankStatementLine.line_date <= period.end_date).count())
        unbatched_claims = (self.db.query(InsuranceClaim)
                            .filter(InsuranceClaim.is_deleted.is_(False),
                                    InsuranceClaim.batch_id.is_(None),
                                    InsuranceClaim.status == InsuranceClaimStatus.DRAFT).count())
        pending = self.posting_status()
        unswept = sum(s["pending"] for s in pending["sources"])
        checklist = [
            {"item": "Draft / pending-approval journal entries in period",
             "count": drafts, "ok": drafts == 0},
            {"item": "Unswept operational money events", "count": unswept, "ok": unswept == 0},
            {"item": "Unmatched bank statement lines in period",
             "count": unmatched_bank, "ok": unmatched_bank == 0},
            {"item": "Un-batched draft insurance claims",
             "count": unbatched_claims, "ok": unbatched_claims == 0},
        ]
        return {"period_id": period.id, "period": period.code,
                "ready": all(c["ok"] for c in checklist), "checklist": checklist}

    def posting_status(self) -> dict:
        """Per auto-posting source: how many operational records are swept vs
        pending (best-effort counts, cheap queries)."""
        from app.models.all_models import BillingPayment
        from app.models.finance_models import CapitationPayment, PettyCashVoucher as PCV

        def _swept(prefix: str) -> set[str]:
            rows = (self.db.query(JournalEntry.source_ref)
                    .filter(JournalEntry.source_ref.like(f"{prefix}:%"),
                            JournalEntry.is_deleted.is_(False)).all())
            return {r[0] for r in rows}

        sources = []
        # billing payments
        bp_ids = [str(r[0]) for r in self.db.query(BillingPayment.id)
                  .filter(BillingPayment.is_deleted.is_(False)).all()]
        swept = _swept("billing_payment")
        sources.append({"source": "billing_payment", "total": len(bp_ids),
                        "swept": len([i for i in bp_ids if f"billing_payment:{i}" in swept]),
                        "pending": len([i for i in bp_ids if f"billing_payment:{i}" not in swept])})
        # claims approved
        claim_ids = [str(r[0]) for r in self.db.query(InsuranceClaim.id)
                     .filter(InsuranceClaim.is_deleted.is_(False),
                             InsuranceClaim.status.in_([
                                 InsuranceClaimStatus.APPROVED,
                                 InsuranceClaimStatus.PARTIALLY_APPROVED,
                                 InsuranceClaimStatus.PAID])).all()]
        swept = _swept("insurance_claim")
        sources.append({"source": "insurance_claim", "total": len(claim_ids),
                        "swept": len([i for i in claim_ids if f"insurance_claim:{i}" in swept]),
                        "pending": len([i for i in claim_ids if f"insurance_claim:{i}" not in swept])})
        # capitation schedules + payments
        line_ids = [str(r[0]) for r in self.db.query(CapitationScheduleLine.id)
                    .filter(CapitationScheduleLine.is_deleted.is_(False),
                            CapitationScheduleLine.confirmed_at.isnot(None)).all()]
        swept = _swept("capitation_schedule")
        sources.append({"source": "capitation_schedule", "total": len(line_ids),
                        "swept": len([i for i in line_ids if f"capitation_schedule:{i}" in swept]),
                        "pending": len([i for i in line_ids if f"capitation_schedule:{i}" not in swept])})
        pay_ids = [str(r[0]) for r in self.db.query(CapitationPayment.id)
                   .filter(CapitationPayment.is_deleted.is_(False)).all()]
        swept = _swept("capitation_payment")
        sources.append({"source": "capitation_payment", "total": len(pay_ids),
                        "swept": len([i for i in pay_ids if f"capitation_payment:{i}" in swept]),
                        "pending": len([i for i in pay_ids if f"capitation_payment:{i}" not in swept])})
        return {"sources": sources,
                "checked_at": datetime.now(timezone.utc).isoformat()}
