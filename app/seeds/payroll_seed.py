# app/seeds/payroll_seed.py
from __future__ import annotations

"""
Idempotent payroll lookup seed: a comprehensive catalog of allowance and
deduction types common in Nigerian hospitals, plus statutory deduction
configs (pension, NHF, NHIS) and the PAYE band table under the
Nigeria Tax Act 2025 (effective 1 January 2026).

Hospitals can freely edit, deactivate or extend these in Payroll → Lookups;
the seed only ever ADDS missing codes — it never overwrites configured rows.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.all_models import (
    AllowanceType,
    DeductionType,
    PayrollComponent,
    PayrollComponentTemplate,
    PayrollComponentTemplateItem,
    StatutoryDeductionConfig,
)
from app.core.enums import PayrollCalcMethod, PayrollComponentType

# (code, name, taxable, default_percent_of_base) — percent None = amount-based
ALLOWANCE_SEEDS: list[tuple[str, str, bool, str | None]] = [
    ("HOUSING", "Housing Allowance", True, "20"),
    ("TRANSPORT", "Transport Allowance", True, "10"),
    ("MEAL", "Meal / Feeding Allowance", True, None),
    ("UTILITY", "Utility Allowance", True, None),
    ("LEAVE", "Leave Allowance", True, "10"),
    ("HAZARD", "Hazard Allowance", True, None),
    ("CALL_DUTY", "Call Duty Allowance", True, None),
    ("SHIFT", "Shift Allowance", True, None),
    ("RURAL_POSTING", "Rural Posting Allowance", True, None),
    ("RESPONSIBILITY", "Responsibility Allowance", True, None),
    ("SPECIALIST", "Specialist / Consultancy Allowance", True, None),
    ("TEACHING", "Teaching / Training Allowance", True, None),
    ("CME", "Professional Development (CME) Allowance", False, None),
    ("UNIFORM", "Uniform / Laundry Allowance", False, None),
    ("ENTERTAINMENT", "Entertainment Allowance", True, None),
    ("DRESSING", "Dressing Allowance", True, None),
    ("INDUCEMENT", "Inducement Allowance", True, None),
    ("OTHER_ALLOWANCE", "Other Allowance", True, None),
]

# (code, name, statutory, default_percent_of_base)
DEDUCTION_SEEDS: list[tuple[str, str, bool, str | None]] = [
    ("PAYE", "PAYE Income Tax", True, None),           # computed by the engine
    ("PENSION", "Pension (Employee)", True, "8"),      # computed by the engine
    ("NHF", "National Housing Fund", True, "2.5"),     # computed by the engine
    ("NHIS", "Health Insurance (NHIA/NHIS)", True, "5"),
    ("LIFE_INSURANCE", "Group Life Insurance Premium", False, None),
    ("UNION_DUES", "Union Dues (e.g. NANNM/NMA/JOHESU)", False, None),
    ("COOPERATIVE", "Cooperative Contribution", False, None),
    ("WELFARE", "Staff Welfare Levy", False, None),
    ("LATENESS", "Lateness / Absence Deduction", False, None),
    ("LOAN_REPAYMENT", "Loan Repayment", False, None),     # engine-driven
    ("SALARY_ADVANCE", "Salary Advance Recovery", False, None),  # engine-driven
    ("OTHER_DEDUCTION", "Other Deduction", False, None),
]

#: Nigeria Tax Act 2025 — annual bands as [width_or_null, rate_percent].
NTA_2025_BANDS: list[list] = [
    [800_000, 0],        # first ₦800,000 — tax-free
    [2_200_000, 15],     # ₦800,001 – ₦3,000,000
    [9_000_000, 18],     # ₦3,000,001 – ₦12,000,000
    [13_000_000, 21],    # ₦12,000,001 – ₦25,000,000
    [25_000_000, 23],    # ₦25,000,001 – ₦50,000,000
    [None, 25],          # above ₦50,000,000
]

STATUTORY_SEEDS: list[dict] = [
    {"code": "PENSION", "name": "Pension (Contributory, PRA 2014)",
     "rate_percent": Decimal("8"), "employer_rate_percent": Decimal("10"),
     "note": "Employee 8% / employer 10% of monthly emoluments."},
    {"code": "NHF", "name": "National Housing Fund",
     "rate_percent": Decimal("2.5"), "employer_rate_percent": None,
     "note": "2.5% of basic salary (NHF Act)."},
    {"code": "NHIS", "name": "Health Insurance (NHIA Act 2022)",
     "rate_percent": Decimal("5"), "employer_rate_percent": Decimal("10"),
     "note": "Formal sector: employee 5% / employer 10% of basic (configure to your scheme)."},
    {"code": "NSITF", "name": "NSITF — Employees' Compensation (ECA 2010)",
     "rate_percent": None, "employer_rate_percent": Decimal("1"),
     "note": "1% of total monthly emoluments, employer-borne — remitted to the "
             "Nigeria Social Insurance Trust Fund. Never deducted from staff pay."},
    {"code": "PAYE", "name": "PAYE — Nigeria Tax Act 2025",
     "rate_percent": None, "employer_rate_percent": None,
     "bands_json": NTA_2025_BANDS,
     "note": ("Progressive annual bands per the Nigeria Tax Act 2025 (effective "
              "1 Jan 2026). First ₦800k tax-free; CRA abolished; rent relief = "
              "20% of annual rent capped at ₦500,000.")},
]


#: Component catalog seeds: (code, name, type, calc_method, default_amount,
#: default_percent, is_taxable, is_tax_relief, is_statutory, display_order)
_E = PayrollComponentType.EARNING
_D = PayrollComponentType.DEDUCTION
_S = PayrollComponentType.STATUTORY
_C = PayrollComponentType.EMPLOYER_CONTRIBUTION
_FIX = PayrollCalcMethod.FIXED_AMOUNT
_PCT = PayrollCalcMethod.PERCENT_OF_BASE

COMPONENT_SEEDS: list[tuple] = [
    ("BASIC", "Basic Salary", _E, _FIX, None, None, True, False, False, 0),
    ("OVERTIME", "Overtime", _E, _FIX, None, None, True, False, False, 90),
    ("BONUS", "Bonus", _E, _FIX, None, None, True, False, False, 91),
    ("ARREARS", "Salary Arrears", _E, _FIX, None, None, True, False, False, 92),
    ("THIRTEENTH_MONTH", "13th-Month Pay", _E, _FIX, None, None, True, False, False, 93),
    ("OTHER_EARNING", "Other Earning", _E, _FIX, None, None, True, False, False, 94),
    ("PAYE", "PAYE Income Tax", _S, _FIX, None, None, False, False, True, 100),
    ("PENSION", "Pension (Employee 8%)", _S, _PCT, None, "8", False, False, True, 101),
    ("NHF", "National Housing Fund (2.5% of basic)", _S, _PCT, None, "2.5", False, False, True, 102),
    ("PENSION_EMPLOYER", "Pension (Employer 10%)", _C, _PCT, None, "10", False, False, True, 110),
    ("NSITF", "NSITF (Employer 1% of gross)", _C, _PCT, None, "1", False, False, True, 111),
    ("LOAN_REPAYMENT", "Loan Repayment", _D, _FIX, None, None, False, False, False, 120),
    ("SALARY_ADVANCE", "Salary Advance Recovery", _D, _FIX, None, None, False, False, False, 121),
]


def seed_payroll_components(db: Session) -> dict:
    """Idempotent component-catalog seeding.

    Mirrors the allowance/deduction catalogs into PayrollComponent (earnings
    from ALLOWANCE_SEEDS, voluntary deductions from DEDUCTION_SEEDS) and adds
    the engine components (BASIC, OVERTIME, statutory, recoveries). Also seeds
    one example 'STANDARD' template so templates are discoverable.
    """
    added = {"components": 0, "templates": 0}

    order = 10
    for code, name, taxable, pct in ALLOWANCE_SEEDS:
        if db.query(PayrollComponent).filter(PayrollComponent.code == code).first():
            continue
        db.add(PayrollComponent(
            code=code, name=name, component_type=_E,
            calc_method=_PCT if pct else _FIX,
            default_percent=Decimal(pct) if pct else None,
            is_taxable=taxable, is_tax_relief=False, is_statutory=False,
            display_order=order,
        ))
        added["components"] += 1
        order += 1

    order = 130
    for code, name, statutory, pct in DEDUCTION_SEEDS:
        if code in {"PAYE", "PENSION", "NHF", "LOAN_REPAYMENT", "SALARY_ADVANCE"}:
            continue  # covered by COMPONENT_SEEDS as engine components
        if db.query(PayrollComponent).filter(PayrollComponent.code == code).first():
            continue
        db.add(PayrollComponent(
            code=code, name=name, component_type=_D,
            calc_method=_PCT if pct else _FIX,
            default_percent=Decimal(pct) if pct else None,
            is_taxable=True,
            is_tax_relief=code in {"NHIS", "LIFE_INSURANCE"},
            is_statutory=statutory,
            display_order=order,
        ))
        added["components"] += 1
        order += 1

    for (code, name, ctype, method, amt, pct, taxable,
         relief, statutory, order_) in COMPONENT_SEEDS:
        if db.query(PayrollComponent).filter(PayrollComponent.code == code).first():
            continue
        db.add(PayrollComponent(
            code=code, name=name, component_type=ctype, calc_method=method,
            default_amount=Decimal(amt) if amt else None,
            default_percent=Decimal(pct) if pct else None,
            is_taxable=taxable, is_tax_relief=relief, is_statutory=statutory,
            display_order=order_,
        ))
        added["components"] += 1

    db.flush()

    # Example template: the classic Nigerian percent-of-base structure.
    if db.query(PayrollComponentTemplate).filter(
            PayrollComponentTemplate.code == "STANDARD").first() is None:
        tpl = PayrollComponentTemplate(
            code="STANDARD", name="Standard Package",
            description=("Housing 20%, transport 10% and leave allowance 10% "
                         "of basic — a starting point; duplicate and adjust "
                         "per cadre."),
        )
        db.add(tpl)
        db.flush()
        comp_by_code = {
            c.code: c for c in db.query(PayrollComponent)
            .filter(PayrollComponent.code.in_(["HOUSING", "TRANSPORT", "LEAVE"])).all()
        }
        for order_, code in enumerate(("HOUSING", "TRANSPORT", "LEAVE")):
            comp = comp_by_code.get(code)
            if comp is not None:
                db.add(PayrollComponentTemplateItem(
                    template_id=tpl.id, component_id=comp.id,
                    percent=comp.default_percent or Decimal("0"),
                    display_order=order_,
                ))
        added["templates"] += 1

    db.flush()
    return added


def seed_payroll_lookups(db: Session) -> dict:
    added = {"allowances": 0, "deductions": 0, "statutory": 0}

    for code, name, taxable, pct in ALLOWANCE_SEEDS:
        if db.query(AllowanceType).filter(AllowanceType.code == code).first():
            continue
        db.add(AllowanceType(code=code, name=name, is_taxable=taxable,
                             default_percent_of_base=Decimal(pct) if pct else None,
                             is_active=True))
        added["allowances"] += 1

    for code, name, statutory, pct in DEDUCTION_SEEDS:
        if db.query(DeductionType).filter(DeductionType.code == code).first():
            continue
        db.add(DeductionType(code=code, name=name, is_statutory=statutory,
                             default_percent_of_base=Decimal(pct) if pct else None,
                             is_active=True))
        added["deductions"] += 1

    for cfg in STATUTORY_SEEDS:
        if db.query(StatutoryDeductionConfig).filter(
                StatutoryDeductionConfig.code == cfg["code"]).first():
            continue
        db.add(StatutoryDeductionConfig(
            code=cfg["code"], name=cfg["name"],
            rate_percent=cfg.get("rate_percent"),
            employer_rate_percent=cfg.get("employer_rate_percent"),
            bands_json=cfg.get("bands_json"),
            effective_from=date(2026, 1, 1),
            note=cfg.get("note"),
        ))
        added["statutory"] += 1

    db.flush()
    added.update(seed_payroll_components(db))
    return added
