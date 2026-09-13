# app/services/banking_service.py
from __future__ import annotations

"""
Bank & cash management: bank accounts (each mirrored by a CoA asset account),
deposits of cash-point takings, inter-account transfers, CSV bank-statement
import and reconciliation sessions with auto-matching.
"""

import csv
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import (
    AccountType,
    BankReconciliationStatus,
    JournalEntryStatus,
    JournalSourceType,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import Account, JournalEntry, JournalEntryLine
from app.models.finance_models import (
    BankAccount,
    BankReconciliation,
    BankStatementImport,
    BankStatementLine,
)
from app.services.accounting_service import AccountingService, _d
from app.services.system_accounts_service import audit, resolve_system_account


def _mask(num: Optional[str]) -> Optional[str]:
    if not num:
        return num
    digits = str(num)
    return ("*" * max(0, len(digits) - 4)) + digits[-4:]


class BankingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounting = AccountingService(db)

    # ---------------- bank accounts ----------------

    def _get(self, bank_account_id: int) -> BankAccount:
        b = (self.db.query(BankAccount)
             .filter(BankAccount.id == bank_account_id,
                     BankAccount.is_deleted.is_(False)).first())
        if b is None:
            raise NotFoundError("Bank account not found.")
        return b

    def _read(self, b: BankAccount, *, with_balance: bool = False) -> dict:
        out = {
            "id": b.id, "name": b.name, "bank_name": b.bank_name,
            "account_number_masked": _mask(b.account_number),
            "account_id": b.account_id,
            "ledger_code": b.account.code if b.account else None,
            "is_default": b.is_default, "is_active": b.is_active,
            "notes": b.notes,
        }
        if with_balance:
            out["balance"] = str(self.ledger_balance(b))
        return out

    def ledger_balance(self, b: BankAccount, *, as_of: Optional[date] = None) -> Decimal:
        q = (self.db.query(
                func.coalesce(func.sum(JournalEntryLine.debit), 0),
                func.coalesce(func.sum(JournalEntryLine.credit), 0))
             .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
             .filter(JournalEntryLine.account_id == b.account_id,
                     JournalEntry.status == JournalEntryStatus.POSTED,
                     JournalEntry.is_deleted.is_(False)))
        if as_of:
            q = q.filter(JournalEntry.entry_date <= as_of)
        dr, cr = q.first()
        return _d(dr) - _d(cr)

    def list_accounts(self, *, with_balance: bool = True) -> list[dict]:
        rows = (self.db.query(BankAccount)
                .filter(BankAccount.is_deleted.is_(False))
                .order_by(BankAccount.id).all())
        return [self._read(b, with_balance=with_balance) for b in rows]

    def create_account(self, *, name: str, bank_name: Optional[str] = None,
                       account_number: Optional[str] = None,
                       is_default: bool = False,
                       ledger_code: Optional[str] = None,
                       notes: Optional[str] = None) -> dict:
        # Mirror ledger account (create if a code is not supplied/found).
        acct = None
        if ledger_code:
            acct = (self.db.query(Account)
                    .filter(Account.code == ledger_code,
                            Account.is_deleted.is_(False)).first())
        if acct is None:
            base = 1040
            code = ledger_code
            if not code:
                while self.db.query(Account).filter(Account.code == str(base)).first() is not None:
                    base += 1
                code = str(base)
            acct = Account(code=code, name=f"Bank — {name}",
                           account_type=AccountType.ASSET,
                           cash_flow_category="NONE", is_system=True,
                           description="Auto-created for bank account.")
            self.db.add(acct)
            self.db.flush()
        if is_default:
            self.db.query(BankAccount).filter(
                BankAccount.is_deleted.is_(False)).update({"is_default": False})
        b = BankAccount(name=name, bank_name=bank_name,
                        account_number=account_number, account_id=acct.id,
                        is_default=is_default, notes=notes)
        self.db.add(b)
        self.db.flush()
        self.db.commit()
        return self._read(b)

    def update_account(self, bank_account_id: int, **fields) -> dict:
        b = self._get(bank_account_id)
        if fields.get("is_default"):
            self.db.query(BankAccount).filter(
                BankAccount.is_deleted.is_(False)).update({"is_default": False})
        for k in ("name", "bank_name", "account_number", "is_default", "is_active", "notes"):
            if k in fields and fields[k] is not None:
                setattr(b, k, fields[k])
        self.db.commit()
        return self._read(b)

    def default_account(self) -> Optional[BankAccount]:
        return (self.db.query(BankAccount)
                .filter(BankAccount.is_deleted.is_(False),
                        BankAccount.is_active.is_(True))
                .order_by(BankAccount.is_default.desc(), BankAccount.id.asc())
                .first())

    # ---------------- deposits & transfers ----------------

    def record_deposit(self, *, bank_account_id: int, amount, deposit_date: date,
                       reference: Optional[str] = None,
                       user_id: Optional[int] = None) -> dict:
        """Bank deposit of cash-point takings: Dr Bank / Cr Undeposited Funds."""
        b = self._get(bank_account_id)
        amount = _d(amount)
        if amount <= 0:
            raise BadRequestError("Amount must be positive.")
        undeposited = resolve_system_account(self.db, "UNDEPOSITED_FUNDS")
        entry = self.accounting.create_entry(
            entry_date=deposit_date,
            memo=f"Cash deposit to {b.name}" + (f" ({reference})" if reference else ""),
            lines=[
                {"account_id": b.account_id, "debit": amount, "credit": 0,
                 "description": f"Deposit {reference or ''}".strip()},
                {"account_id": undeposited.id, "debit": 0, "credit": amount,
                 "description": "Cash takings banked"},
            ],
            source_type=JournalSourceType.BANK, user_id=user_id, auto_post=True)
        audit(self.db, action="BANK_DEPOSIT", entity_type="bank_account",
              entity_id=b.id, user_id=user_id, summary=f"Deposit {amount} to {b.name}")
        self.db.commit()
        return entry

    def record_transfer(self, *, from_bank_account_id: int, to_bank_account_id: int,
                        amount, transfer_date: date,
                        reference: Optional[str] = None,
                        user_id: Optional[int] = None) -> dict:
        if from_bank_account_id == to_bank_account_id:
            raise BadRequestError("Source and destination accounts must differ.")
        src, dst = self._get(from_bank_account_id), self._get(to_bank_account_id)
        amount = _d(amount)
        if amount <= 0:
            raise BadRequestError("Amount must be positive.")
        entry = self.accounting.create_entry(
            entry_date=transfer_date,
            memo=f"Transfer {src.name} -> {dst.name}" + (f" ({reference})" if reference else ""),
            lines=[
                {"account_id": dst.account_id, "debit": amount, "credit": 0,
                 "description": f"Transfer in from {src.name}"},
                {"account_id": src.account_id, "debit": 0, "credit": amount,
                 "description": f"Transfer out to {dst.name}"},
            ],
            source_type=JournalSourceType.BANK, user_id=user_id, auto_post=True)
        audit(self.db, action="BANK_TRANSFER", entity_type="bank_account",
              entity_id=src.id, user_id=user_id,
              summary=f"Transfer {amount} {src.name} -> {dst.name}")
        self.db.commit()
        return entry

    # ---------------- statement import ----------------

    def import_statement_csv(self, *, bank_account_id: int, content: bytes,
                             file_name: Optional[str] = None,
                             user_id: Optional[int] = None) -> dict:
        """CSV columns (case-insensitive): date, description, reference,
        debit, credit — or a single signed 'amount' column."""
        b = self._get(bank_account_id)
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise BadRequestError("Empty CSV file.")
        headers = {h.strip().lower(): h for h in reader.fieldnames}
        if "date" not in headers:
            raise BadRequestError("CSV needs a 'date' column.")
        has_amount = "amount" in headers
        if not has_amount and ("debit" not in headers and "credit" not in headers):
            raise BadRequestError("CSV needs 'debit'/'credit' (or a signed 'amount') columns.")

        imp = BankStatementImport(bank_account_id=b.id, file_name=file_name,
                                  imported_by_user_id=user_id)
        self.db.add(imp)
        self.db.flush()
        errors, count = [], 0
        min_d = max_d = None
        for i, row in enumerate(reader, start=2):
            raw_date = (row.get(headers["date"], "") or "").strip()
            parsed = None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
                try:
                    parsed = datetime.strptime(raw_date, fmt).date()
                    break
                except ValueError:
                    continue
            if parsed is None:
                errors.append({"row": i, "error": f"Unparseable date '{raw_date}'."})
                continue
            def _num(key):
                v = (row.get(headers.get(key, ""), "") or "").strip().replace(",", "")
                try:
                    return _d(v) if v else Decimal("0")
                except Exception:
                    return Decimal("0")
            if has_amount:
                amt = _num("amount")
                debit = amt if amt > 0 else Decimal("0")
                credit = -amt if amt < 0 else Decimal("0")
            else:
                debit, credit = _num("debit"), _num("credit")
            if debit == 0 and credit == 0:
                continue
            self.db.add(BankStatementLine(
                import_id=imp.id, line_date=parsed,
                description=(row.get(headers.get("description", ""), "") or "").strip() or None,
                reference=(row.get(headers.get("reference", ""), "") or "").strip() or None,
                debit=debit, credit=credit))
            count += 1
            min_d = parsed if (min_d is None or parsed < min_d) else min_d
            max_d = parsed if (max_d is None or parsed > max_d) else max_d
        imp.line_count = count
        imp.statement_from, imp.statement_to = min_d, max_d
        self.db.commit()
        return {"import_id": imp.id, "lines": count, "errors": errors,
                "statement_from": min_d.isoformat() if min_d else None,
                "statement_to": max_d.isoformat() if max_d else None}

    # ---------------- reconciliation ----------------

    def _get_rec(self, rec_id: int) -> BankReconciliation:
        r = (self.db.query(BankReconciliation)
             .filter(BankReconciliation.id == rec_id,
                     BankReconciliation.is_deleted.is_(False)).first())
        if r is None:
            raise NotFoundError("Reconciliation not found.")
        return r

    def start_reconciliation(self, *, bank_account_id: int, period_from: date,
                             period_to: date, statement_closing_balance=None) -> dict:
        b = self._get(bank_account_id)
        rec = BankReconciliation(
            bank_account_id=b.id, period_from=period_from, period_to=period_to,
            statement_closing_balance=_d(statement_closing_balance)
            if statement_closing_balance is not None else None,
            book_closing_balance=self.ledger_balance(b, as_of=period_to))
        self.db.add(rec)
        self.db.flush()
        auto = self.auto_match(rec.id)
        self.db.commit()
        return {**self.reconciliation_report(rec.id), "auto_matched": auto["matched"]}

    def _unmatched_statement_lines(self, rec: BankReconciliation):
        return (self.db.query(BankStatementLine)
                .join(BankStatementImport,
                      BankStatementImport.id == BankStatementLine.import_id)
                .filter(BankStatementImport.bank_account_id == rec.bank_account_id,
                        BankStatementLine.is_deleted.is_(False),
                        BankStatementLine.matched_journal_line_id.is_(None),
                        BankStatementLine.line_date >= rec.period_from,
                        BankStatementLine.line_date <= rec.period_to).all())

    def _candidate_ledger_lines(self, rec: BankReconciliation):
        b = self._get(rec.bank_account_id)
        matched_ids = {r[0] for r in self.db.query(
            BankStatementLine.matched_journal_line_id)
            .filter(BankStatementLine.matched_journal_line_id.isnot(None)).all()}
        q = (self.db.query(JournalEntryLine, JournalEntry)
             .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
             .filter(JournalEntryLine.account_id == b.account_id,
                     JournalEntry.status == JournalEntryStatus.POSTED,
                     JournalEntry.is_deleted.is_(False),
                     JournalEntry.entry_date <= rec.period_to))
        return [(l, e) for l, e in q.all() if l.id not in matched_ids]

    def auto_match(self, rec_id: int) -> dict:
        """Match statement lines to ledger lines by amount + date proximity
        (±5 days), tightest date distance first."""
        rec = self._get_rec(rec_id)
        stmt_lines = self._unmatched_statement_lines(rec)
        ledger = self._candidate_ledger_lines(rec)
        used: set[int] = set()
        matched = 0
        for s in stmt_lines:
            s_amt = _d(s.debit) - _d(s.credit)  # statement debit == money into bank
            best, best_gap = None, None
            for l, e in ledger:
                if l.id in used:
                    continue
                l_amt = _d(l.debit) - _d(l.credit)
                if l_amt != s_amt or l_amt == 0:
                    continue
                gap = abs((e.entry_date - s.line_date).days)
                if gap <= 5 and (best_gap is None or gap < best_gap):
                    best, best_gap = l, gap
            if best is not None:
                s.matched_journal_line_id = best.id
                s.reconciliation_id = rec.id
                s.matched_at = datetime.now(timezone.utc)
                used.add(best.id)
                matched += 1
        self.db.flush()
        return {"matched": matched, "remaining": len(stmt_lines) - matched}

    def manual_match(self, rec_id: int, *, statement_line_id: int,
                     journal_line_id: Optional[int]) -> dict:
        rec = self._get_rec(rec_id)
        s = (self.db.query(BankStatementLine)
             .filter(BankStatementLine.id == statement_line_id).first())
        if s is None:
            raise NotFoundError("Statement line not found.")
        if journal_line_id is None:  # unmatch
            s.matched_journal_line_id = None
            s.reconciliation_id = None
            s.matched_at = None
        else:
            l = (self.db.query(JournalEntryLine)
                 .filter(JournalEntryLine.id == journal_line_id).first())
            if l is None:
                raise NotFoundError("Journal line not found.")
            s.matched_journal_line_id = l.id
            s.reconciliation_id = rec.id
            s.matched_at = datetime.now(timezone.utc)
        self.db.commit()
        return {"statement_line_id": s.id,
                "matched_journal_line_id": s.matched_journal_line_id}

    def add_adjustment(self, rec_id: int, *, kind: str, amount,
                       adj_date: Optional[date] = None,
                       description: Optional[str] = None,
                       user_id: Optional[int] = None) -> dict:
        """Create the book entry for a statement-only item (bank charge or
        interest) during reconciliation, then it can be matched."""
        rec = self._get_rec(rec_id)
        b = self._get(rec.bank_account_id)
        amount = _d(amount)
        if amount <= 0:
            raise BadRequestError("Amount must be positive.")
        adj_date = adj_date or rec.period_to
        if kind.upper() == "BANK_CHARGE":
            other = resolve_system_account(self.db, "BANK_CHARGES")
            lines = [
                {"account_id": other.id, "debit": amount, "credit": 0,
                 "description": description or "Bank charges"},
                {"account_id": b.account_id, "debit": 0, "credit": amount,
                 "description": "Bank charges"},
            ]
        elif kind.upper() == "INTEREST":
            other = resolve_system_account(self.db, "INTEREST_INCOME")
            lines = [
                {"account_id": b.account_id, "debit": amount, "credit": 0,
                 "description": description or "Bank interest"},
                {"account_id": other.id, "debit": 0, "credit": amount,
                 "description": "Interest income"},
            ]
        else:
            raise BadRequestError("kind must be BANK_CHARGE or INTEREST.")
        entry = self.accounting.create_entry(
            entry_date=adj_date, memo=description or f"Reconciliation adjustment ({kind})",
            lines=lines, source_type=JournalSourceType.BANK,
            user_id=user_id, auto_post=True)
        self.db.commit()
        return entry

    def reconciliation_report(self, rec_id: int) -> dict:
        rec = self._get_rec(rec_id)
        b = self._get(rec.bank_account_id)
        stmt_unmatched = self._unmatched_statement_lines(rec)
        ledger_all = self._candidate_ledger_lines(rec)
        ledger_unmatched = [
            (l, e) for l, e in ledger_all
            if e.entry_date >= rec.period_from]
        book = self.ledger_balance(b, as_of=rec.period_to)
        rec.book_closing_balance = book
        outstanding_stmt = sum((_d(s.debit) - _d(s.credit) for s in stmt_unmatched), Decimal("0"))
        outstanding_book = sum((_d(l.debit) - _d(l.credit) for l, _ in ledger_unmatched), Decimal("0"))
        return {
            "id": rec.id, "bank_account_id": b.id, "bank_account_name": b.name,
            "period_from": rec.period_from.isoformat(),
            "period_to": rec.period_to.isoformat(),
            "status": rec.status.value if hasattr(rec.status, "value") else rec.status,
            "book_closing_balance": str(book),
            "statement_closing_balance": str(_d(rec.statement_closing_balance))
                if rec.statement_closing_balance is not None else None,
            "difference": str(book - _d(rec.statement_closing_balance))
                if rec.statement_closing_balance is not None else None,
            "unmatched_statement_lines": [{
                "id": s.id, "date": s.line_date.isoformat(),
                "description": s.description, "reference": s.reference,
                "debit": str(_d(s.debit)), "credit": str(_d(s.credit)),
            } for s in stmt_unmatched],
            "unmatched_book_lines": [{
                "journal_line_id": l.id, "entry_no": e.entry_no,
                "date": e.entry_date.isoformat(), "memo": e.memo,
                "debit": str(_d(l.debit)), "credit": str(_d(l.credit)),
            } for l, e in ledger_unmatched],
            "outstanding_statement_total": str(outstanding_stmt),
            "outstanding_book_total": str(outstanding_book),
        }

    def complete_reconciliation(self, rec_id: int, *,
                                user_id: Optional[int] = None) -> dict:
        rec = self._get_rec(rec_id)
        if rec.status != BankReconciliationStatus.IN_PROGRESS:
            raise BadRequestError("Reconciliation is not in progress.")
        rec.status = BankReconciliationStatus.COMPLETED
        rec.completed_at = datetime.now(timezone.utc)
        rec.completed_by_user_id = user_id
        audit(self.db, action="BANK_RECONCILED", entity_type="bank_reconciliation",
              entity_id=rec.id, user_id=user_id,
              summary=f"Reconciliation completed for account {rec.bank_account_id}")
        self.db.commit()
        return self.reconciliation_report(rec.id)

    def list_reconciliations(self, *, bank_account_id: Optional[int] = None) -> list[dict]:
        q = (self.db.query(BankReconciliation)
             .filter(BankReconciliation.is_deleted.is_(False)))
        if bank_account_id:
            q = q.filter(BankReconciliation.bank_account_id == bank_account_id)
        return [{
            "id": r.id, "bank_account_id": r.bank_account_id,
            "period_from": r.period_from.isoformat(),
            "period_to": r.period_to.isoformat(),
            "status": r.status.value if hasattr(r.status, "value") else r.status,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        } for r in q.order_by(BankReconciliation.id.desc()).all()]
