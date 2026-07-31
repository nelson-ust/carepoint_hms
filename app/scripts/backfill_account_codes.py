# app/scripts/backfill_account_codes.py
from __future__ import annotations

"""
Backfill: give every existing monetary record a ledger account.

Rows that predate the chart-of-accounts integration were left with a NULL
account. This script maps each such row to an **existing** account (it never
creates accounts) using the account *type* plus a small keyword hint, and falls
back to any existing account so nothing is left unmapped:

- reimbursement_request.account_id  -> an EXPENSE account (staff welfare / sundry)
- salary_advance.account_id         -> an ASSET account   (staff advance receivable)
- payroll_run.account_id            -> an EXPENSE account  (salaries & wages)
- billing_item.account_code/name    -> the line's billable-service account, else a REVENUE account
- billing_payment.account_code/name -> a cash/bank ASSET account chosen by payment method

Only rows whose account is currently NULL are touched, so the script is
idempotent — running it twice changes nothing the second time.

Usage (mirrors the other backfill scripts):

    # DRY RUN against the default database (reports what it would change)
    python -m app.scripts.backfill_account_codes

    # apply to a specific database URL
    python -m app.scripts.backfill_account_codes --db-url postgresql://... --apply

    # apply to every provisioned tenant
    python -m app.scripts.backfill_account_codes --all-tenants --apply

Without --apply the script is a DRY RUN: it computes and reports the counts but
rolls back instead of committing.
"""

import argparse
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.cryptography import decrypt_string
from app.core.database import SessionLocal, get_master_engine
from app.models.all_models import (
    Account,
    BillingItem,
    BillingPayment,
    PayrollRun,
    ReimbursementRequest,
    SalaryAdvance,
    Tenant,
)


# --------------------------------------------------------------------------
# Account selection (existing accounts only — never creates)
# --------------------------------------------------------------------------

def _type_val(a: Account) -> str:
    v = a.account_type
    return v.value if hasattr(v, "value") else str(v)


def _pick(
    accounts: list[Account],
    *,
    account_type: Optional[str] = None,
    keywords: tuple[str, ...] = (),
) -> Optional[Account]:
    """Choose the best existing account: prefer the given type + a keyword
    match on name/code; else any account of that type; else any account at
    all (so a record is never left unmapped when accounts exist)."""
    pool = [a for a in accounts if account_type is None or _type_val(a) == account_type]
    for kw in keywords:
        for a in pool:
            if kw in (a.name or "").lower() or kw in (a.code or "").lower():
                return a
    if pool:
        return sorted(pool, key=lambda a: (a.code or ""))[0]
    if accounts:
        return sorted(accounts, key=lambda a: (a.code or ""))[0]
    return None


_METHOD_ASSET_KEYWORDS: dict[str, tuple[str, ...]] = {
    "CASH": ("cash - main", "main till", "collections", "cash on hand", "petty cash", "cash"),
    "POS": ("pos", "card settlement", "card"),
    "CARD": ("pos", "card settlement", "card"),
    "TRANSFER": ("transfer", "bank - current", "bank current", "bank"),
    "BANK_TRANSFER": ("transfer", "bank - current", "bank current", "bank"),
    "BANK": ("bank - current", "bank current", "bank"),
    "CHEQUE": ("bank - current", "bank"),
    "CHECK": ("bank - current", "bank"),
    "MOBILE_MONEY": ("mobile", "transfer", "bank"),
    "USSD": ("transfer", "bank"),
    "MEMBERSHIP_CARD": ("membership", "card", "receivable"),
    "WALLET": ("wallet", "membership", "card"),
}


def _pick_cash(accounts: list[Account], method: Optional[str]) -> Optional[Account]:
    kws = _METHOD_ASSET_KEYWORDS.get((method or "").strip().upper(), ())
    return _pick(accounts, account_type="ASSET", keywords=kws)


# --------------------------------------------------------------------------
# Core backfill
# --------------------------------------------------------------------------

