# app/seeds/accounting_seed.py
from __future__ import annotations

"""
Default Nigerian-hospital chart of accounts (hierarchical) + demo HMO data.

``seed_default_chart_of_accounts`` is idempotent — it only creates accounts
whose codes are missing — so it is safe to run on every tenant schema sync
and against tenants that already customised their chart.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.enums import AccountType, InsuranceProviderType, PlanCoverageType
from app.models.all_models import Account, BillableService, InsuranceProvider

A, L, Q, R, E = (AccountType.ASSET, AccountType.LIABILITY, AccountType.EQUITY,
                 AccountType.REVENUE, AccountType.EXPENSE)

#: (code, name, type, cash_flow_category, parent_code, postable)
DEFAULT_COA: list[tuple] = [
    ("1000-H", "ASSETS", A, "NONE", None, False),
    ("1000", "Cash on Hand", A, "NONE", "1000-H", True),
    ("1010", "Bank — Main Account", A, "NONE", "1000-H", True),
    ("1020", "Petty Cash", A, "NONE", "1000-H", True),
    ("1030", "Undeposited Funds", A, "NONE", "1000-H", True),
    ("1200", "Accounts Receivable — Patients", A, "OPERATING", "1000-H", True),
    ("1210", "Accounts Receivable — HMO / Insurance", A, "OPERATING", "1000-H", True),
    ("1220", "Accounts Receivable — Capitation", A, "OPERATING", "1000-H", True),
    ("1300", "Inventory — Pharmacy & Consumables", A, "OPERATING", "1000-H", True),
    ("1450", "Staff Salary Advances", A, "OPERATING", "1000-H", True),
    ("1500-H", "Fixed Assets", A, "NONE", "1000-H", False),
    ("1510", "Medical Equipment", A, "INVESTING", "1500-H", True),
    ("1520", "Buildings & Improvements", A, "INVESTING", "1500-H", True),
    ("1530", "Vehicles & Ambulances", A, "INVESTING", "1500-H", True),
    ("1540", "Furniture & Office Equipment", A, "INVESTING", "1500-H", True),
    ("1590", "Accumulated Depreciation", A, "NONE", "1500-H", True),

    ("2000-H", "LIABILITIES", L, "NONE", None, False),
    ("2100", "Accounts Payable", L, "OPERATING", "2000-H", True),
    ("2200", "Net Salaries Payable", L, "OPERATING", "2000-H", True),
    ("2210", "PAYE Tax Payable", L, "OPERATING", "2000-H", True),
    ("2220", "Pension Contributions Payable", L, "OPERATING", "2000-H", True),
    ("2230", "NHF Payable", L, "OPERATING", "2000-H", True),
    ("2240", "Other Payroll Deductions Payable", L, "OPERATING", "2000-H", True),
    ("2300", "VAT Payable", L, "OPERATING", "2000-H", True),
    ("2310", "Withholding Tax Payable", L, "OPERATING", "2000-H", True),

    ("3000-H", "EQUITY", Q, "NONE", None, False),
    ("3800", "Opening Balance Equity", Q, "NONE", "3000-H", True),
    ("3900", "Retained Earnings", Q, "NONE", "3000-H", True),

    ("4000-H", "INCOME", R, "NONE", None, False),
    ("4000", "Patient Services Revenue", R, "OPERATING", "4000-H", True),
    ("4010", "Consultation Revenue", R, "OPERATING", "4000-H", True),
    ("4020", "Pharmacy Sales Revenue", R, "OPERATING", "4000-H", True),
    ("4030", "Laboratory Revenue", R, "OPERATING", "4000-H", True),
    ("4040", "Radiology Revenue", R, "OPERATING", "4000-H", True),
    ("4050", "Procedure & Theatre Revenue", R, "OPERATING", "4000-H", True),
    ("4060", "Admission & Ward Revenue", R, "OPERATING", "4000-H", True),
    ("4100", "Insurance (Fee-for-Service) Revenue", R, "OPERATING", "4000-H", True),
    ("4110", "Capitation Income", R, "OPERATING", "4000-H", True),
    ("4190", "Claim Disallowances (contra-revenue)", R, "OPERATING", "4000-H", True),
    ("4200", "Interest Income", R, "OPERATING", "4000-H", True),

    ("5000-H", "EXPENSES", E, "NONE", None, False),
    ("5100", "Salaries & Wages Expense", E, "OPERATING", "5000-H", True),
    ("5200", "Pharmacy Cost of Goods Sold", E, "OPERATING", "5000-H", True),
    ("5210", "Inventory Shrinkage & Expiries", E, "OPERATING", "5000-H", True),
    ("5300", "Medical & Lab Consumables", E, "OPERATING", "5000-H", True),
    ("5400", "Utilities (Power, Water, Diesel)", E, "OPERATING", "5000-H", True),
    ("5500", "Repairs & Maintenance", E, "OPERATING", "5000-H", True),
    ("5600", "Claim Disallowance Expense", E, "OPERATING", "5000-H", True),
    ("5700", "Bad Debt Expense", E, "OPERATING", "5000-H", True),
    ("5710", "Cash Over/Short", E, "OPERATING", "5000-H", True),
    ("5720", "Bank Charges", E, "OPERATING", "5000-H", True),
    ("5900", "Depreciation Expense", E, "NONE", "5000-H", True),
]


def seed_default_chart_of_accounts(db: Session) -> dict:
    """Create any missing default accounts (idempotent, additive)."""
    existing = {a.code: a for a in db.query(Account)
                .filter(Account.is_deleted.is_(False)).all()}
    created = 0
    for code, name, acc_type, cf, parent_code, postable in DEFAULT_COA:
        if code in existing:
            continue
        acct = Account(code=code, name=name, account_type=acc_type,
                       cash_flow_category=cf, is_postable=postable,
                       is_system=True,
                       description="Default hospital chart of accounts.")
        db.add(acct)
        db.flush()
        existing[code] = acct
        created += 1
    # second pass: wire the hierarchy
    for code, _n, _t, _cf, parent_code, _p in DEFAULT_COA:
        acct = existing.get(code)
        parent = existing.get(parent_code) if parent_code else None
        if acct is not None and parent is not None and acct.parent_account_id is None:
            acct.parent_account_id = parent.id
    db.flush()
    return {"created": created, "total_default_codes": len(DEFAULT_COA)}


def seed_demo_hmos(db: Session) -> dict:
    """Two demo HMOs — one capitation, one fee-for-service — with plans,
    benefits and a small tariff, for fresh-tenant demos. Idempotent."""
    from app.models.finance_models import (
        CapitationContract, HmoPlan, HmoPlanBenefit, HmoTariff)
    made = {"providers": 0, "plans": 0, "benefits": 0, "tariffs": 0, "contracts": 0}

    def _provider(name, code, ptype, cap, ffs):
        p = (db.query(InsuranceProvider)
             .filter(InsuranceProvider.name == name).first())
        if p is None:
            p = InsuranceProvider(name=name, code=code)
            db.add(p)
            made["providers"] += 1
        p.provider_type = ptype.value
        p.capitation_supported = cap
        p.fee_for_service_supported = ffs
        db.flush()
        return p

    demo_ffs = _provider("Demo HealthShield HMO", "DEMO-HS",
                         InsuranceProviderType.PRIVATE_HMO, False, True)
    demo_cap = _provider("Demo X-Health (Capitation)", "DEMO-XH",
                         InsuranceProviderType.NHIA, True, True)

    def _plan(provider, name, code, cov_type, cov_pct, copay_flat):
        pl = db.query(HmoPlan).filter(HmoPlan.code == code).first()
        if pl is None:
            pl = HmoPlan(insurance_provider_id=provider.id, name=name, code=code)
            db.add(pl)
            made["plans"] += 1
        pl.coverage_type = cov_type
        pl.default_coverage_percent = Decimal(cov_pct)
        pl.default_copay_flat = Decimal(copay_flat)
        db.flush()
        return pl

    gold = _plan(demo_ffs, "HealthShield Gold", "DEMO-HS-GOLD",
                 PlanCoverageType.FEE_FOR_SERVICE, "90", "500")
    basic = _plan(demo_cap, "X-Health Basic (Capitated)", "DEMO-XH-BASIC",
                  PlanCoverageType.CAPITATION, "100", "0")

    if not db.query(HmoPlanBenefit).filter(HmoPlanBenefit.hmo_plan_id == gold.id).first():
        db.add_all([
            HmoPlanBenefit(hmo_plan_id=gold.id, category="PHARMACY",
                           coverage_percent=Decimal("50")),
            HmoPlanBenefit(hmo_plan_id=gold.id, category="RADIOLOGY",
                           coverage_percent=Decimal("90"), requires_preauth=True),
            HmoPlanBenefit(hmo_plan_id=gold.id, category="OPTICAL", is_excluded=True),
        ])
        made["benefits"] += 3
    svc = (db.query(BillableService)
           .filter(BillableService.is_deleted.is_(False)).first())
    if svc is not None and not db.query(HmoTariff).filter(
            HmoTariff.hmo_plan_id == gold.id).first():
        db.add(HmoTariff(hmo_plan_id=gold.id, billable_service_id=svc.id,
                         agreed_price=svc.default_price))
        made["tariffs"] += 1
    if not db.query(CapitationContract).filter(
            CapitationContract.insurance_provider_id == demo_cap.id).first():
        db.add(CapitationContract(
            insurance_provider_id=demo_cap.id, hmo_plan_id=basic.id,
            rate_per_enrollee=Decimal("750"),
            effective_from=date(date.today().year, 1, 1), payment_day=25))
        made["contracts"] += 1
    db.flush()
    return made
