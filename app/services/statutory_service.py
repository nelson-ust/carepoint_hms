# app/services/statutory_service.py
from __future__ import annotations

"""
Statutory remittances — the compliance side of hospital finance.

The hospital accumulates statutory liabilities all month:
* PAYE, pension, NHF and other deductions withheld from payroll,
* WHT withheld when paying vendors / professionals,
* VAT charged on invoices.
Each already lands on its own payable account through the auto-posting
pipeline. This module closes the loop:

* **Positions** — per statutory type: what has accrued, what has been
  remitted, and what is outstanding (straight from the posted ledger, so it
  can never drift from the books).
* **Remittances** — record the actual payment to FIRS / State IRS / a PFA /
  NHF..., posting Dr <payable> / Cr Bank (idempotent via
  ``statutory_remittance:{id}``), optionally marking WHT records REMITTED.
* **Filing schedules** — the per-person / per-payee workbooks the
  authorities require: PAYE, pension (grouped by PFA), NHF and the WHT
  register, as JSON for the UI and XLSX for filing.
"""

import io
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import (
    JournalEntryStatus,
    JournalSourceType,
    TaxKind,
    WithholdingTaxStatus,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    Account,
    JournalEntry,
    JournalEntryLine,
    PayrollLine,
    PayrollRun,
    PensionProvider,
    StaffProfile,
    TaxType,
    User,
    Vendor,
    WithholdingTaxRecord,
)
from app.models.finance_models import BankAccount, StatutoryRemittance
from app.services.accounting_service import AccountingService, _d
from app.services.system_accounts_service import audit, resolve_system_account

#: statutory type -> (system account key, default authority label)
STATUTORY_TYPES: dict[str, tuple[str, str]] = {
    "PAYE":    ("PAYE_PAYABLE", "State Internal Revenue Service"),
    "PENSION": ("PENSION_PAYABLE", "Pension Fund Administrator"),
    "NHF":     ("NHF_PAYABLE", "Federal Mortgage Bank (NHF)"),
    "WHT":     ("WHT_PAYABLE", "FIRS / State IRS"),
    "VAT":     ("VAT_PAYABLE", "FIRS"),
    "OTHER":   ("OTHER_DEDUCTIONS_PAYABLE", "Other authority"),
}


def _month_bounds(period_code: str) -> tuple[date, date]:
    try:
        year, month = (int(x) for x in period_code.split("-"))
        start = date(year, month, 1)
    except (ValueError, AttributeError):
        raise BadRequestError("period_code must be YYYY-MM.")
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


def get_or_create_wht_tax_type(db: Session) -> TaxType:
    tt = (db.query(TaxType)
          .filter(TaxType.is_withholding.is_(True),
                  TaxType.is_deleted.is_(False))
          .order_by(TaxType.id.asc()).first())
    if tt is not None:
        return tt
    tt = TaxType(code="WHT", name="Withholding Tax", kind=TaxKind.WHT,
                 is_withholding=True,
                 description="Auto-created for withholding at source.")
    db.add(tt)
    db.flush()
    return tt


def record_vendor_wht(db: Session, *, vendor: Optional[Vendor], gross_amount,
                      rate_percent, wht_amount, reference: Optional[str] = None,
                      notes: Optional[str] = None) -> WithholdingTaxRecord:
    """Register WHT withheld on a vendor payment (ledger already posted by
    the caller). Kept commit-free so it joins the caller's transaction."""
    tt = get_or_create_wht_tax_type(db)
    rec = WithholdingTaxRecord(
        tax_type_id=tt.id,
        payee_name=vendor.name if vendor is not None else "Vendor",
        payee_tax_id=getattr(vendor, "tax_id", None),
        payee_kind="VENDOR",
        gross_amount=_d(gross_amount),
        rate_percent_snapshot=_d(rate_percent),
        wht_amount=_d(wht_amount),
        status=WithholdingTaxStatus.DEDUCTED,
        deducted_at=datetime.now(timezone.utc),
        notes=(notes or "") + (f" [ref {reference}]" if reference else ""),
    )
    db.add(rec)
    db.flush()
    return rec


class StatutoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounting = AccountingService(db)

    # ------------------------------------------------------------------
    # Positions (ledger-derived, cannot drift)
    # ------------------------------------------------------------------

    def _account_balance(self, account: Account) -> dict:
        dr, cr = (self.db.query(
            func.coalesce(func.sum(JournalEntryLine.debit), 0),
            func.coalesce(func.sum(JournalEntryLine.credit), 0))
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .filter(JournalEntryLine.account_id == account.id,
                    JournalEntry.status == JournalEntryStatus.POSTED,
                    JournalEntry.is_deleted.is_(False))
            .first())
        accrued, remitted = _d(cr), _d(dr)
        return {"accrued": accrued, "remitted": remitted,
                "outstanding": accrued - remitted}

    def positions(self) -> list[dict]:
        out = []
        for rtype, (key, authority) in STATUTORY_TYPES.items():
            acct = resolve_system_account(self.db, key)
            bal = self._account_balance(acct)
            last = (self.db.query(StatutoryRemittance)
                    .filter(StatutoryRemittance.remittance_type == rtype,
                            StatutoryRemittance.is_deleted.is_(False))
                    .order_by(StatutoryRemittance.paid_at.desc()).first())
            row = {
                "type": rtype,
                "default_authority": authority,
                "account": f"{acct.code} · {acct.name}",
                "account_id": acct.id,
                "accrued": str(bal["accrued"]),
                "remitted": str(bal["remitted"]),
                "outstanding": str(bal["outstanding"]),
                "last_remitted_at": last.paid_at.isoformat() if last else None,
            }
            if rtype == "WHT":
                pending = (self.db.query(
                    func.count(WithholdingTaxRecord.id),
                    func.coalesce(func.sum(WithholdingTaxRecord.wht_amount), 0))
                    .filter(WithholdingTaxRecord.is_deleted.is_(False),
                            WithholdingTaxRecord.status.in_([
                                WithholdingTaxStatus.PENDING,
                                WithholdingTaxStatus.DEDUCTED])).first())
                row["wht_pending_records"] = int(pending[0] or 0)
                row["wht_pending_value"] = str(_d(pending[1]))
            out.append(row)
        return out

    # ------------------------------------------------------------------
    # Remittances
    # ------------------------------------------------------------------

    def _remittance_read(self, r: StatutoryRemittance) -> dict:
        return {
            "id": r.id, "remittance_type": r.remittance_type,
            "period_code": r.period_code, "authority": r.authority,
            "pension_provider_id": r.pension_provider_id,
            "amount": str(_d(r.amount)),
            "paid_at": r.paid_at.isoformat(),
            "bank_account_id": r.bank_account_id,
            "reference": r.reference, "receipt_url": r.receipt_url,
            "notes": r.notes,
        }

    def list_remittances(self, *, remittance_type: Optional[str] = None,
                         period_code: Optional[str] = None) -> list[dict]:
        q = (self.db.query(StatutoryRemittance)
             .filter(StatutoryRemittance.is_deleted.is_(False)))
        if remittance_type:
            q = q.filter(StatutoryRemittance.remittance_type == remittance_type.upper())
        if period_code:
            q = q.filter(StatutoryRemittance.period_code == period_code)
        return [self._remittance_read(r)
                for r in q.order_by(StatutoryRemittance.paid_at.desc(),
                                    StatutoryRemittance.id.desc()).all()]

    def create_remittance(self, *, remittance_type: str, period_code: str,
                          paid_at: date, amount=None,
                          bank_account_id: Optional[int] = None,
                          authority: Optional[str] = None,
                          pension_provider_id: Optional[int] = None,
                          reference: Optional[str] = None,
                          receipt_url: Optional[str] = None,
                          notes: Optional[str] = None,
                          wht_record_ids: Optional[list[int]] = None,
                          user_id: Optional[int] = None) -> dict:
        rtype = (remittance_type or "").strip().upper()
        if rtype not in STATUTORY_TYPES:
            raise BadRequestError(
                f"Unknown remittance type '{remittance_type}'. "
                f"Valid: {', '.join(STATUTORY_TYPES)}.")
        _month_bounds(period_code)  # validates format
        key, default_authority = STATUTORY_TYPES[rtype]
        payable = resolve_system_account(self.db, key)
        outstanding = self._account_balance(payable)["outstanding"]

        amount = _d(amount) if amount is not None else outstanding
        if amount <= 0:
            raise BadRequestError(
                f"Nothing outstanding for {rtype} (balance {outstanding}). "
                "Run the posting sweep first if liabilities are pending.")
        if amount > outstanding:
            raise BadRequestError(
                f"Remittance {amount} exceeds the outstanding {rtype} "
                f"liability ({outstanding}).")

        bank_ledger_id = None
        if bank_account_id is not None:
            b = (self.db.query(BankAccount)
                 .filter(BankAccount.id == bank_account_id,
                         BankAccount.is_deleted.is_(False)).first())
            if b is None:
                raise NotFoundError("Bank account not found.")
            bank_ledger_id = b.account_id
        if bank_ledger_id is None:
            bank_ledger_id = resolve_system_account(self.db, "BANK_DEFAULT").id

        if pension_provider_id is not None:
            pfa = (self.db.query(PensionProvider)
                   .filter(PensionProvider.id == pension_provider_id).first())
            if pfa is None:
                raise NotFoundError("Pension provider not found.")
            authority = authority or pfa.name

        r = StatutoryRemittance(
            remittance_type=rtype, period_code=period_code,
            authority=authority or default_authority,
            pension_provider_id=pension_provider_id,
            amount=amount, paid_at=paid_at, bank_account_id=bank_account_id,
            reference=reference, receipt_url=receipt_url, notes=notes,
            created_by_user_id=user_id)
        self.db.add(r)
        self.db.flush()

        self.accounting.create_entry(
            entry_date=paid_at,
            memo=f"{rtype} remittance {period_code} — {r.authority}",
            lines=[
                {"account_id": payable.id, "debit": amount, "credit": 0,
                 "description": f"{rtype} {period_code} remitted"},
                {"account_id": bank_ledger_id, "debit": 0, "credit": amount,
                 "description": reference or f"{rtype} remittance"},
            ],
            source_type=JournalSourceType.TAX,
            source_ref=f"statutory_remittance:{r.id}",
            user_id=user_id, auto_post=True)

        # WHT: tie the covered register records to this remittance.
        marked = 0
        if rtype == "WHT":
            ids = wht_record_ids
            if ids is None:
                start, end = _month_bounds(period_code)
                ids = [row[0] for row in self.db.query(WithholdingTaxRecord.id)
                       .filter(WithholdingTaxRecord.is_deleted.is_(False),
                               WithholdingTaxRecord.status.in_([
                                   WithholdingTaxStatus.PENDING,
                                   WithholdingTaxStatus.DEDUCTED]),
                               WithholdingTaxRecord.deducted_at >= datetime(
                                   start.year, start.month, 1, tzinfo=timezone.utc),
                               WithholdingTaxRecord.deducted_at < datetime(
                                   end.year, end.month, 1, tzinfo=timezone.utc)).all()]
            for rid in ids or []:
                rec = (self.db.query(WithholdingTaxRecord)
                       .filter(WithholdingTaxRecord.id == rid).first())
                if rec is not None and rec.status in (
                        WithholdingTaxStatus.PENDING, WithholdingTaxStatus.DEDUCTED):
                    rec.status = WithholdingTaxStatus.REMITTED
                    rec.remitted_at = datetime(
                        paid_at.year, paid_at.month, paid_at.day, tzinfo=timezone.utc)
                    if reference and not rec.certificate_no:
                        rec.notes = (rec.notes or "") + f" [remittance {reference}]"
                    marked += 1

        audit(self.db, action="STATUTORY_REMITTED", entity_type="statutory_remittance",
              entity_id=r.id, user_id=user_id,
              summary=f"{rtype} {period_code}: {amount} to {r.authority}",
              detail={"wht_records_marked": marked})
        self.db.commit()
        out = self._remittance_read(r)
        out["wht_records_marked"] = marked
        return out

    # ------------------------------------------------------------------
    # WHT register
    # ------------------------------------------------------------------

    def wht_register(self, *, period_code: Optional[str] = None,
                     status: Optional[str] = None) -> list[dict]:
        q = (self.db.query(WithholdingTaxRecord)
             .filter(WithholdingTaxRecord.is_deleted.is_(False)))
        if period_code:
            start, end = _month_bounds(period_code)
            q = q.filter(WithholdingTaxRecord.deducted_at >= datetime(
                             start.year, start.month, 1, tzinfo=timezone.utc),
                         WithholdingTaxRecord.deducted_at < datetime(
                             end.year, end.month, 1, tzinfo=timezone.utc))
        if status:
            q = q.filter(WithholdingTaxRecord.status == WithholdingTaxStatus(status))
        return [{
            "id": w.id, "payee_name": w.payee_name, "payee_tax_id": w.payee_tax_id,
            "payee_kind": w.payee_kind,
            "gross_amount": str(_d(w.gross_amount)),
            "rate_percent": str(_d(w.rate_percent_snapshot)),
            "wht_amount": str(_d(w.wht_amount)),
            "status": w.status.value if hasattr(w.status, "value") else w.status,
            "deducted_at": w.deducted_at.isoformat() if w.deducted_at else None,
            "remitted_at": w.remitted_at.isoformat() if w.remitted_at else None,
            "certificate_no": w.certificate_no, "notes": w.notes,
        } for w in q.order_by(WithholdingTaxRecord.id.desc()).all()]

    # ------------------------------------------------------------------
    # Filing schedules
    # ------------------------------------------------------------------

    def _payroll_lines_for(self, period_code: str):
        start, end = _month_bounds(period_code)
        return (self.db.query(PayrollLine, StaffProfile, User)
                .join(PayrollRun, PayrollRun.id == PayrollLine.payroll_run_id)
                .join(StaffProfile, StaffProfile.id == PayrollLine.staff_profile_id)
                .join(User, User.id == StaffProfile.user_id)
                .filter(PayrollLine.is_deleted.is_(False),
                        PayrollRun.is_deleted.is_(False),
                        PayrollRun.period_end >= start,
                        PayrollRun.period_end < end)
                .all())

    def schedule(self, kind: str, *, period_code: str) -> dict:
        kind = (kind or "").strip().upper()
        rows: list[dict] = []
        if kind == "PAYE":
            for line, staff, user in self._payroll_lines_for(period_code):
                if _d(line.paye_amount) <= 0:
                    continue
                rows.append({
                    "staff_no": staff.staff_no,
                    "name": f"{user.first_name} {user.last_name}",
                    "tax_id": staff.tax_id,
                    "gross_pay": str(_d(line.gross_pay)),
                    "amount": str(_d(line.paye_amount)),
                })
        elif kind == "PENSION":
            for line, staff, user in self._payroll_lines_for(period_code):
                if _d(line.pension_amount) <= 0:
                    continue
                pfa = (self.db.query(PensionProvider)
                       .filter(PensionProvider.id == staff.pension_provider_id).first()
                       if staff.pension_provider_id else None)
                rows.append({
                    "staff_no": staff.staff_no,
                    "name": f"{user.first_name} {user.last_name}",
                    "pension_pin": staff.pension_pin,
                    "pfa": pfa.name if pfa else None,
                    "gross_pay": str(_d(line.gross_pay)),
                    "amount": str(_d(line.pension_amount)),
                })
        elif kind == "NHF":
            for line, staff, user in self._payroll_lines_for(period_code):
                if _d(line.nhf_amount) <= 0:
                    continue
                rows.append({
                    "staff_no": staff.staff_no,
                    "name": f"{user.first_name} {user.last_name}",
                    "nhf_no": staff.nhf_no,
                    "gross_pay": str(_d(line.gross_pay)),
                    "amount": str(_d(line.nhf_amount)),
                })
        elif kind == "WHT":
            for w in self.wht_register(period_code=period_code):
                rows.append({
                    "payee_name": w["payee_name"], "tax_id": w["payee_tax_id"],
                    "payee_kind": w["payee_kind"],
                    "gross_amount": w["gross_amount"],
                    "rate_percent": w["rate_percent"],
                    "amount": w["wht_amount"], "status": w["status"],
                })
        else:
            raise BadRequestError(
                f"Unknown schedule '{kind}'. Valid: PAYE, PENSION, NHF, WHT.")
        total = sum((Decimal(r["amount"]) for r in rows), Decimal("0"))
        return {"kind": kind, "period_code": period_code,
                "rows": rows, "count": len(rows), "total": str(total)}

    def schedule_xlsx(self, kind: str, *, period_code: str) -> tuple[str, bytes]:
        from openpyxl import Workbook
        data = self.schedule(kind, period_code=period_code)
        wb = Workbook()
        ws = wb.active
        ws.title = f"{data['kind']} {period_code}"
        if data["rows"]:
            headers = list(data["rows"][0].keys())
            ws.append([h.replace("_", " ").title() for h in headers])
            for r in data["rows"]:
                ws.append([(float(v) if h in ("gross_pay", "gross_amount",
                                              "amount", "rate_percent") and v
                            else v) for h, v in r.items()])
            ws.append([])
            ws.append(["TOTAL"] + [""] * (len(headers) - 2) + [float(data["total"])])
        else:
            ws.append([f"No {data['kind']} entries for {period_code}."])
        buf = io.BytesIO()
        wb.save(buf)
        return f"{data['kind'].lower()}_schedule_{period_code}.xlsx", buf.getvalue()
