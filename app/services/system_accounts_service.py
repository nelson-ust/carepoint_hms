# app/services/system_accounts_service.py
from __future__ import annotations

"""
System-account mapping, accounting configuration and document sequences.

``resolve_system_account(db, key)`` is the single way any posting code should
obtain a "well-known" ledger account (Accounts Payable, HMO Receivable,
Pharmacy COGS, ...). Resolution order:

1. Tenant-editable ``SystemAccountMapping`` row for the key.
2. An existing account matching the built-in default code (mapping row is
   created pointing at it, so the settings page always shows the truth).
3. The account is created from the built-in default and mapped.

The legacy ``finance_ops_service.get_or_create_system_account`` delegates
here, so old keys ("AP", "SALARY_EXP", ...) keep working.
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import AccountType, CashFlowCategory
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import Account
from app.models.finance_models import AccountingConfig, DocumentSequence, SystemAccountMapping


#: key -> (code, name, AccountType, CashFlowCategory)
DEFAULT_SYSTEM_ACCOUNTS: dict[str, tuple[str, str, AccountType, str]] = {
    # ---- legacy keys (kept identical to finance_ops_service) ----
    "AP":            ("2100", "Accounts Payable", AccountType.LIABILITY, "OPERATING"),
    "ACC_DEP":       ("1590", "Accumulated Depreciation", AccountType.ASSET, "NONE"),
    "DEP_EXP":       ("5900", "Depreciation Expense", AccountType.EXPENSE, "NONE"),
    "RETAINED":      ("3900", "Retained Earnings", AccountType.EQUITY, "NONE"),
    "SALARY_EXP":    ("5100", "Salaries & Wages Expense", AccountType.EXPENSE, "OPERATING"),
    "STAFF_ADV":     ("1450", "Staff Salary Advances", AccountType.ASSET, "OPERATING"),
    # ---- receivables ----
    "PATIENT_AR":    ("1200", "Accounts Receivable — Patients", AccountType.ASSET, "OPERATING"),
    "HMO_AR":        ("1210", "Accounts Receivable — HMO / Insurance", AccountType.ASSET, "OPERATING"),
    "CAPITATION_AR": ("1220", "Accounts Receivable — Capitation", AccountType.ASSET, "OPERATING"),
    # ---- revenue ----
    "PATIENT_REVENUE":   ("4000", "Patient Services Revenue", AccountType.REVENUE, "OPERATING"),
    "INSURANCE_REVENUE": ("4100", "Insurance (Fee-for-Service) Revenue", AccountType.REVENUE, "OPERATING"),
    "CAPITATION_INCOME": ("4110", "Capitation Income", AccountType.REVENUE, "OPERATING"),
    # ---- insurance costs ----
    "DISALLOWANCE_EXPENSE": ("5600", "Claim Disallowance Expense", AccountType.EXPENSE, "OPERATING"),
    "DISALLOWANCE_CONTRA":  ("4190", "Claim Disallowances (contra-revenue)", AccountType.REVENUE, "OPERATING"),
    # ---- inventory / pharmacy ----
    "INVENTORY_ASSET":     ("1300", "Inventory — Pharmacy & Consumables", AccountType.ASSET, "OPERATING"),
    "PHARMACY_COGS":       ("5200", "Pharmacy Cost of Goods Sold", AccountType.EXPENSE, "OPERATING"),
    "INVENTORY_SHRINKAGE": ("5210", "Inventory Shrinkage & Expiries", AccountType.EXPENSE, "OPERATING"),
    # ---- payroll liabilities ----
    "NET_SALARIES_PAYABLE": ("2200", "Net Salaries Payable", AccountType.LIABILITY, "OPERATING"),
    "PAYE_PAYABLE":         ("2210", "PAYE Tax Payable", AccountType.LIABILITY, "OPERATING"),
    "PENSION_PAYABLE":      ("2220", "Pension Contributions Payable", AccountType.LIABILITY, "OPERATING"),
    "NHF_PAYABLE":          ("2230", "NHF Payable", AccountType.LIABILITY, "OPERATING"),
    "OTHER_DEDUCTIONS_PAYABLE": ("2240", "Other Payroll Deductions Payable", AccountType.LIABILITY, "OPERATING"),
    # ---- taxes ----
    "VAT_PAYABLE": ("2300", "VAT Payable", AccountType.LIABILITY, "OPERATING"),
    "WHT_PAYABLE": ("2310", "Withholding Tax Payable", AccountType.LIABILITY, "OPERATING"),
    # ---- cash & banks ----
    "BANK_DEFAULT":      ("1010", "Bank — Main Account", AccountType.ASSET, "NONE"),
    "CASH_ON_HAND":      ("1000", "Cash on Hand", AccountType.ASSET, "NONE"),
    "PETTY_CASH":        ("1020", "Petty Cash", AccountType.ASSET, "NONE"),
    "UNDEPOSITED_FUNDS": ("1030", "Undeposited Funds", AccountType.ASSET, "NONE"),
    # ---- equity / other ----
    "OPENING_BALANCE_EQUITY": ("3800", "Opening Balance Equity", AccountType.EQUITY, "NONE"),
    "BAD_DEBT_EXPENSE":       ("5700", "Bad Debt Expense", AccountType.EXPENSE, "OPERATING"),
    "CASH_VARIANCE":          ("5710", "Cash Over/Short", AccountType.EXPENSE, "OPERATING"),
    "BANK_CHARGES":           ("5720", "Bank Charges", AccountType.EXPENSE, "OPERATING"),
    "INTEREST_INCOME":        ("4200", "Interest Income", AccountType.REVENUE, "OPERATING"),
}


def resolve_system_account(db: Session, key: str) -> Account:
    """Return the ledger account mapped to ``key``, creating the mapping
    (and, if necessary, the account) from the built-in defaults."""
    key = key.upper()
    mapping = (db.query(SystemAccountMapping)
               .filter(SystemAccountMapping.key == key,
                       SystemAccountMapping.is_deleted.is_(False)).first())
    if mapping is not None:
        acct = db.query(Account).filter(Account.id == mapping.account_id,
                                        Account.is_deleted.is_(False)).first()
        if acct is not None:
            return acct
    if key not in DEFAULT_SYSTEM_ACCOUNTS:
        raise BadRequestError(f"Unknown system account key '{key}'.")
    code, name, acc_type, cf = DEFAULT_SYSTEM_ACCOUNTS[key]
    acct = db.query(Account).filter(Account.code == code, Account.is_deleted.is_(False)).first()
    if acct is None:
        acct = db.query(Account).filter(Account.name == name, Account.is_deleted.is_(False)).first()
    if acct is None:
        acct = Account(code=code, name=name, account_type=acc_type,
                       cash_flow_category=cf, is_system=True,
                       description="Auto-created system account.")
        db.add(acct)
        db.flush()
    if mapping is None:
        db.add(SystemAccountMapping(key=key, account_id=acct.id,
                                    description=name))
        db.flush()
    else:
        mapping.account_id = acct.id
        db.flush()
    return acct


def list_system_account_mappings(db: Session) -> list[dict]:
    """All known keys with their currently-resolved account (resolving lazily
    so the settings page shows a complete, editable picture)."""
    out = []
    for key in DEFAULT_SYSTEM_ACCOUNTS:
        acct = resolve_system_account(db, key)
        out.append({
            "key": key,
            "account_id": acct.id,
            "account_code": acct.code,
            "account_name": acct.name,
            "account_type": acct.account_type.value if hasattr(acct.account_type, "value") else acct.account_type,
            "default_code": DEFAULT_SYSTEM_ACCOUNTS[key][0],
        })
    return out


def set_system_account_mapping(db: Session, *, key: str, account_id: int) -> dict:
    key = key.upper()
    if key not in DEFAULT_SYSTEM_ACCOUNTS:
        raise BadRequestError(f"Unknown system account key '{key}'.")
    acct = db.query(Account).filter(Account.id == account_id,
                                    Account.is_deleted.is_(False)).first()
    if acct is None:
        raise NotFoundError("Account not found.")
    mapping = (db.query(SystemAccountMapping)
               .filter(SystemAccountMapping.key == key,
                       SystemAccountMapping.is_deleted.is_(False)).first())
    if mapping is None:
        mapping = SystemAccountMapping(key=key, account_id=account_id)
        db.add(mapping)
    else:
        mapping.account_id = account_id
    db.flush()
    audit(db, action="SYSTEM_ACCOUNT_REMAPPED", entity_type="system_account_mapping",
          entity_id=mapping.id,
          summary=f"{key} -> {acct.code} · {acct.name}")
    db.commit()
    return {"key": key, "account_id": account_id,
            "account_code": acct.code, "account_name": acct.name}


# ---------------------------------------------------------------------------
# Accounting config (single row)
# ---------------------------------------------------------------------------

def get_accounting_config(db: Session) -> AccountingConfig:
    cfg = (db.query(AccountingConfig)
           .filter(AccountingConfig.is_deleted.is_(False))
           .order_by(AccountingConfig.id.asc()).first())
    if cfg is None:
        cfg = AccountingConfig()
        db.add(cfg)
        db.flush()
    return cfg


def config_read(cfg: AccountingConfig) -> dict:
    return {
        "opening_balance_date": cfg.opening_balance_date.isoformat() if cfg.opening_balance_date else None,
        "journal_approval_threshold": str(cfg.journal_approval_threshold) if cfg.journal_approval_threshold is not None else None,
        "disallowance_as_expense": cfg.disallowance_as_expense,
        "enforce_preauth_block": cfg.enforce_preauth_block,
        "require_eligibility_check": cfg.require_eligibility_check,
    }


def update_accounting_config(db: Session, **fields) -> dict:
    cfg = get_accounting_config(db)
    allowed = {"opening_balance_date", "journal_approval_threshold",
               "disallowance_as_expense", "enforce_preauth_block",
               "require_eligibility_check"}
    changed = {}
    for k, v in fields.items():
        if k in allowed and v is not None:
            setattr(cfg, k, v)
            changed[k] = str(v)
    db.flush()
    if changed:
        audit(db, action="ACCOUNTING_CONFIG_CHANGED", entity_type="accounting_config",
              entity_id=cfg.id, summary=", ".join(f"{k}={v}" for k, v in changed.items()),
              detail=changed)
    db.commit()
    return config_read(cfg)


# ---------------------------------------------------------------------------
# Document sequences (receipts, credit notes, refunds, vouchers, ...)
# ---------------------------------------------------------------------------

_SEQUENCE_DEFAULTS = {
    "RECEIPT":      ("RCT-", 6),
    "CREDIT_NOTE":  ("CN-", 5),
    "VENDOR_CN":    ("VCN-", 5),
    "REFUND":       ("RFD-", 5),
    "PC_VOUCHER":   ("PCV-", 5),
    "REMITTANCE":   ("REM-", 5),
    "CLAIM_BATCH":  ("CB-", 5),
}


def next_document_no(db: Session, key: str) -> str:
    """Allocate the next number for ``key`` under a row lock (duplicate-free
    under concurrency; PostgreSQL honours FOR UPDATE, SQLite serialises)."""
    key = key.upper()
    prefix, padding = _SEQUENCE_DEFAULTS.get(key, (f"{key}-", 6))
    seq = (db.query(DocumentSequence)
           .filter(DocumentSequence.key == key)
           .with_for_update()
           .first())
    if seq is None:
        seq = DocumentSequence(key=key, prefix=prefix, next_number=1, padding=padding)
        db.add(seq)
        db.flush()
        seq = (db.query(DocumentSequence)
               .filter(DocumentSequence.key == key)
               .with_for_update().first())
    number = seq.next_number
    seq.next_number = number + 1
    db.flush()
    return f"{seq.prefix or ''}{number:0{seq.padding or 6}d}"


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------

def audit(db: Session, *, action: str, entity_type: str,
          entity_id: Optional[int] = None, user_id: Optional[int] = None,
          summary: Optional[str] = None, detail: Optional[dict] = None,
          ip: Optional[str] = None) -> None:
    """Append an immutable accounting audit-log row (best-effort)."""
    from datetime import datetime, timezone
    from app.models.finance_models import AccountingAuditLog
    try:
        db.add(AccountingAuditLog(
            actor_user_id=user_id, action=action, entity_type=entity_type,
            entity_id=entity_id, summary=summary, detail=detail,
            ip_address=ip, occurred_at=datetime.now(timezone.utc)))
        db.flush()
    except Exception:  # pragma: no cover — audit must never break business flow
        pass
