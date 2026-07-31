# app/services/finance_ops_service.py
from __future__ import annotations

"""
Finance operations that make the accounting module self-sufficient:

* Accounts Payable — vendors, vendor bills and bill payments, each movement
  double-entry posted (bill: Dr expense / Cr Accounts Payable; payment:
  Dr Accounts Payable / Cr cash), plus an AP ageing report.
* Fixed assets — register with straight-line monthly depreciation runs that
  post Dr Depreciation Expense / Cr Accumulated Depreciation, idempotent per
  asset per period.
* Budgets — per-account monthly budget lines and a budget-vs-actual report.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.core.enums import (
    AccountType,
    DepreciationMethod,
    FixedAssetStatus,
    JournalSourceType,
    VendorBillStatus,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    Account,
    BudgetLine,
    FixedAsset,
    Vendor,
    VendorBill,
    VendorBillPayment,
)
from app.services.accounting_service import AccountingService, _d


# ---------------------------------------------------------------------------
# System accounts (resolved or created on demand)
# ---------------------------------------------------------------------------
_SYSTEM_ACCOUNTS = {
    "AP": ("2100", "Accounts Payable", AccountType.LIABILITY),
    "ACC_DEP": ("1590", "Accumulated Depreciation", AccountType.ASSET),  # contra-asset
    "DEP_EXP": ("5900", "Depreciation Expense", AccountType.EXPENSE),
    "RETAINED": ("3900", "Retained Earnings", AccountType.EQUITY),
    "SALARY_EXP": ("5100", "Salaries & Wages Expense", AccountType.EXPENSE),
    "STAFF_ADV": ("1450", "Staff Salary Advances", AccountType.ASSET),
}


def get_or_create_system_account(db: Session, key: str) -> Account:
    code, name, acc_type = _SYSTEM_ACCOUNTS[key]
    acct = db.query(Account).filter(Account.code == code, Account.is_deleted.is_(False)).first()
    if acct is None:
        acct = db.query(Account).filter(Account.name == name, Account.is_deleted.is_(False)).first()
    if acct is None:
        acct = Account(code=code, name=name, account_type=acc_type,
                       description="Auto-created system account.")
        db.add(acct)
        db.flush()
    return acct


def _bill_read(b: VendorBill) -> dict:
    total, paid = _d(b.total_amount), _d(b.amount_paid)
    return {
        "id": b.id, "bill_no": b.bill_no,
        "vendor_id": b.vendor_id,
        "vendor_name": b.vendor.name if b.vendor else None,
        "bill_date": b.bill_date.isoformat(), "due_date": b.due_date.isoformat() if b.due_date else None,
        "description": b.description,
        "expense_account_id": b.expense_account_id,
        "expense_account": f"{b.expense_account.code} · {b.expense_account.name}" if b.expense_account else None,
        "total_amount": str(total), "amount_paid": str(paid),
        "balance_due": str(total - paid),
        "status": b.status.value if hasattr(b.status, "value") else b.status,
    }


class VendorService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounting = AccountingService(db)

    # ---- vendors ----
    def upsert_vendor(self, *, vendor_id: Optional[int] = None, **fields) -> dict:
        if vendor_id:
            v = self.db.query(Vendor).filter(Vendor.id == vendor_id).first()
            if v is None:
                raise NotFoundError(message="Vendor not found.")
        else:
            if not (fields.get("name") or "").strip():
                raise BadRequestError(message="Vendor name is required.")
            v = Vendor(name=fields["name"].strip())
            self.db.add(v)
        for k in ("name", "contact_person", "email", "phone", "tax_id", "address", "is_active"):
            if k in fields and fields[k] is not None:
                setattr(v, k, fields[k])
        self.db.commit()
        self.db.refresh(v)
        return self._vendor_read(v)

    def _vendor_read(self, v: Vendor) -> dict:
        return {"id": v.id, "name": v.name, "contact_person": v.contact_person,
                "email": v.email, "phone": v.phone, "tax_id": v.tax_id,
                "address": v.address, "is_active": v.is_active}

    def list_vendors(self, *, search: Optional[str] = None) -> list[dict]:
        q = self.db.query(Vendor).filter(Vendor.is_deleted.is_(False))
        if search:
            q = q.filter(Vendor.name.ilike(f"%{search.strip()}%"))
        return [self._vendor_read(v) for v in q.order_by(Vendor.name.asc()).all()]

    # ---- bills ----
    def create_bill(self, *, vendor_id: int, bill_date: date, total_amount,
                    expense_account_id: int, due_date: Optional[date] = None,
                    description: Optional[str] = None, bill_no: Optional[str] = None,
                    user_id: Optional[int] = None) -> dict:
        vendor = self.db.query(Vendor).filter(Vendor.id == vendor_id, Vendor.is_deleted.is_(False)).first()
        if vendor is None:
            raise NotFoundError(message="Vendor not found.")
        amount = _d(total_amount)
        if amount <= 0:
            raise BadRequestError(message="Bill amount must be greater than zero.")
        expense = self.db.query(Account).filter(Account.id == expense_account_id).first()
        if expense is None:
            raise BadRequestError(message="Unknown expense account.")

        bill = VendorBill(
            vendor_id=vendor_id,
            bill_no=(bill_no or f"BILL-{bill_date.strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"),
            bill_date=bill_date, due_date=due_date, description=description,
            expense_account_id=expense_account_id, total_amount=amount,
            status=VendorBillStatus.OPEN,
        )
        self.db.add(bill)
        self.db.flush()

        ap = get_or_create_system_account(self.db, "AP")
        self.accounting.create_entry(
            entry_date=bill_date,
            memo=f"Vendor bill {bill.bill_no} — {vendor.name}",
            lines=[
                {"account_id": expense.id, "debit": amount, "credit": 0,
                 "description": description or f"Bill from {vendor.name}"},
                {"account_id": ap.id, "debit": 0, "credit": amount,
                 "description": f"Payable to {vendor.name}"},
            ],
            source_type=JournalSourceType.ADJUSTMENT,
            source_ref=f"vendor_bill:{bill.id}", user_id=user_id, auto_post=True,
        )
        self.db.commit()
        self.db.refresh(bill)
        return _bill_read(bill)

    def list_bills(self, *, status: Optional[str] = None, vendor_id: Optional[int] = None) -> list[dict]:
        q = (self.db.query(VendorBill)
             .options(joinedload(VendorBill.vendor), joinedload(VendorBill.expense_account))
             .filter(VendorBill.is_deleted.is_(False)))
        if status:
            try:
                q = q.filter(VendorBill.status == VendorBillStatus(status.strip().upper()))
            except Exception:
                pass
        if vendor_id:
            q = q.filter(VendorBill.vendor_id == vendor_id)
        return [_bill_read(b) for b in q.order_by(VendorBill.bill_date.desc(), VendorBill.id.desc()).all()]

    def pay_bill(self, *, bill_id: int, amount, paid_at: date,
                 payment_method: Optional[str] = None, reference: Optional[str] = None,
                 user_id: Optional[int] = None) -> dict:
        bill = (self.db.query(VendorBill)
                .options(joinedload(VendorBill.vendor))
                .filter(VendorBill.id == bill_id, VendorBill.is_deleted.is_(False)).first())
        if bill is None:
            raise NotFoundError(message="Bill not found.")
        if bill.status in (VendorBillStatus.PAID, VendorBillStatus.CANCELLED):
            raise BadRequestError(message=f"Bill is already {bill.status.value.lower()}.")
        pay = _d(amount)
        balance = _d(bill.total_amount) - _d(bill.amount_paid)
        if pay <= 0:
            raise BadRequestError(message="Payment must be greater than zero.")
        if pay > balance:
            raise BadRequestError(message=f"Payment exceeds the outstanding balance ({balance}).")

        payment = VendorBillPayment(
            vendor_bill_id=bill.id, amount=pay, paid_at=paid_at,
            payment_method=payment_method, reference=reference,
        )
        self.db.add(payment)
        self.db.flush()

        from app.utils.charge_capture import resolve_cash_account
        ap = get_or_create_system_account(self.db, "AP")
        cash = resolve_cash_account(self.db, payment_method=payment_method)
        if cash is None:
            raise BadRequestError(message="No cash/bank account is configured.")
        self.accounting.create_entry(
            entry_date=paid_at,
            memo=f"Payment on {bill.bill_no} — {bill.vendor.name if bill.vendor else ''}".strip(),
            lines=[
                {"account_id": ap.id, "debit": pay, "credit": 0,
                 "description": f"Settle {bill.bill_no}"},
                {"account_id": cash.id, "debit": 0, "credit": pay,
                 "description": reference or payment_method or "Bill payment"},
            ],
            source_type=JournalSourceType.ADJUSTMENT,
            source_ref=f"vendor_bill_payment:{payment.id}", user_id=user_id, auto_post=True,
        )

        bill.amount_paid = _d(bill.amount_paid) + pay
        bill.status = (VendorBillStatus.PAID if bill.amount_paid >= _d(bill.total_amount)
                       else VendorBillStatus.PARTIALLY_PAID)
        self.db.commit()
        self.db.refresh(bill)
        return _bill_read(bill)

    # ---- AP ageing ----
    def ap_aging(self, *, as_of: Optional[date] = None) -> dict:
        as_of = as_of or date.today()
        bills = (self.db.query(VendorBill)
                 .options(joinedload(VendorBill.vendor))
                 .filter(VendorBill.is_deleted.is_(False),
                         VendorBill.status.in_([VendorBillStatus.OPEN, VendorBillStatus.PARTIALLY_PAID]))
                 .all())
        buckets = {"current": Decimal("0"), "d1_30": Decimal("0"), "d31_60": Decimal("0"),
                   "d61_90": Decimal("0"), "d90_plus": Decimal("0")}
        rows = []
        for b in bills:
            due = b.due_date or b.bill_date
            overdue = (as_of - due).days
            balance = _d(b.total_amount) - _d(b.amount_paid)
            if balance <= 0:
                continue
            key = ("current" if overdue <= 0 else "d1_30" if overdue <= 30
                   else "d31_60" if overdue <= 60 else "d61_90" if overdue <= 90 else "d90_plus")
            buckets[key] += balance
            rows.append({"bill_no": b.bill_no, "vendor": b.vendor.name if b.vendor else None,
                         "due_date": due.isoformat(), "days_overdue": max(0, overdue),
                         "balance": str(balance), "bucket": key})
        return {"as_of": as_of.isoformat(),
                "buckets": {k: str(v) for k, v in buckets.items()},
                "total_outstanding": str(sum(buckets.values())), "items": rows}


class FixedAssetService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounting = AccountingService(db)

    def _read(self, a: FixedAsset) -> dict:
        cost, acc = _d(a.cost), _d(a.accumulated_depreciation)
        return {"id": a.id, "code": a.code, "name": a.name, "category": a.category,
                "acquisition_date": a.acquisition_date.isoformat(),
                "cost": str(cost), "salvage_value": str(_d(a.salvage_value)),
                "useful_life_months": a.useful_life_months,
                "accumulated_depreciation": str(acc),
                "net_book_value": str(cost - acc),
                "last_depreciated_period": a.last_depreciated_period,
                "status": a.status.value if hasattr(a.status, "value") else a.status}

    def create_asset(self, *, name: str, acquisition_date: date, cost, useful_life_months: int,
                     salvage_value=0, category: Optional[str] = None,
                     code: Optional[str] = None, user_id: Optional[int] = None,
                     book_acquisition: bool = False,
                     funding_account_id: Optional[int] = None) -> dict:
        c = _d(cost)
        if c <= 0 or useful_life_months <= 0:
            raise BadRequestError(message="Cost and useful life must be greater than zero.")
        if _d(salvage_value) >= c:
            raise BadRequestError(message="Salvage value must be less than cost.")
        asset = FixedAsset(
            code=code or f"FA-{uuid.uuid4().hex[:8].upper()}",
            name=name.strip(), category=category,
            acquisition_date=acquisition_date, cost=c,
            salvage_value=_d(salvage_value), useful_life_months=useful_life_months,
            method=DepreciationMethod.STRAIGHT_LINE,
        )
        self.db.add(asset)
        self.db.flush()

        # Optionally book the acquisition (Dr asset / Cr cash-or-payable).
        if book_acquisition and funding_account_id:
            asset_acct = self.db.query(Account).filter(
                Account.account_type == AccountType.ASSET,
                Account.is_deleted.is_(False)).order_by(Account.code).first()
            funding = self.db.query(Account).filter(Account.id == funding_account_id).first()
            if asset_acct and funding:
                self.accounting.create_entry(
                    entry_date=acquisition_date, memo=f"Acquire asset {asset.code} — {asset.name}",
                    lines=[
                        {"account_id": asset_acct.id, "debit": c, "credit": 0, "description": asset.name},
                        {"account_id": funding.id, "debit": 0, "credit": c, "description": "Asset acquisition"},
                    ],
                    source_type=JournalSourceType.ADJUSTMENT,
                    source_ref=f"fixed_asset_acquire:{asset.id}", user_id=user_id, auto_post=True)
        self.db.commit()
        self.db.refresh(asset)
        return self._read(asset)

    def list_assets(self) -> list[dict]:
        rows = self.db.query(FixedAsset).filter(FixedAsset.is_deleted.is_(False)) \
            .order_by(FixedAsset.code.asc()).all()
        return [self._read(a) for a in rows]

    def monthly_depreciation(self, a: FixedAsset) -> Decimal:
        base = _d(a.cost) - _d(a.salvage_value)
        if a.useful_life_months <= 0:
            return Decimal("0.00")
        return (base / Decimal(a.useful_life_months)).quantize(Decimal("0.01"))

    def run_depreciation(self, *, period_code: Optional[str] = None,
                         user_id: Optional[int] = None) -> dict:
        """Post one month of straight-line depreciation for every active asset
        (idempotent per asset+period; capped at depreciable base)."""
        today = date.today()
        period_code = period_code or f"{today.year:04d}-{today.month:02d}"
        try:
            y, m = (int(x) for x in period_code.split("-"))
            entry_date = (date(y, m + 1, 1) if m < 12 else date(y + 1, 1, 1)) - timedelta(days=1)
        except Exception:
            raise BadRequestError(message="period_code must look like YYYY-MM.")

        dep_exp = get_or_create_system_account(self.db, "DEP_EXP")
        acc_dep = get_or_create_system_account(self.db, "ACC_DEP")

        posted, skipped = [], 0
        assets = self.db.query(FixedAsset).filter(
            FixedAsset.is_deleted.is_(False),
            FixedAsset.status == FixedAssetStatus.ACTIVE).all()
        for a in assets:
            if a.last_depreciated_period and a.last_depreciated_period >= period_code:
                skipped += 1
                continue
            if a.acquisition_date > entry_date:
                continue
            base_remaining = (_d(a.cost) - _d(a.salvage_value)) - _d(a.accumulated_depreciation)
            if base_remaining <= 0:
                a.status = FixedAssetStatus.FULLY_DEPRECIATED
                continue
            amount = min(self.monthly_depreciation(a), base_remaining)
            if amount <= 0:
                continue
            self.accounting.create_entry(
                entry_date=entry_date,
                memo=f"Depreciation {period_code} — {a.code} {a.name}",
                lines=[
                    {"account_id": dep_exp.id, "debit": amount, "credit": 0, "description": a.name},
                    {"account_id": acc_dep.id, "debit": 0, "credit": amount, "description": "Accumulated depreciation"},
                ],
                source_type=JournalSourceType.ADJUSTMENT,
                source_ref=f"depreciation:{a.id}:{period_code}", user_id=user_id, auto_post=True)
            a.accumulated_depreciation = _d(a.accumulated_depreciation) + amount
            a.last_depreciated_period = period_code
            if _d(a.accumulated_depreciation) >= (_d(a.cost) - _d(a.salvage_value)):
                a.status = FixedAssetStatus.FULLY_DEPRECIATED
            posted.append(a.code)
        self.db.commit()
        return {"period": period_code, "posted": len(posted), "skipped_current": skipped, "assets": posted}


class BudgetService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert(self, *, account_id: int, period_code: str, amount) -> dict:
        acct = self.db.query(Account).filter(Account.id == account_id).first()
        if acct is None:
            raise NotFoundError(message="Account not found.")
        line = self.db.query(BudgetLine).filter(
            BudgetLine.account_id == account_id,
            BudgetLine.period_code == period_code,
            BudgetLine.is_deleted.is_(False)).first()
        if line is None:
            line = BudgetLine(account_id=account_id, period_code=period_code, amount=_d(amount))
            self.db.add(line)
        else:
            line.amount = _d(amount)
        self.db.commit()
        self.db.refresh(line)
        return {"id": line.id, "account_id": account_id, "period_code": period_code,
                "amount": str(line.amount)}

    def budget_vs_actual(self, *, date_from: date, date_to: date) -> dict:
        """Compare budgets against actual posted activity for REVENUE/EXPENSE
        accounts across the covered periods."""
        acc = AccountingService(self.db)
        actual_rows = {r["account_id"]: r for r in acc._balances_by_account(
            date_from=date_from, date_to=date_to)}

        # periods covered
        periods = []
        y, m = date_from.year, date_from.month
        while (y, m) <= (date_to.year, date_to.month):
            periods.append(f"{y:04d}-{m:02d}")
            m += 1
            if m > 12:
                m, y = 1, y + 1

        budget_rows = self.db.query(BudgetLine).options(joinedload(BudgetLine.account)).filter(
            BudgetLine.period_code.in_(periods), BudgetLine.is_deleted.is_(False)).all()
        budget_by_account: dict[int, Decimal] = {}
        for b in budget_rows:
            budget_by_account[b.account_id] = budget_by_account.get(b.account_id, Decimal("0")) + _d(b.amount)

        account_ids = set(budget_by_account) | set(actual_rows)
        accounts = {a.id: a for a in self.db.query(Account).filter(Account.id.in_(account_ids)).all()} if account_ids else {}
        items = []
        for aid in sorted(account_ids, key=lambda i: accounts[i].code if i in accounts else ""):
            a = accounts.get(aid)
            if a is None or a.account_type not in (AccountType.REVENUE, AccountType.EXPENSE):
                continue
            actual = actual_rows.get(aid)
            if actual:
                amt = (actual["credit"] - actual["debit"]) if a.account_type == AccountType.REVENUE \
                    else (actual["debit"] - actual["credit"])
            else:
                amt = Decimal("0")
            budget = budget_by_account.get(aid, Decimal("0"))
            items.append({
                "account_id": aid, "code": a.code, "name": a.name, "type": a.account_type.value,
                "budget": str(budget), "actual": str(amt), "variance": str(budget - amt),
            })
        return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
                "periods": periods, "items": items}
