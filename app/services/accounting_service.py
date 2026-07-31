# app/services/accounting_service.py
from __future__ import annotations

"""
Double-entry accounting for the hospital.

Design principles (standard accounting semantics):

* Every journal entry balances: sum(debits) == sum(credits) > 0.
* Only POSTED entries hit the ledgers and financial statements.
* Posted entries are immutable — corrections happen via reversal entries.
* Entries belong to an accounting period; CLOSED periods reject posting.
* Operational money events (billing payments, payroll, expense claims,
  salary advances) are auto-posted with idempotent ``source_ref`` keys so a
  re-run never double-books.

Normal balances: ASSET/EXPENSE are debit-normal; LIABILITY/EQUITY/REVENUE are
credit-normal. Trial balance shows raw debit/credit totals; P&L and balance
sheet apply normal-balance signs.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.enums import (
    AccountType,
    AccountingPeriodStatus,
    JournalEntryStatus,
    JournalSourceType,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    Account,
    AccountingPeriod,
    JournalEntry,
    JournalEntryLine,
)

_TWO = Decimal("0.01")


def _d(v) -> Decimal:
    try:
        return Decimal(str(v or 0)).quantize(_TWO)
    except Exception:
        return Decimal("0.00")


def _now() -> datetime:
    return datetime.now(timezone.utc)


DEBIT_NORMAL = {AccountType.ASSET, AccountType.EXPENSE}


def _entry_read(e: JournalEntry, *, with_lines: bool = True) -> dict:
    out = {
        "id": e.id,
        "entry_no": e.entry_no,
        "entry_date": e.entry_date.isoformat() if e.entry_date else None,
        "memo": e.memo,
        "status": e.status.value if hasattr(e.status, "value") else e.status,
        "source_type": e.source_type.value if hasattr(e.source_type, "value") else e.source_type,
        "source_ref": e.source_ref,
        "total_debit": str(e.total_debit or 0),
        "total_credit": str(e.total_credit or 0),
        "posted_at": e.posted_at.isoformat() if e.posted_at else None,
        "reversal_of_id": e.reversal_of_id,
        "period_code": e.period.code if getattr(e, "period", None) else None,
    }
    if with_lines:
        out["lines"] = [
            {
                "id": l.id,
                "account_id": l.account_id,
                "account_code": l.account_code,
                "account_name": l.account_name,
                "description": l.description,
                "debit": str(l.debit or 0),
                "credit": str(l.credit or 0),
            }
            for l in (e.lines or [])
        ]
    return out


class AccountingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Periods
    # ------------------------------------------------------------------
    def ensure_period_for(self, on: date) -> AccountingPeriod:
        """Return (creating if needed) the calendar-month period covering ``on``."""
        code = f"{on.year:04d}-{on.month:02d}"
        period = self.db.query(AccountingPeriod).filter(
            AccountingPeriod.code == code, AccountingPeriod.is_deleted.is_(False)
        ).first()
        if period:
            return period
        start = on.replace(day=1)
        end = (start.replace(year=start.year + 1, month=1) if start.month == 12
               else start.replace(month=start.month + 1)) - timedelta(days=1)
        period = AccountingPeriod(
            code=code, name=start.strftime("%B %Y"), start_date=start, end_date=end,
            status=AccountingPeriodStatus.OPEN,
        )
        self.db.add(period)
        self.db.flush()
        return period

    def list_periods(self) -> list[dict]:
        rows = self.db.query(AccountingPeriod).filter(
            AccountingPeriod.is_deleted.is_(False)
        ).order_by(AccountingPeriod.start_date.desc()).all()
        return [{
            "id": p.id, "code": p.code, "name": p.name,
            "start_date": p.start_date.isoformat(), "end_date": p.end_date.isoformat(),
            "status": p.status.value if hasattr(p.status, "value") else p.status,
            "closed_at": p.closed_at.isoformat() if p.closed_at else None,
        } for p in rows]

    def set_period_status(self, period_id: int, *, close: bool, user_id: Optional[int] = None) -> dict:
        period = self.db.query(AccountingPeriod).filter(AccountingPeriod.id == period_id).first()
        if period is None:
            raise NotFoundError(message="Accounting period not found.")
        if close:
            draft_count = self.db.query(func.count(JournalEntry.id)).filter(
                JournalEntry.period_id == period.id,
                JournalEntry.status == JournalEntryStatus.DRAFT,
                JournalEntry.is_deleted.is_(False),
            ).scalar() or 0
            if draft_count:
                raise BadRequestError(
                    message=f"Cannot close {period.code}: {draft_count} draft entr{'y' if draft_count == 1 else 'ies'} remain. Post or delete them first."
                )
            period.status = AccountingPeriodStatus.CLOSED
            period.closed_by_user_id = user_id
            period.closed_at = _now()
        else:
            period.status = AccountingPeriodStatus.OPEN
            period.closed_by_user_id = None
            period.closed_at = None
        self.db.commit()
        return {"id": period.id, "code": period.code,
                "status": period.status.value}

    # ------------------------------------------------------------------
    # Journal entries
    # ------------------------------------------------------------------
    def _validate_lines(self, lines: list[dict]) -> tuple[Decimal, Decimal]:
        if not lines or len(lines) < 2:
            raise BadRequestError(message="A journal entry needs at least two lines.")
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")
        for ln in lines:
            debit, credit = _d(ln.get("debit")), _d(ln.get("credit"))
            if debit < 0 or credit < 0:
                raise BadRequestError(message="Line amounts cannot be negative.")
            if (debit > 0) == (credit > 0):
                raise BadRequestError(message="Each line must be either a debit or a credit (not both, not neither).")
            total_debit += debit
            total_credit += credit
        if total_debit != total_credit:
            raise BadRequestError(
                message=f"Entry is out of balance: debits {total_debit} ≠ credits {total_credit}.")
        if total_debit <= 0:
            raise BadRequestError(message="Entry total must be greater than zero.")
        return total_debit, total_credit

    def create_entry(self, *, entry_date: date, memo: Optional[str], lines: list[dict],
                     source_type: JournalSourceType = JournalSourceType.MANUAL,
                     source_ref: Optional[str] = None,
                     user_id: Optional[int] = None,
                     auto_post: bool = False) -> dict:
        total_debit, total_credit = self._validate_lines(lines)
        period = self.ensure_period_for(entry_date)
        if period.status == AccountingPeriodStatus.CLOSED:
            raise BadRequestError(message=f"Period {period.code} is closed.")

        # Resolve accounts up front so bad ids fail cleanly.
        entry = JournalEntry(
            entry_no=f"JE-{entry_date.strftime('%Y%m')}-{uuid.uuid4().hex[:8].upper()}",
            entry_date=entry_date, period_id=period.id, memo=memo,
            status=JournalEntryStatus.DRAFT, source_type=source_type,
            source_ref=source_ref, total_debit=total_debit, total_credit=total_credit,
            created_by_user_id=user_id,
        )
        self.db.add(entry)
        self.db.flush()
        for ln in lines:
            account = self.db.query(Account).filter(
                Account.id == ln.get("account_id"), Account.is_deleted.is_(False)
            ).first()
            if account is None:
                raise BadRequestError(message=f"Unknown account id {ln.get('account_id')}.")
            self.db.add(JournalEntryLine(
                journal_entry_id=entry.id, account_id=account.id,
                account_code=account.code, account_name=account.name,
                description=ln.get("description"),
                debit=_d(ln.get("debit")), credit=_d(ln.get("credit")),
            ))
        self.db.flush()
        if auto_post:
            self._post(entry, user_id=user_id)
        self.db.commit()
        self.db.refresh(entry)
        return _entry_read(entry)

    def _post(self, entry: JournalEntry, *, user_id: Optional[int]) -> None:
        if entry.status != JournalEntryStatus.DRAFT:
            raise BadRequestError(message=f"Only draft entries can be posted (this one is {entry.status.value}).")
        if entry.period and entry.period.status == AccountingPeriodStatus.CLOSED:
            raise BadRequestError(message=f"Period {entry.period.code} is closed.")
        entry.status = JournalEntryStatus.POSTED
        entry.posted_by_user_id = user_id
        entry.posted_at = _now()

    def post_entry(self, entry_id: int, *, user_id: Optional[int] = None) -> dict:
        entry = self._get(entry_id)
        self._post(entry, user_id=user_id)
        self.db.commit()
        self.db.refresh(entry)
        return _entry_read(entry)

    def reverse_entry(self, entry_id: int, *, user_id: Optional[int] = None,
                      memo: Optional[str] = None) -> dict:
        original = self._get(entry_id)
        if original.status != JournalEntryStatus.POSTED:
            raise BadRequestError(message="Only posted entries can be reversed.")
        already = self.db.query(JournalEntry).filter(
            JournalEntry.reversal_of_id == original.id,
            JournalEntry.is_deleted.is_(False),
        ).first()
        if already is not None:
            raise BadRequestError(message=f"Already reversed by {already.entry_no}.")

        today = date.today()
        period = self.ensure_period_for(today)
        if period.status == AccountingPeriodStatus.CLOSED:
            raise BadRequestError(message=f"Period {period.code} is closed.")
        rev = JournalEntry(
            entry_no=f"JE-{today.strftime('%Y%m')}-{uuid.uuid4().hex[:8].upper()}",
            entry_date=today, period_id=period.id,
            memo=memo or f"Reversal of {original.entry_no}",
            status=JournalEntryStatus.POSTED,
            source_type=JournalSourceType.ADJUSTMENT,
            total_debit=original.total_credit, total_credit=original.total_debit,
            created_by_user_id=user_id, posted_by_user_id=user_id,
            posted_at=_now(), reversal_of_id=original.id,
        )
        self.db.add(rev)
        self.db.flush()
        for l in original.lines:
            self.db.add(JournalEntryLine(
                journal_entry_id=rev.id, account_id=l.account_id,
                account_code=l.account_code, account_name=l.account_name,
                description=f"Reversal: {l.description or ''}".strip(),
                debit=l.credit, credit=l.debit,
            ))
        original.status = JournalEntryStatus.REVERSED
        self.db.commit()
        self.db.refresh(rev)
        return _entry_read(rev)

    def delete_draft(self, entry_id: int) -> dict:
        entry = self._get(entry_id)
        if entry.status != JournalEntryStatus.DRAFT:
            raise BadRequestError(message="Only draft entries can be deleted; reverse posted entries instead.")
        entry.is_deleted = True
        # free the idempotency key so the source can repost if needed
        entry.source_ref = None
        self.db.commit()
        return {"id": entry_id, "deleted": True}

    def _get(self, entry_id: int) -> JournalEntry:
        entry = self.db.query(JournalEntry).options(
            joinedload(JournalEntry.lines), joinedload(JournalEntry.period)
        ).filter(JournalEntry.id == entry_id, JournalEntry.is_deleted.is_(False)).first()
        if entry is None:
            raise NotFoundError(message="Journal entry not found.")
        return entry

    def get_entry(self, entry_id: int) -> dict:
        return _entry_read(self._get(entry_id))

    def list_entries(self, *, status: Optional[str] = None, source: Optional[str] = None,
                     date_from: Optional[date] = None, date_to: Optional[date] = None,
                     page: int = 1, page_size: int = 25) -> dict:
        q = self.db.query(JournalEntry).options(joinedload(JournalEntry.period)).filter(
            JournalEntry.is_deleted.is_(False))
        if status:
            try:
                q = q.filter(JournalEntry.status == JournalEntryStatus(status.strip().upper()))
            except Exception:
                pass
        if source:
            try:
                q = q.filter(JournalEntry.source_type == JournalSourceType(source.strip().upper()))
            except Exception:
                pass
        if date_from:
            q = q.filter(JournalEntry.entry_date >= date_from)
        if date_to:
            q = q.filter(JournalEntry.entry_date <= date_to)
        total = q.count()
        rows = (q.order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc())
                 .offset((page - 1) * page_size).limit(page_size).all())
        return {"total": total, "page": page, "page_size": page_size,
                "items": [_entry_read(e, with_lines=False) for e in rows]}

    # ------------------------------------------------------------------
    # Auto-posting from operations (idempotent via source_ref)
    # ------------------------------------------------------------------
    def _already_posted(self, ref: str) -> bool:
        return self.db.query(JournalEntry.id).filter(
            JournalEntry.source_ref == ref, JournalEntry.is_deleted.is_(False)
        ).first() is not None

    def auto_post_operations(self, *, user_id: Optional[int] = None, limit: int = 500) -> dict:
        """Sweep operational money events into POSTED journal entries.

        * Billing payments (completed): Dr cash/bank account, Cr the revenue
          account stamped on the payment (fallback: generic patient revenue).
        * Approved reimbursements (expense claims): Dr expense account, Cr cash.
        * Approved salary advances: Dr staff-advance (asset/expense) account, Cr cash.
        """
        from app.models.all_models import BillingPayment, ReimbursementRequest, SalaryAdvance
        from app.utils.charge_capture import resolve_cash_account, resolve_revenue_account

        created: list[str] = []
        skipped = 0

        def _account_by_code(code: Optional[str]) -> Optional[Account]:
            if not code:
                return None
            return self.db.query(Account).filter(
                Account.code == code, Account.is_deleted.is_(False)).first()

        # ---- 1) Billing payments ----
        payments = self.db.query(BillingPayment).filter(
            BillingPayment.is_deleted.is_(False),
        ).order_by(BillingPayment.id.asc()).limit(limit).all()
        for p in payments:
            status_val = str(getattr(p.payment_status, "value", p.payment_status) or "").upper()
            if status_val not in {"COMPLETED", "PAID", "SUCCESS", "SUCCESSFUL"}:
                continue
            ref = f"billing_payment:{p.id}"
            if self._already_posted(ref):
                skipped += 1
                continue
            amount = _d(p.amount)
            if amount <= 0:
                continue
            cash = resolve_cash_account(self.db, payment_method=p.payment_method)
            revenue = _account_by_code(p.account_code) or resolve_revenue_account(self.db, domain=None)
            if cash is None or revenue is None:
                continue
            when = (p.paid_at.date() if p.paid_at else (p.date_created.date() if p.date_created else date.today()))
            self.create_entry(
                entry_date=when,
                memo=f"Patient payment {p.payment_reference}",
                lines=[
                    {"account_id": cash.id, "debit": amount, "credit": 0,
                     "description": f"Receipt {p.payment_reference} ({p.payment_method or 'CASH'})"},
                    {"account_id": revenue.id, "debit": 0, "credit": amount,
                     "description": "Patient service revenue"},
                ],
                source_type=JournalSourceType.BILLING_PAYMENT, source_ref=ref,
                user_id=user_id, auto_post=True,
            )
            created.append(ref)

        # ---- 2) Approved reimbursements (expense claims) ----
        try:
            claims = self.db.query(ReimbursementRequest).filter(
                ReimbursementRequest.is_deleted.is_(False)).limit(limit).all()
        except Exception:
            claims = []
        for c in claims:
            status_val = str(getattr(getattr(c, "status", None), "value", getattr(c, "status", "")) or "").upper()
            if status_val not in {"APPROVED", "PAID", "COMPLETED"}:
                continue
            ref = f"reimbursement:{c.id}"
            if self._already_posted(ref):
                skipped += 1
                continue
            amount = _d(getattr(c, "amount", 0))
            expense = None
            if getattr(c, "account_id", None):
                expense = self.db.query(Account).filter(Account.id == c.account_id).first()
            cash = resolve_cash_account(self.db, payment_method="CASH")
            if amount <= 0 or expense is None or cash is None:
                continue
            when = (c.date_created.date() if getattr(c, "date_created", None) else date.today())
            self.create_entry(
                entry_date=when, memo=f"Expense claim #{c.id}",
                lines=[
                    {"account_id": expense.id, "debit": amount, "credit": 0, "description": "Staff expense claim"},
                    {"account_id": cash.id, "debit": 0, "credit": amount, "description": "Reimbursement payout"},
                ],
                source_type=JournalSourceType.EXPENSE_CLAIM, source_ref=ref,
                user_id=user_id, auto_post=True,
            )
            created.append(ref)

        # ---- 3) Approved salary advances ----
        try:
            advances = self.db.query(SalaryAdvance).filter(
                SalaryAdvance.is_deleted.is_(False)).limit(limit).all()
        except Exception:
            advances = []
        for a in advances:
            status_val = str(getattr(getattr(a, "status", None), "value", getattr(a, "status", "")) or "").upper()
            # Cash only leaves the till at DISBURSEMENT, not approval.
            if status_val not in {"PAID", "DISBURSED"}:
                continue
            ref = f"salary_advance:{a.id}"
            if self._already_posted(ref):
                skipped += 1
                continue
            amount = _d(getattr(a, "amount", 0))
            adv_account = None
            if getattr(a, "account_id", None):
                adv_account = self.db.query(Account).filter(Account.id == a.account_id).first()
            cash = resolve_cash_account(self.db, payment_method="CASH")
            if amount <= 0 or adv_account is None or cash is None:
                continue
            when = (a.date_created.date() if getattr(a, "date_created", None) else date.today())
            self.create_entry(
                entry_date=when, memo=f"Salary advance #{a.id}",
                lines=[
                    {"account_id": adv_account.id, "debit": amount, "credit": 0, "description": "Staff salary advance"},
                    {"account_id": cash.id, "debit": 0, "credit": amount, "description": "Advance disbursement"},
                ],
                source_type=JournalSourceType.SALARY_ADVANCE, source_ref=ref,
                user_id=user_id, auto_post=True,
            )
            created.append(ref)

        # ---- 4) Approved / paid payroll runs ----
        try:
            from app.models.all_models import PayrollRun
            runs = self.db.query(PayrollRun).filter(
                PayrollRun.is_deleted.is_(False)).limit(limit).all()
        except Exception:
            runs = []
        for r in runs:
            status_val = str(getattr(getattr(r, "status", None), "value", getattr(r, "status", "")) or "").upper()
            if status_val not in {"APPROVED", "PAID", "COMPLETED", "DISBURSED"}:
                continue
            ref = f"payroll_run:{r.id}"
            if self._already_posted(ref):
                skipped += 1
                continue
            amount = _d(getattr(r, "total_net", 0))
            if amount <= 0:
                continue
            expense = None
            if getattr(r, "account_id", None):
                expense = self.db.query(Account).filter(Account.id == r.account_id).first()
            if expense is None:
                from app.services.finance_ops_service import get_or_create_system_account
                expense = get_or_create_system_account(self.db, "SALARY_EXP")
            cash = resolve_cash_account(self.db, payment_method="BANK_TRANSFER")
            if cash is None:
                continue
            when = getattr(r, "period_end", None) or date.today()

            # Advance recoveries withheld on this run clear the Staff Salary
            # Advances receivable, grouped by each advance's posting account.
            recovery_by_account: dict[int, Decimal] = {}
            try:
                from app.models.all_models import PayrollLine as _PL, SalaryAdvance as _SA
                from app.services.finance_ops_service import get_or_create_system_account as _sys_acct
                fallback_adv = None
                for pl in self.db.query(_PL).filter(_PL.payroll_run_id == r.id,
                                                    _PL.is_deleted.is_(False)).all():
                    bd = pl.breakdown_json or {}
                    rec = _d(bd.get("advance_recovery"))
                    if rec <= 0:
                        continue
                    adv_ids = bd.get("advance_ids") or []
                    advs = (self.db.query(_SA).filter(_SA.id.in_(adv_ids)).all()
                            if adv_ids else [])
                    remaining = rec
                    for adv in advs:
                        amt_a = min(_d(adv.amount), remaining)
                        if amt_a <= 0:
                            continue
                        acct_id = adv.account_id
                        if acct_id is None:
                            if fallback_adv is None:
                                fallback_adv = _sys_acct(self.db, "STAFF_ADV")
                            acct_id = fallback_adv.id
                        recovery_by_account[acct_id] = recovery_by_account.get(acct_id, Decimal("0")) + amt_a
                        remaining -= amt_a
                    if remaining > 0:
                        if fallback_adv is None:
                            fallback_adv = _sys_acct(self.db, "STAFF_ADV")
                        recovery_by_account[fallback_adv.id] = recovery_by_account.get(fallback_adv.id, Decimal("0")) + remaining
            except Exception:
                recovery_by_account = {}

            recovery_total = sum(recovery_by_account.values(), Decimal("0"))
            je_lines = [
                {"account_id": expense.id, "debit": amount + recovery_total, "credit": 0,
                 "description": f"Salaries {getattr(r, 'period_start', '')} – {getattr(r, 'period_end', '')}"},
                {"account_id": cash.id, "debit": 0, "credit": amount, "description": "Net salary disbursement"},
            ]
            for acct_id, rec_amt in recovery_by_account.items():
                je_lines.append({"account_id": acct_id, "debit": 0, "credit": rec_amt,
                                 "description": "Salary advance recovery"})
            self.create_entry(
                entry_date=when, memo=f"Payroll run {getattr(r, 'code', r.id)}",
                lines=je_lines,
                source_type=JournalSourceType.PAYROLL, source_ref=ref,
                user_id=user_id, auto_post=True,
            )
            created.append(ref)

        return {"created": len(created), "skipped_existing": skipped, "refs": created[:50]}

    # ------------------------------------------------------------------
    # Ledgers & financial statements (POSTED entries only)
    # ------------------------------------------------------------------
    def _posted_lines(self, *, date_from: Optional[date] = None, date_to: Optional[date] = None):
        q = (self.db.query(JournalEntryLine, JournalEntry)
             .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
             .filter(JournalEntry.status == JournalEntryStatus.POSTED,
                     JournalEntry.is_deleted.is_(False),
                     JournalEntryLine.is_deleted.is_(False)))
        if date_from:
            q = q.filter(JournalEntry.entry_date >= date_from)
        if date_to:
            q = q.filter(JournalEntry.entry_date <= date_to)
        return q

    def account_ledger(self, account_id: int, *, date_from: Optional[date] = None,
                       date_to: Optional[date] = None) -> dict:
        account = self.db.query(Account).filter(Account.id == account_id).first()
        if account is None:
            raise NotFoundError(message="Account not found.")
        rows = (self._posted_lines(date_from=date_from, date_to=date_to)
                .filter(JournalEntryLine.account_id == account_id)
                .order_by(JournalEntry.entry_date.asc(), JournalEntry.id.asc()).all())
        debit_normal = account.account_type in DEBIT_NORMAL
        balance = Decimal("0.00")
        items = []
        for line, entry in rows:
            debit, credit = _d(line.debit), _d(line.credit)
            balance += (debit - credit) if debit_normal else (credit - debit)
            items.append({
                "entry_id": entry.id, "entry_no": entry.entry_no,
                "entry_date": entry.entry_date.isoformat(),
                "memo": entry.memo, "description": line.description,
                "debit": str(debit), "credit": str(credit),
                "running_balance": str(balance),
            })
        return {
            "account": {"id": account.id, "code": account.code, "name": account.name,
                        "type": account.account_type.value},
            "normal_balance": "DEBIT" if debit_normal else "CREDIT",
            "closing_balance": str(balance),
            "items": items,
        }

    def _balances_by_account(self, *, date_from: Optional[date] = None,
                             date_to: Optional[date] = None) -> list[dict]:
        rows = (self._posted_lines(date_from=date_from, date_to=date_to)
                .with_entities(
                    JournalEntryLine.account_id,
                    func.sum(JournalEntryLine.debit).label("debit"),
                    func.sum(JournalEntryLine.credit).label("credit"))
                .group_by(JournalEntryLine.account_id).all())
        by_id = {r[0]: (_d(r[1]), _d(r[2])) for r in rows}
        accounts = self.db.query(Account).filter(
            Account.id.in_(list(by_id.keys())) if by_id else Account.id.is_(None)
        ).all()
        out = []
        for a in sorted(accounts, key=lambda x: x.code):
            debit, credit = by_id.get(a.id, (Decimal("0"), Decimal("0")))
            out.append({
                "account_id": a.id, "code": a.code, "name": a.name,
                "type": a.account_type.value, "debit": debit, "credit": credit,
            })
        return out

    def trial_balance(self, *, date_from: Optional[date] = None,
                      date_to: Optional[date] = None) -> dict:
        rows = self._balances_by_account(date_from=date_from, date_to=date_to)
        items, td, tc = [], Decimal("0"), Decimal("0")
        for r in rows:
            net = r["debit"] - r["credit"]
            debit = net if net > 0 else Decimal("0")
            credit = -net if net < 0 else Decimal("0")
            td += debit
            tc += credit
            items.append({**{k: r[k] for k in ("account_id", "code", "name", "type")},
                          "debit": str(debit), "credit": str(credit)})
        return {"items": items, "total_debit": str(td), "total_credit": str(tc),
                "balanced": td == tc}

    def profit_and_loss(self, *, date_from: date, date_to: date) -> dict:
        rows = self._balances_by_account(date_from=date_from, date_to=date_to)
        revenue, expenses = [], []
        rev_total, exp_total = Decimal("0"), Decimal("0")
        for r in rows:
            if r["type"] == AccountType.REVENUE.value:
                amt = r["credit"] - r["debit"]
                rev_total += amt
                revenue.append({"code": r["code"], "name": r["name"], "amount": str(amt)})
            elif r["type"] == AccountType.EXPENSE.value:
                amt = r["debit"] - r["credit"]
                exp_total += amt
                expenses.append({"code": r["code"], "name": r["name"], "amount": str(amt)})
        return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
                "revenue": revenue, "expenses": expenses,
                "total_revenue": str(rev_total), "total_expenses": str(exp_total),
                "net_income": str(rev_total - exp_total)}

    def balance_sheet(self, *, as_of: date) -> dict:
        rows = self._balances_by_account(date_to=as_of)
        assets, liabilities, equity = [], [], []
        a_t = l_t = e_t = Decimal("0")
        retained = Decimal("0")
        for r in rows:
            t = r["type"]
            if t == AccountType.ASSET.value:
                amt = r["debit"] - r["credit"]
                a_t += amt
                assets.append({"code": r["code"], "name": r["name"], "amount": str(amt)})
            elif t == AccountType.LIABILITY.value:
                amt = r["credit"] - r["debit"]
                l_t += amt
                liabilities.append({"code": r["code"], "name": r["name"], "amount": str(amt)})
            elif t == AccountType.EQUITY.value:
                amt = r["credit"] - r["debit"]
                e_t += amt
                equity.append({"code": r["code"], "name": r["name"], "amount": str(amt)})
            elif t == AccountType.REVENUE.value:
                retained += r["credit"] - r["debit"]
            elif t == AccountType.EXPENSE.value:
                retained -= r["debit"] - r["credit"]
        equity.append({"code": "—", "name": "Retained earnings (current)", "amount": str(retained)})
        e_t += retained
        return {"as_of": as_of.isoformat(),
                "assets": assets, "liabilities": liabilities, "equity": equity,
                "total_assets": str(a_t), "total_liabilities": str(l_t),
                "total_equity": str(e_t),
                "balanced": a_t == (l_t + e_t)}

    # ------------------------------------------------------------------
    # Accounts receivable ageing (from patient/insurer invoices)
    # ------------------------------------------------------------------
    def ar_aging(self, *, as_of: Optional[date] = None) -> dict:
        from app.models.all_models import Invoice
        as_of = as_of or date.today()
        invoices = self.db.query(Invoice).filter(
            Invoice.is_deleted.is_(False), Invoice.balance_due > 0).all()
        buckets = {"current": Decimal("0"), "d1_30": Decimal("0"), "d31_60": Decimal("0"),
                   "d61_90": Decimal("0"), "d90_plus": Decimal("0")}
        rows = []
        for inv in invoices:
            status_val = str(getattr(inv.status, "value", inv.status) or "").upper()
            if status_val in {"CANCELLED", "VOID", "VOIDED", "REFUNDED"}:
                continue
            due = (inv.due_date or inv.invoice_date)
            due_d = due.date() if hasattr(due, "date") else due
            overdue = (as_of - due_d).days
            balance = _d(inv.balance_due)
            key = ("current" if overdue <= 0 else "d1_30" if overdue <= 30
                   else "d31_60" if overdue <= 60 else "d61_90" if overdue <= 90 else "d90_plus")
            buckets[key] += balance
            rows.append({"invoice_no": inv.invoice_no, "due_date": due_d.isoformat(),
                         "days_overdue": max(0, overdue), "balance": str(balance), "bucket": key})
        return {"as_of": as_of.isoformat(),
                "buckets": {k: str(v) for k, v in buckets.items()},
                "total_outstanding": str(sum(buckets.values())), "items": rows}

    # ------------------------------------------------------------------
    # Year-end close: move revenue & expense balances to retained earnings
    # ------------------------------------------------------------------
    def close_fiscal_year(self, *, year: int, user_id: Optional[int] = None) -> dict:
        from app.services.finance_ops_service import get_or_create_system_account
        ref = f"year_close:{year}"
        if self._already_posted(ref):
            raise BadRequestError(message=f"Fiscal year {year} is already closed.")
        start, end = date(year, 1, 1), date(year, 12, 31)
        rows = self._balances_by_account(date_from=start, date_to=end)
        retained = get_or_create_system_account(self.db, "RETAINED")
        lines = []
        net = Decimal("0")
        for r in rows:
            if r["type"] == AccountType.REVENUE.value:
                bal = r["credit"] - r["debit"]
                if bal == 0:
                    continue
                # zero out revenue: debit it
                lines.append({"account_id": r["account_id"],
                              "debit": bal if bal > 0 else 0,
                              "credit": -bal if bal < 0 else 0,
                              "description": f"Close {r['code']} to retained earnings"})
                net += bal
            elif r["type"] == AccountType.EXPENSE.value:
                bal = r["debit"] - r["credit"]
                if bal == 0:
                    continue
                # zero out expense: credit it
                lines.append({"account_id": r["account_id"],
                              "debit": -bal if bal < 0 else 0,
                              "credit": bal if bal > 0 else 0,
                              "description": f"Close {r['code']} to retained earnings"})
                net -= bal
        if not lines:
            raise BadRequestError(message=f"No revenue or expense activity to close for {year}.")
        # balancing line to retained earnings (omitted when net is exactly zero —
        # the closing lines already balance and a 0/0 line would be invalid)
        if net != 0:
            lines.append({"account_id": retained.id,
                          "debit": -net if net < 0 else 0,
                          "credit": net if net > 0 else 0,
                          "description": f"Net income {year} to retained earnings"})
        entry = self.create_entry(
            entry_date=end, memo=f"Year-end closing entry {year}",
            lines=lines, source_type=JournalSourceType.ADJUSTMENT,
            source_ref=ref, user_id=user_id, auto_post=True)
        return {"year": year, "net_income": str(net), "entry": entry}
