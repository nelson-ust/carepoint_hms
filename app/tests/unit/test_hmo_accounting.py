# app/tests/unit/test_hmo_accounting.py
"""
End-to-end unit tests (SQLite) for the HMO/insurance + full-accounting build:
coverage engine split, charge-capture integration, capitation lifecycle,
extended auto-posting, credit notes and bank reconciliation — finishing with
a balanced trial balance.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import TenantBase
from app.models.all_models import (
    Account, Billing, BillingItem, InsuranceProvider, Patient, PatientInsurance,
    JournalEntry, JournalEntryLine, BillableService,
)
from app.core.enums import (
    Gender, InsurancePolicyStatus, JournalEntryStatus, PlanCoverageType,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    TenantBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    yield s
    s.close()


def _mk_world(db: Session):
    """Provider + 90% plan (₦500 copay, pharmacy 50%) + enrolled patient."""
    from app.seeds.accounting_seed import seed_default_chart_of_accounts
    from app.models.finance_models import HmoPlan, HmoPlanBenefit, HmoTariff
    seed_default_chart_of_accounts(db)

    prov = InsuranceProvider(name="Hygeia", code="HYG")
    db.add(prov)
    db.flush()
    plan = HmoPlan(insurance_provider_id=prov.id, name="Hygeia Gold", code="HYG-G",
                   coverage_type=PlanCoverageType.FEE_FOR_SERVICE,
                   default_coverage_percent=Decimal("90"),
                   default_copay_flat=Decimal("500"))
    db.add(plan)
    db.flush()
    db.add(HmoPlanBenefit(hmo_plan_id=plan.id, category="PHARMACY",
                          coverage_percent=Decimal("50"), copay_flat=Decimal("0")))
    svc = BillableService(code="CONS-GP", name="GP Consultation",
                          category="CONSULTATION", default_price=Decimal("10000"))
    db.add(svc)
    db.flush()
    db.add(HmoTariff(hmo_plan_id=plan.id, billable_service_id=svc.id,
                     agreed_price=Decimal("8000")))
    patient = Patient(global_patient_id="GPID-1", hospital_number="HN-1",
                      first_name="Ada", last_name="Obi", gender=Gender.FEMALE)
    db.add(patient)
    db.flush()
    pi = PatientInsurance(patient_id=patient.id, insurance_provider_id=prov.id,
                          policy_number="POL-1", hmo_plan_id=plan.id,
                          policy_status=InsurancePolicyStatus.ACTIVE)
    db.add(pi)
    db.flush()
    return prov, plan, svc, patient, pi


def test_coverage_engine_split_with_tariff_and_copay(db):
    from app.services.coverage_engine import CoverageEngine
    prov, plan, svc, patient, pi = _mk_world(db)
    engine = CoverageEngine(db)
    d = engine.evaluate(enrollment=pi, unit_price=Decimal("10000"),
                        billable_service_id=svc.id)
    # Tariff reprices 10,000 -> 8,000; 90% = 7,200; minus 500 flat copay = 6,700
    assert d.unit_price == Decimal("8000.00")
    assert d.covered_amount == Decimal("6700.00")
    assert d.patient_amount == Decimal("1300.00")
    assert d.is_covered


def test_pharmacy_category_benefit(db):
    from app.services.coverage_engine import CoverageEngine
    prov, plan, svc, patient, pi = _mk_world(db)
    d = CoverageEngine(db).evaluate(enrollment=pi, unit_price=Decimal("2000"),
                                    category="PHARMACY")
    assert d.covered_amount == Decimal("1000.00")
    assert d.patient_amount == Decimal("1000.00")


def test_charge_capture_stamps_split(db):
    from app.utils.charge_capture import add_charge
    prov, plan, svc, patient, pi = _mk_world(db)
    billing = Billing(patient_id=patient.id, patient_insurance_id=pi.id,
                      billing_no="B-1",
                      billing_date=datetime.now(timezone.utc), status="OPEN",
                      gross_amount=Decimal("0"), discount_amount=Decimal("0"),
                      net_amount=Decimal("0"))
    db.add(billing)
    db.flush()
    item = add_charge(db, billing=billing, service_name="GP Consultation",
                      unit_price=Decimal("10000"), billable_service_id=svc.id,
                      source_reference="TEST:1")
    assert item.unit_price == Decimal("8000.00")       # tariff applied
    assert item.covered_amount == Decimal("6700.00")
    assert item.patient_amount == Decimal("1300.00")
    assert item.is_covered is True


def test_capitation_lifecycle_and_posting(db):
    from app.models.finance_models import HmoPlan
    from app.services.capitation_service import CapitationService
    from app.services.posting_rules_service import PostingRulesService
    prov, plan, svc, patient, pi = _mk_world(db)
    plan.coverage_type = PlanCoverageType.CAPITATION
    db.flush()
    cap = CapitationService(db)
    c = cap.upsert_contract(insurance_provider_id=prov.id, hmo_plan_id=plan.id,
                            rate_per_enrollee=Decimal("750"),
                            effective_from=date(2026, 1, 1))
    line = cap.run_month(contract_id=c["id"], period_code="2026-09")
    assert line["enrollee_count"] == 1
    assert Decimal(line["expected_amount"]) == Decimal("750")
    line = cap.confirm_schedule(line["id"])
    out = cap.record_payment(line_id=line["id"], amount=Decimal("500"),
                             paid_at=date(2026, 9, 25), reference="XH/09")
    assert out["schedule_line"]["status"] == "PARTIALLY_PAID"

    swept = PostingRulesService(db).sweep_extended()
    refs = set(swept["refs"])
    assert any(r.startswith("capitation_schedule:") for r in refs)
    assert any(r.startswith("capitation_payment:") for r in refs)
    # idempotent
    again = PostingRulesService(db).sweep_extended()
    assert again["created"] == 0

    report = cap.utilization_report(provider_id=prov.id,
                                    period_from="2026-09", period_to="2026-09")
    assert Decimal(report["expected_capitation"]) == Decimal("750")
    assert Decimal(report["received_capitation"]) == Decimal("500")


def test_trial_balance_balances_after_flows(db):
    from app.services.accounting_service import AccountingService
    from app.services.banking_service import BankingService
    prov, plan, svc, patient, pi = _mk_world(db)
    banking = BankingService(db)
    acct = banking.create_account(name="GTB Main", bank_name="GTBank",
                                  account_number="0123456789", is_default=True)
    banking.record_deposit(bank_account_id=acct["id"], amount=Decimal("100000"),
                           deposit_date=date(2026, 8, 1), reference="DEP-1")
    tb = AccountingService(db).trial_balance()
    assert tb["balanced"] is True
    assert Decimal(tb["total_debit"]) == Decimal(tb["total_credit"])
    assert Decimal(tb["total_debit"]) > 0


def test_bank_reconciliation_auto_match(db):
    from app.services.banking_service import BankingService
    prov, plan, svc, patient, pi = _mk_world(db)
    b = BankingService(db)
    acct = b.create_account(name="Zenith Ops")
    b.record_deposit(bank_account_id=acct["id"], amount=Decimal("50000"),
                     deposit_date=date(2026, 8, 10), reference="DEP-9")
    csv_content = (b"date,description,reference,debit,credit\n"
                   b"2026-08-11,CASH DEPOSIT,DEP-9,50000,0\n"
                   b"2026-08-12,COT CHARGE,CHG,0,150\n")
    imp = b.import_statement_csv(bank_account_id=acct["id"], content=csv_content)
    assert imp["lines"] == 2
    rec = b.start_reconciliation(bank_account_id=acct["id"],
                                 period_from=date(2026, 8, 1),
                                 period_to=date(2026, 8, 31),
                                 statement_closing_balance=Decimal("49850"))
    assert rec["auto_matched"] == 1          # the deposit matches
    assert len(rec["unmatched_statement_lines"]) == 1  # the bank charge
    entry = b.add_adjustment(rec["id"], kind="BANK_CHARGE", amount=Decimal("150"),
                             adj_date=date(2026, 8, 12))
    assert entry["status"] == "POSTED"
    out = b.auto_match(rec["id"])
    db.commit()
    assert out["matched"] == 1
    report = b.complete_reconciliation(rec["id"])
    assert report["status"] == "COMPLETED"
    assert Decimal(report["book_closing_balance"]) == Decimal("49850")


def test_credit_note_and_write_off(db):
    from app.models.all_models import Invoice, InvoiceItem
    from app.core.enums import InvoiceStatus
    from app.services.ar_ops_service import ArOpsService
    prov, plan, svc, patient, pi = _mk_world(db)
    inv = Invoice(patient_id=patient.id, invoice_no="INV-1",
                  status=InvoiceStatus.ISSUED,
                  invoice_date=datetime.now(timezone.utc),
                  subtotal_amount=Decimal("5000"), total_amount=Decimal("5000"),
                  amount_paid=Decimal("0"), balance_due=Decimal("5000"))
    db.add(inv)
    db.flush()
    db.add(InvoiceItem(invoice_id=inv.id, service_name="Dressing",
                       quantity=Decimal("1"), unit_price=Decimal("5000"),
                       line_total=Decimal("5000")))
    db.flush()
    ar = ArOpsService(db)
    cn = ar.create_credit_note(invoice_id=inv.id, reason="Overbilled",
                               items=[{"amount": Decimal("2000")}])
    cn = ar.issue_credit_note(cn["id"])
    assert cn["status"] in ("ISSUED", "APPLIED")
    db.refresh(inv)
    assert inv.balance_due == Decimal("3000.00")
    out = ar.write_off_invoice(invoice_id=inv.id, reason="Bad debt")
    assert Decimal(out["balance_due"]) == Decimal("0")


def test_claim_posting_and_write_off_flow(db):
    from app.models.all_models import InsuranceClaim
    from app.core.enums import InsuranceClaimStatus
    from app.services.posting_rules_service import PostingRulesService
    from app.services.remittance_service import RemittanceService
    prov, plan, svc, patient, pi = _mk_world(db)
    claim = InsuranceClaim(claim_no="CLM-1", patient_id=patient.id,
                           patient_insurance_id=pi.id,
                           insurance_provider_id=prov.id,
                           status=InsuranceClaimStatus.APPROVED,
                           billed_amount=Decimal("10000"),
                           approved_amount=Decimal("9000"),
                           service_date=date(2026, 8, 1))
    db.add(claim)
    db.flush()
    swept = PostingRulesService(db).sweep_extended()
    assert f"insurance_claim:{claim.id}" in swept["refs"]

    rem = RemittanceService(db)
    adv = rem.create_advice(insurance_provider_id=prov.id,
                            total_amount=Decimal("8000"),
                            received_at=date(2026, 9, 1), reference="REM-X")
    sug = rem.suggest_matches(adv["id"])
    assert sug["open_claims"][0]["claim_id"] == claim.id
    adv = rem.allocate(adv["id"], allocations=[
        {"claim_id": claim.id, "amount": Decimal("8000")}])
    assert adv["status"] == "ALLOCATED"
    # the HMO short-paid: write off the uncollected 1,000 of the approved 9,000
    out = rem.write_off_claim(claim_id=claim.id)
    assert Decimal(out["amount"]) == Decimal("1000")
    swept = PostingRulesService(db).sweep_extended()
    assert any(r.startswith("claim_write_off:") for r in swept["refs"])
    # payer statement closes at zero
    stmt = rem.payer_statement(prov.id)
    assert Decimal(stmt["closing_balance"]) == Decimal("0")