def backfill(db: Session, *, commit: bool = False) -> dict:
    """Map every NULL-account monetary record to an existing account.

    Returns a summary dict of per-domain counts and the account chosen. When
    ``commit`` is False the caller is responsible for committing or rolling
    back (dry runs simply close the session, discarding the changes).
    """
    accounts = db.query(Account).filter(Account.is_deleted.is_(False)).all()
    summary: dict = {"has_accounts": bool(accounts), "reimbursements": 0, "salary_advances": 0,
                     "payroll_runs": 0, "billing_items": 0, "billing_payments": 0, "chosen": {}}

    if not accounts:
        return summary  # nothing to map to

    # 1. Reimbursements (expense claims) -> EXPENSE account
    reimb_acct = _pick(accounts, account_type="EXPENSE",
                       keywords=("reimburs", "staff welfare", "welfare", "sundry", "miscellaneous", "staff cost", "other"))
    if reimb_acct is not None:
        rows = (db.query(ReimbursementRequest)
                .filter(ReimbursementRequest.account_id.is_(None),
                        ReimbursementRequest.is_deleted.is_(False)).all())
        for r in rows:
            r.account_id = reimb_acct.id
        summary["reimbursements"] = len(rows)
        summary["chosen"]["reimbursements"] = f"{reimb_acct.code} — {reimb_acct.name}"

    # 2. Salary advances -> ASSET (staff advance receivable)
    adv_acct = _pick(accounts, account_type="ASSET",
                     keywords=("salary advance", "staff salary advance", "staff advance", "advance", "staff loan", "receivable"))
    if adv_acct is not None:
        rows = (db.query(SalaryAdvance)
                .filter(SalaryAdvance.account_id.is_(None),
                        SalaryAdvance.is_deleted.is_(False)).all())
        for r in rows:
            r.account_id = adv_acct.id
        summary["salary_advances"] = len(rows)
        summary["chosen"]["salary_advances"] = f"{adv_acct.code} — {adv_acct.name}"

    # 3. Payroll runs -> EXPENSE (salaries & wages)
    pay_acct = _pick(accounts, account_type="EXPENSE",
                     keywords=("salar", "wages", "payroll", "staff cost"))
    if pay_acct is not None:
        rows = (db.query(PayrollRun)
                .filter(PayrollRun.account_id.is_(None),
                        PayrollRun.is_deleted.is_(False)).all())
        for r in rows:
            r.account_id = pay_acct.id
        summary["payroll_runs"] = len(rows)
        summary["chosen"]["payroll_runs"] = f"{pay_acct.code} — {pay_acct.name}"

    # 4. Billing items -> the line's billable-service account, else a REVENUE account
    rev_acct = _pick(accounts, account_type="REVENUE",
                     keywords=("patient service", "other clinical", "clinical revenue", "revenue"))
    item_rows = (db.query(BillingItem)
                 .filter(BillingItem.account_code.is_(None),
                         BillingItem.is_deleted.is_(False)).all())
    item_count = 0
    for it in item_rows:
        svc_acct = getattr(it.billable_service, "account", None) if it.billable_service is not None else None
        chosen = svc_acct or rev_acct
        if chosen is not None:
            it.account_code = chosen.code
            it.account_name = chosen.name
            item_count += 1
    summary["billing_items"] = item_count
    if rev_acct is not None:
        summary["chosen"]["billing_items_default"] = f"{rev_acct.code} — {rev_acct.name}"

    # 5. Billing payments -> cash/bank ASSET account by payment method
    pay_rows = (db.query(BillingPayment)
                .filter(BillingPayment.account_code.is_(None),
                        BillingPayment.is_deleted.is_(False)).all())
    pay_count = 0
    for p in pay_rows:
        acct = _pick_cash(accounts, p.payment_method)
        if acct is not None:
            p.account_code = acct.code
            p.account_name = acct.name
            pay_count += 1
    summary["billing_payments"] = pay_count

    db.flush()
    if commit:
        db.commit()
    return summary


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _report(label: str, summary: dict, *, applied: bool) -> None:
    print(f"\n[{label}] mode={'APPLY' if applied else 'DRY-RUN'}")
    if not summary.get("has_accounts"):
        print("  no accounts configured for this tenant — nothing to map to; skipped.")
        return
    print(
        "  reimbursements={reimbursements} salary_advances={salary_advances} "
        "payroll_runs={payroll_runs} billing_items={billing_items} "
        "billing_payments={billing_payments}".format(**summary)
    )
    for k, v in (summary.get("chosen") or {}).items():
        print(f"    {k}: {v}")


def _run_cli() -> None:
    parser = argparse.ArgumentParser(description="Backfill ledger accounts on existing monetary records.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all-tenants", action="store_true", help="Run for all provisioned tenants.")
    group.add_argument("--db-url", type=str, help="Run against a specific database URL.")
    parser.add_argument("--apply", action="store_true", help="Persist changes (default is a dry run).")
    args = parser.parse_args()

    if args.all_tenants:
        print("--- Fleet-wide account back-fill ---")
        master_engine = get_master_engine()
        with Session(master_engine) as master_db:
            tenants = master_db.query(Tenant).filter(Tenant.is_provisioned == True).all()  # noqa: E712
            tenant_data = [{"name": t.name, "code": t.code, "conn": t.db_connection_string} for t in tenants]
        for t in tenant_data:
            if not t["conn"]:
                continue
            try:
                engine = create_engine(decrypt_string(t["conn"]))
                db = Session(engine)
                try:
                    _report(f"{t['name']} ({t['code']})", backfill(db, commit=args.apply), applied=args.apply)
                finally:
                    db.close()
                engine.dispose()
            except Exception as e:  # pragma: no cover
                print(f"  [X] {t['code']}: {e}")
        return

    if args.db_url:
        engine = create_engine(args.db_url)
        db = sessionmaker(bind=engine)()
    else:
        db = SessionLocal()
    try:
        _report("single-db", backfill(db, commit=args.apply), applied=args.apply)
    finally:
        db.close()


if __name__ == "__main__":
    _run_cli()
