# app/tests/unit/test_statutory.py
"""
Statutory remittances: WHT withheld on vendor payments, payroll liability
sweep -> positions -> remittance posting -> filing schedules. SQLite,
end to end, trial balance stays balanced.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.enums import PayrollRunStatus, UserStatus
from app.models.base import TenantBase
from app.models.all_models import (
    PayrollLine, PayrollRun, PensionProvider, StaffProfile, User, Vendor,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    TenantBase.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    from app.seeds.accounting_seed import seed_default_chart_of_accounts
    seed_default_chart_of_accounts(s)
    yield s
    s.close()


def _mk_payroll(db: Session):
    u = User(username="jdoe", email="jdoe@x.com", password_hash="x",
             first_name="Jane", last_name="Doe", status=UserStatus.ACTIVE)
    db.add(u)
    db.flush()
    pfa = PensionProvider(code="ARM", name="ARM Pensions")
    db.add(pfa)
    db.flush()
    staff = StaffProfile(user_id=u.id, staff_no="ST-1", tax_id="TIN-123",
                         pension_pin="PEN-9", nhf_no="NHF-7",
                         pension_provider_id=pfa.id)
    db.add(staff)
    db.flush()
    run = PayrollRun(code="RUN-2026-08", period_start=date(2026, 8, 1),
                     period_end=date(2026, 8, 31),
                     status=PayrollRunStatus.APPROVED,
                     total_gross=Decimal("500000"),
                     total_net=Decimal("420000"))
    db.add(run)
    db.flush()
    db.add(PayrollLine(payroll_run_id=run.id, staff_profile_id=staff.id,
                       gross_pay=Decimal("500000"),
                       paye_amount=Decimal("50000"),
                       pension_amount=Decimal("40000"),
                       nhf_amount=Decimal("12500"),
                       net_pay=Decimal("420000")))
    db.flush()
    return staff


def test_wht_on_vendor_payment(db):
    from app.services.finance_ops_service import VendorService
    from app.services.statutory_service import StatutoryService
    v = Vendor(name="MedSupplies Ltd", tax_id="TIN-VENDOR")
    db.add(v)
    db.flush()
    from app.services.system_accounts_service import resolve_system_account
    expense = resolve_system_account(db, "BANK_CHARGES")  # any expense account
    vs = VendorService(db)
    bill = vs.create_bill(vendor_id=v.id, bill_date=date(2026, 8, 5),
                          total_amount=Decimal("100000"),
                          expense_account_id=expense.id)
    paid = vs.pay_bill(bill_id=bill["id"], amount=Decimal("100000"),
                       paid_at=date(2026, 8, 10), wht_rate_percent=5)
    assert paid["status"] == "PAID"

    reg = StatutoryService(db).wht_register(period_code="2026-08")
    assert len(reg) == 1
    assert reg[0]["payee_name"] == "MedSupplies Ltd"
    assert Decimal(reg[0]["wht_amount"]) == Decimal("5000.00")
    assert reg[0]["status"] == "DEDUCTED"

    pos = {p["type"]: p for p in StatutoryService(db).positions()}
    assert Decimal(pos["WHT"]["outstanding"]) == Decimal("5000.00")

    from app.services.accounting_service import AccountingService
    tb = AccountingService(db).trial_balance()
    assert tb["balanced"] is True


def test_payroll_sweep_positions_and_remittance(db):
    from app.services.posting_rules_service import PostingRulesService
    from app.services.statutory_service import StatutoryService
    _mk_payroll(db)
    swept = PostingRulesService(db).sweep_extended()
    assert any(r.startswith("payroll_liabilities:") for r in swept["refs"])

    svc = StatutoryService(db)
    pos = {p["type"]: p for p in svc.positions()}
    assert Decimal(pos["PAYE"]["outstanding"]) == Decimal("50000.00")
    assert Decimal(pos["PENSION"]["outstanding"]) == Decimal("40000.00")
    assert Decimal(pos["NHF"]["outstanding"]) == Decimal("12500.00")

    # Remit PAYE in full (amount defaults to the outstanding balance).
    r = svc.create_remittance(remittance_type="PAYE", period_code="2026-08",
                              paid_at=date(2026, 9, 8), reference="SIRS/08")
    assert Decimal(r["amount"]) == Decimal("50000.00")
    pos = {p["type"]: p for p in svc.positions()}
    assert Decimal(pos["PAYE"]["outstanding"]) == Decimal("0.00")

    # Over-remitting is refused with a clear message.
    with pytest.raises(Exception) as exc:
        svc.create_remittance(remittance_type="PAYE", period_code="2026-08",
                              paid_at=date(2026, 9, 9), amount=Decimal("1"))
    assert "outstanding" in str(exc.value).lower() or "nothing" in str(exc.value).lower()


def test_filing_schedules(db):
    from app.services.posting_rules_service import PostingRulesService
    from app.services.statutory_service import StatutoryService
    _mk_payroll(db)
    PostingRulesService(db).sweep_extended()
    svc = StatutoryService(db)

    paye = svc.schedule("PAYE", period_code="2026-08")
    assert paye["count"] == 1
    assert paye["rows"][0]["tax_id"] == "TIN-123"
    assert Decimal(paye["total"]) == Decimal("50000")

    pension = svc.schedule("PENSION", period_code="2026-08")
    assert pension["rows"][0]["pfa"] == "ARM Pensions"
    assert pension["rows"][0]["pension_pin"] == "PEN-9"

    nhf = svc.schedule("NHF", period_code="2026-08")
    assert nhf["rows"][0]["nhf_no"] == "NHF-7"

    name, blob = svc.schedule_xlsx("PAYE", period_code="2026-08")
    assert name.endswith(".xlsx") and len(blob) > 500


def test_wht_remittance_marks_records(db):
    from app.services.statutory_service import StatutoryService, record_vendor_wht
    from app.services.accounting_service import AccountingService
    from app.services.system_accounts_service import resolve_system_account
    from app.core.enums import JournalSourceType
    svc = StatutoryService(db)
    v = Vendor(name="Consultants LLP", tax_id="TIN-C")
    db.add(v)
    db.flush()
    rec = record_vendor_wht(db, vendor=v, gross_amount=Decimal("200000"),
                            rate_percent=Decimal("10"),
                            wht_amount=Decimal("20000"), reference="INV-77")
    # accrue the matching liability in the ledger
    wht = resolve_system_account(db, "WHT_PAYABLE")
    exp = resolve_system_account(db, "BANK_CHARGES")
    AccountingService(db).create_entry(
        entry_date=date(2026, 8, 15), memo="test accrual",
        lines=[{"account_id": exp.id, "debit": Decimal("20000"), "credit": 0},
               {"account_id": wht.id, "debit": 0, "credit": Decimal("20000")}],
        source_type=JournalSourceType.TAX, auto_post=True)
    db.commit()

    out = svc.create_remittance(remittance_type="WHT", period_code="2026-08",
                                paid_at=date(2026, 9, 21), reference="FIRS/2026/08")
    assert out["wht_records_marked"] == 1
    reg = svc.wht_register()
    assert reg[0]["status"] == "REMITTED"
