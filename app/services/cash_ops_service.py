# app/services/cash_ops_service.py
from __future__ import annotations

"""
Petty cash (imprest floats, expense vouchers, replenishment) and cashier
sessions (open shift -> take payments -> counted close with over/short
posting and a Z-report).
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import (
    AccountType,
    CashierSessionStatus,
    JournalSourceType,
    PaymentStatus,
    PettyCashVoucherStatus,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import Account, BillingPayment, Payment
from app.models.finance_models import CashierSession, PettyCashFloat, PettyCashVoucher
from app.services.accounting_service import AccountingService, _d
from app.services.system_accounts_service import (
    audit,
    next_document_no,
    resolve_system_account,
)


class PettyCashService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounting = AccountingService(db)

    def _get_float(self, float_id: int) -> PettyCashFloat:
        f = (self.db.query(PettyCashFloat)
             .filter(PettyCashFloat.id == float_id,
                     PettyCashFloat.is_deleted.is_(False)).first())
        if f is None:
            raise NotFoundError("Petty cash float not found.")
        return f

    def _float_read(self, f: PettyCashFloat) -> dict:
        spent = _d(self.db.query(func.coalesce(func.sum(PettyCashVoucher.amount), 0))
                   .filter(PettyCashVoucher.float_id == f.id,
                           PettyCashVoucher.is_deleted.is_(False),
                           PettyCashVoucher.status.in_([
                               PettyCashVoucherStatus.APPROVED,
                               PettyCashVoucherStatus.RETIRED])).scalar() or 0)
        return {"id": f.id, "name": f.name,
                "custodian_user_id": f.custodian_user_id,
                "account_id": f.account_id,
                "float_amount": str(_d(f.float_amount)),
                "unretired_spend": str(spent),
                "cash_at_hand": str(_d(f.float_amount) - spent),
                "is_active": f.is_active}

    def list_floats(self) -> list[dict]:
        return [self._float_read(f) for f in
                self.db.query(PettyCashFloat)
                .filter(PettyCashFloat.is_deleted.is_(False)).all()]

    def create_float(self, *, name: str, custodian_user_id: Optional[int] = None) -> dict:
        acct = resolve_system_account(self.db, "PETTY_CASH")
        f = PettyCashFloat(name=name, custodian_user_id=custodian_user_id,
                           account_id=acct.id, float_amount=Decimal("0"))
        self.db.add(f)
        self.db.flush()
        self.db.commit()
        return self._float_read(f)

    def top_up(self, float_id: int, *, amount, bank_account_id: Optional[int] = None,
               top_up_date: Optional[date] = None,
               user_id: Optional[int] = None) -> dict:
        from app.services.banking_service import BankingService
        f = self._get_float(float_id)
        amount = _d(amount)
        if amount <= 0:
            raise BadRequestError("Amount must be positive.")
        banking = BankingService(self.db)
        bank = (banking._get(bank_account_id) if bank_account_id
                else banking.default_account())
        if bank is None:
            raise BadRequestError("No bank account configured to fund the float.")
        self.accounting.create_entry(
            entry_date=top_up_date or date.today(),
            memo=f"Petty cash top-up — {f.name}",
            lines=[
                {"account_id": f.account_id, "debit": amount, "credit": 0,
                 "description": f"Top-up {f.name}"},
                {"account_id": bank.account_id, "debit": 0, "credit": amount,
                 "description": "Petty cash funding"},
            ],
            source_type=JournalSourceType.PETTY_CASH, user_id=user_id, auto_post=True)
        f.float_amount = _d(f.float_amount) + amount
        audit(self.db, action="PETTY_CASH_TOPUP", entity_type="petty_cash_float",
              entity_id=f.id, user_id=user_id, summary=f"Top-up {amount}")
        self.db.commit()
        return self._float_read(f)

    def create_voucher(self, float_id: int, *, amount, description: str,
                       expense_account_id: Optional[int] = None,
                       cost_center_id: Optional[int] = None,
                       receipt_url: Optional[str] = None,
                       spent_at: Optional[date] = None,
                       user_id: Optional[int] = None) -> dict:
        f = self._get_float(float_id)
        amount = _d(amount)
        if amount <= 0:
            raise BadRequestError("Amount must be positive.")
        if expense_account_id is None:
            expense_account_id = resolve_system_account(self.db, "BANK_CHARGES").id  # placeholder acct
        acct = (self.db.query(Account)
                .filter(Account.id == expense_account_id,
                        Account.is_deleted.is_(False)).first())
        if acct is None or acct.account_type not in (AccountType.EXPENSE, AccountType.ASSET):
            raise BadRequestError("expense_account_id must be an expense (or asset) account.")
        v = PettyCashVoucher(
            float_id=f.id, voucher_no=next_document_no(self.db, "PC_VOUCHER"),
            expense_account_id=acct.id, cost_center_id=cost_center_id,
            amount=amount, description=description, receipt_url=receipt_url,
            requested_by_user_id=user_id, spent_at=spent_at or date.today())
        self.db.add(v)
        self.db.flush()
        self.db.commit()
        return self._voucher_read(v)

    def _voucher_read(self, v: PettyCashVoucher) -> dict:
        return {"id": v.id, "float_id": v.float_id, "voucher_no": v.voucher_no,
                "expense_account_id": v.expense_account_id,
                "expense_account": (f"{v.expense_account.code} · {v.expense_account.name}"
                                    if v.expense_account else None),
                "cost_center_id": v.cost_center_id,
                "amount": str(_d(v.amount)), "description": v.description,
                "receipt_url": v.receipt_url,
                "status": v.status.value if hasattr(v.status, "value") else v.status,
                "spent_at": v.spent_at.isoformat() if v.spent_at else None}

    def list_vouchers(self, *, float_id: Optional[int] = None,
                      status: Optional[str] = None) -> list[dict]:
        q = (self.db.query(PettyCashVoucher)
             .filter(PettyCashVoucher.is_deleted.is_(False)))
        if float_id:
            q = q.filter(PettyCashVoucher.float_id == float_id)
        if status:
            q = q.filter(PettyCashVoucher.status == PettyCashVoucherStatus(status))
        return [self._voucher_read(v) for v in q.order_by(PettyCashVoucher.id.desc()).all()]

    def decide_voucher(self, voucher_id: int, *, approve: bool,
                       user_id: Optional[int] = None) -> dict:
        v = (self.db.query(PettyCashVoucher)
             .filter(PettyCashVoucher.id == voucher_id,
                     PettyCashVoucher.is_deleted.is_(False)).first())
        if v is None:
            raise NotFoundError("Voucher not found.")
        if v.status != PettyCashVoucherStatus.PENDING:
            raise BadRequestError(f"Voucher is already {v.status.value}.")
        v.status = (PettyCashVoucherStatus.APPROVED if approve
                    else PettyCashVoucherStatus.REJECTED)
        v.approved_by_user_id = user_id
        audit(self.db, action="PETTY_CASH_VOUCHER_" + ("APPROVED" if approve else "REJECTED"),
              entity_type="petty_cash_voucher", entity_id=v.id, user_id=user_id,
              summary=f"{v.voucher_no}: {v.amount}")
        self.db.commit()
        return self._voucher_read(v)

    def retire(self, float_id: int, *, user_id: Optional[int] = None) -> dict:
        """Post every APPROVED voucher (Dr expense / Cr Petty Cash), mark them
        RETIRED, and report the replenishment amount due."""
        f = self._get_float(float_id)
        vouchers = (self.db.query(PettyCashVoucher)
                    .filter(PettyCashVoucher.float_id == f.id,
                            PettyCashVoucher.is_deleted.is_(False),
                            PettyCashVoucher.status == PettyCashVoucherStatus.APPROVED)
                    .all())
        if not vouchers:
            raise BadRequestError("No approved vouchers to retire.")
        total = Decimal("0")
        for v in vouchers:
            self.accounting.create_entry(
                entry_date=v.spent_at or date.today(),
                memo=f"Petty cash voucher {v.voucher_no}",
                lines=[
                    {"account_id": v.expense_account_id, "debit": _d(v.amount), "credit": 0,
                     "description": v.description,
                     "cost_center_id": v.cost_center_id},
                    {"account_id": f.account_id, "debit": 0, "credit": _d(v.amount),
                     "description": f"Petty cash spend {v.voucher_no}"},
                ],
                source_type=JournalSourceType.PETTY_CASH,
                source_ref=f"petty_cash_voucher:{v.id}",
                user_id=user_id, auto_post=True)
            v.status = PettyCashVoucherStatus.RETIRED
            total += _d(v.amount)
        f.float_amount = _d(f.float_amount) - total
        audit(self.db, action="PETTY_CASH_RETIRED", entity_type="petty_cash_float",
              entity_id=f.id, user_id=user_id,
              summary=f"Retired {len(vouchers)} vouchers, {total}")
        self.db.commit()
        return {"float": self._float_read(f), "retired_vouchers": len(vouchers),
                "replenishment_due": str(total)}


class CashierSessionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounting = AccountingService(db)

    def _get(self, session_id: int) -> CashierSession:
        s = (self.db.query(CashierSession)
             .filter(CashierSession.id == session_id,
                     CashierSession.is_deleted.is_(False)).first())
        if s is None:
            raise NotFoundError("Cashier session not found.")
        return s

    def open_session(self, *, cashier_user_id: int,
                     opening_float=0,
                     service_delivery_point_id: Optional[int] = None) -> dict:
        existing = (self.db.query(CashierSession)
                    .filter(CashierSession.cashier_user_id == cashier_user_id,
                            CashierSession.status == CashierSessionStatus.OPEN,
                            CashierSession.is_deleted.is_(False)).first())
        if existing is not None:
            raise BadRequestError("You already have an open cashier session.")
        s = CashierSession(cashier_user_id=cashier_user_id,
                           service_delivery_point_id=service_delivery_point_id,
                           opened_at=datetime.now(timezone.utc),
                           opening_float=_d(opening_float))
        self.db.add(s)
        self.db.flush()
        self.db.commit()
        return self.session_read(s)

    def current_for_user(self, cashier_user_id: int) -> Optional[dict]:
        s = (self.db.query(CashierSession)
             .filter(CashierSession.cashier_user_id == cashier_user_id,
                     CashierSession.status == CashierSessionStatus.OPEN,
                     CashierSession.is_deleted.is_(False)).first())
        return self.session_read(s) if s is not None else None

    def _session_payments(self, s: CashierSession) -> dict:
        """Collect payments attached to the session, grouped by method."""
        by_method: dict[str, Decimal] = {}
        total = Decimal("0")
        count = 0
        for model in (Payment, BillingPayment):
            rows = (self.db.query(model)
                    .filter(model.cashier_session_id == s.id,
                            model.is_deleted.is_(False),
                            model.payment_status == PaymentStatus.SUCCESSFUL).all())
            for p in rows:
                m = (p.payment_method or "CASH").upper()
                by_method[m] = by_method.get(m, Decimal("0")) + _d(p.amount)
                total += _d(p.amount)
                count += 1
        return {"by_method": by_method, "total": total, "count": count}

    def session_read(self, s: CashierSession) -> dict:
        pay = self._session_payments(s)
        cash_taken = pay["by_method"].get("CASH", Decimal("0"))
        return {
            "id": s.id, "cashier_user_id": s.cashier_user_id,
            "service_delivery_point_id": s.service_delivery_point_id,
            "status": s.status.value if hasattr(s.status, "value") else s.status,
            "opened_at": s.opened_at.isoformat() if s.opened_at else None,
            "closed_at": s.closed_at.isoformat() if s.closed_at else None,
            "opening_float": str(_d(s.opening_float)),
            "payments_count": pay["count"],
            "takings_by_method": {k: str(v) for k, v in pay["by_method"].items()},
            "takings_total": str(pay["total"]),
            "expected_cash": str(_d(s.opening_float) + cash_taken),
            "counted_cash": str(_d(s.counted_cash)) if s.counted_cash is not None else None,
            "variance": str(_d(s.variance)) if s.variance is not None else None,
            "notes": s.notes,
        }

    def attach_payment(self, *, session_id: int, payment_id: Optional[int] = None,
                       billing_payment_id: Optional[int] = None) -> dict:
        """Attach a taken payment to an open session (called from payment flows
        or the cash-point UI)."""
        s = self._get(session_id)
        if s.status != CashierSessionStatus.OPEN:
            raise BadRequestError("Session is closed.")
        if payment_id:
            p = self.db.query(Payment).filter(Payment.id == payment_id).first()
            if p is None:
                raise NotFoundError("Payment not found.")
            p.cashier_session_id = s.id
        elif billing_payment_id:
            p = (self.db.query(BillingPayment)
                 .filter(BillingPayment.id == billing_payment_id).first())
            if p is None:
                raise NotFoundError("Billing payment not found.")
            p.cashier_session_id = s.id
        else:
            raise BadRequestError("payment_id or billing_payment_id required.")
        self.db.commit()
        return self.session_read(s)

    def close_session(self, session_id: int, *, counted_cash,
                      notes: Optional[str] = None,
                      user_id: Optional[int] = None) -> dict:
        s = self._get(session_id)
        if s.status != CashierSessionStatus.OPEN:
            raise BadRequestError("Session is already closed.")
        pay = self._session_payments(s)
        cash_taken = pay["by_method"].get("CASH", Decimal("0"))
        expected = _d(s.opening_float) + cash_taken
        counted = _d(counted_cash)
        variance = counted - expected
        s.expected_cash = expected
        s.counted_cash = counted
        s.variance = variance
        s.status = CashierSessionStatus.CLOSED
        s.closed_at = datetime.now(timezone.utc)
        s.notes = notes

        # Over/short posting (only the variance; takings post via auto-post).
        if variance != 0:
            cash_acct = resolve_system_account(self.db, "CASH_ON_HAND")
            var_acct = resolve_system_account(self.db, "CASH_VARIANCE")
            if variance < 0:  # short
                lines = [
                    {"account_id": var_acct.id, "debit": -variance, "credit": 0,
                     "description": f"Cash short — session {s.id}"},
                    {"account_id": cash_acct.id, "debit": 0, "credit": -variance,
                     "description": f"Cash short — session {s.id}"},
                ]
            else:  # over
                lines = [
                    {"account_id": cash_acct.id, "debit": variance, "credit": 0,
                     "description": f"Cash over — session {s.id}"},
                    {"account_id": var_acct.id, "debit": 0, "credit": variance,
                     "description": f"Cash over — session {s.id}"},
                ]
            self.accounting.create_entry(
                entry_date=date.today(), memo=f"Cashier session {s.id} variance",
                lines=lines, source_type=JournalSourceType.CASHIER,
                source_ref=f"cashier_session_variance:{s.id}",
                user_id=user_id, auto_post=True)
        audit(self.db, action="CASHIER_SESSION_CLOSED", entity_type="cashier_session",
              entity_id=s.id, user_id=user_id,
              summary=f"Expected {expected}, counted {counted}, variance {variance}")
        self.db.commit()
        return self.session_read(s)

    def list_sessions(self, *, status: Optional[str] = None,
                      day: Optional[date] = None) -> list[dict]:
        q = (self.db.query(CashierSession)
             .filter(CashierSession.is_deleted.is_(False)))
        if status:
            q = q.filter(CashierSession.status == CashierSessionStatus(status))
        rows = q.order_by(CashierSession.id.desc()).limit(200).all()
        if day is not None:
            rows = [s for s in rows if s.opened_at and s.opened_at.date() == day]
        return [self.session_read(s) for s in rows]

    def daily_summary(self, *, day: Optional[date] = None) -> dict:
        day = day or date.today()
        rows = [s for s in
                self.db.query(CashierSession)
                .filter(CashierSession.is_deleted.is_(False)).all()
                if s.opened_at and s.opened_at.date() == day]
        total = Decimal("0")
        by_method: dict[str, Decimal] = {}
        sessions = []
        for s in rows:
            pay = self._session_payments(s)
            total += pay["total"]
            for k, v in pay["by_method"].items():
                by_method[k] = by_method.get(k, Decimal("0")) + v
            sessions.append(self.session_read(s))
        return {"date": day.isoformat(), "sessions": sessions,
                "takings_total": str(total),
                "takings_by_method": {k: str(v) for k, v in by_method.items()},
                "total_variance": str(sum((_d(s.variance or 0) for s in rows), Decimal("0")))}
