# carepoint_hms/app/models/finance_models.py
from __future__ import annotations

"""
carepoint_hms.app.models.finance_models

HMO / health-insurance and advanced-accounting models added by the
"Robust HMO & Full Accounting" build. Kept in a dedicated module (imported
from ``app.models.all_models`` so every existing import path still sees one
registry) to avoid destabilising the 9,500-line core models file.

Covers:
- HMO plans, benefit rules and negotiated tariffs
- Eligibility verification records
- Capitation contracts, monthly schedules and capitation receipts
- Remittance advices with claim/capitation allocation lines
- Claim rejection reasons and disallowance write-offs
- System account mapping, accounting config and document sequences
- Cost centers, bank accounts, bank statement import + reconciliation
- Petty cash floats/vouchers and cashier sessions
- Credit notes, refunds, vendor credit notes
- Accounting audit log

All tables extend ``TenantTable`` (tenant database), so plain
``unique=True`` constraints are tenant-scoped by construction
(database-per-tenant architecture).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TenantTable
from app.core.enums import (
    BankReconciliationStatus,
    BenefitLimitPeriod,
    CapitationContractStatus,
    CapitationScheduleStatus,
    CashFlowCategory,
    CashierSessionStatus,
    CreditNoteStatus,
    EligibilityCheckMethod,
    EligibilityCheckResult,
    PettyCashVoucherStatus,
    PlanCoverageType,
    RefundStatus,
    RemittanceAdviceStatus,
)


# ============================================================
# HMO PLANS, BENEFITS AND TARIFFS
# ============================================================


class HmoPlan(TenantTable):
    """A benefit plan/scheme sold by an insurance provider (HMO)."""

    insurance_provider_id: Mapped[int] = mapped_column(
        ForeignKey("insurance_provider.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True, index=True)
    plan_tier: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # bronze/silver/gold/custom
    coverage_type: Mapped[PlanCoverageType] = mapped_column(
        Enum(PlanCoverageType), default=PlanCoverageType.FEE_FOR_SERVICE, nullable=False, index=True)

    default_coverage_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=100, nullable=False)
    default_copay_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    default_copay_flat: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    annual_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    per_visit_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    requires_referral: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    insurance_provider: Mapped["InsuranceProvider"] = relationship()  # noqa: F821
    benefits: Mapped[list["HmoPlanBenefit"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan")
    tariffs: Mapped[list["HmoTariff"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan")


class HmoPlanBenefit(TenantTable):
    """Coverage rule for a plan: either a whole service category or one
    specific billable service / drug. Resolution order at billing time:
    exact service match -> category match -> plan defaults."""

    hmo_plan_id: Mapped[int] = mapped_column(ForeignKey("hmo_plan.id"), nullable=False, index=True)
    #: e.g. CONSULTATION, PHARMACY, LAB, RADIOLOGY, PROCEDURE, ADMISSION,
    #: MATERNITY, DENTAL, OPTICAL, OTHER — free-form to stay tenant-extensible.
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    billable_service_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("billable_service.id"), nullable=True, index=True)
    drug_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drug.id"), nullable=True, index=True)

    coverage_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    copay_flat: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    limit_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    limit_period: Mapped[Optional[BenefitLimitPeriod]] = mapped_column(
        Enum(BenefitLimitPeriod), nullable=True)
    requires_preauth: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    plan: Mapped["HmoPlan"] = relationship(back_populates="benefits")
    billable_service: Mapped[Optional["BillableService"]] = relationship()  # noqa: F821


class HmoTariff(TenantTable):
    """Negotiated price list entry for one plan and one billable service or
    drug. Chargeable items on an insured visit price from here first, falling
    back to ``BillableService.default_price``."""

    hmo_plan_id: Mapped[int] = mapped_column(ForeignKey("hmo_plan.id"), nullable=False, index=True)
    billable_service_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("billable_service.id"), nullable=True, index=True)
    drug_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drug.id"), nullable=True, index=True)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    agreed_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)

    plan: Mapped["HmoPlan"] = relationship(back_populates="tariffs")
    billable_service: Mapped[Optional["BillableService"]] = relationship()  # noqa: F821

    __table_args__ = (
        CheckConstraint("agreed_price >= 0", name="ck_hmo_tariff_price_nonneg"),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="ck_hmo_tariff_valid_range"),
    )


class EligibilityCheck(TenantTable):
    """A front-desk (or API) verification that an enrollee is eligible."""

    patient_insurance_id: Mapped[int] = mapped_column(
        ForeignKey("patient_insurance.id"), nullable=False, index=True)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit.id"), nullable=True, index=True)
    checked_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    method: Mapped[EligibilityCheckMethod] = mapped_column(
        Enum(EligibilityCheckMethod), default=EligibilityCheckMethod.CARD, nullable=False)
    result: Mapped[EligibilityCheckResult] = mapped_column(
        Enum(EligibilityCheckResult), nullable=False, index=True)
    authorization_code: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    patient_insurance: Mapped["PatientInsurance"] = relationship()  # noqa: F821


class ClaimRejectionReason(TenantTable):
    """Tenant-editable lookup of structured claim rejection/denial codes."""

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)


class ClaimWriteOff(TenantTable):
    """Explicit write-off of a disallowed / uncollectible claim amount."""

    claim_id: Mapped[int] = mapped_column(ForeignKey("insurance_claim.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    reason_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    reason_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    written_off_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    claim: Mapped["InsuranceClaim"] = relationship()  # noqa: F821

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_claim_write_off_amount_pos"),
    )


# ============================================================
# CAPITATION
# ============================================================


class CapitationContract(TenantTable):
    """Monthly per-enrollee payment agreement with an HMO."""

    insurance_provider_id: Mapped[int] = mapped_column(
        ForeignKey("insurance_provider.id"), nullable=False, index=True)
    hmo_plan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("hmo_plan.id"), nullable=True, index=True)  # NULL = all capitation plans
    rate_per_enrollee: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    payment_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # day of month
    status: Mapped[CapitationContractStatus] = mapped_column(
        Enum(CapitationContractStatus), default=CapitationContractStatus.ACTIVE,
        nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    insurance_provider: Mapped["InsuranceProvider"] = relationship()  # noqa: F821
    plan: Mapped[Optional["HmoPlan"]] = relationship()
    schedule_lines: Mapped[list["CapitationScheduleLine"]] = relationship(
        back_populates="contract")

    __table_args__ = (
        CheckConstraint("rate_per_enrollee >= 0", name="ck_capitation_rate_nonneg"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_capitation_contract_range"),
        CheckConstraint(
            "payment_day IS NULL OR (payment_day >= 1 AND payment_day <= 31)",
            name="ck_capitation_payment_day"),
    )


class CapitationScheduleLine(TenantTable):
    """Snapshot of expected capitation for one contract in one month."""

    contract_id: Mapped[int] = mapped_column(
        ForeignKey("capitation_contract.id"), nullable=False, index=True)
    period_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM
    enrollee_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rate_per_enrollee: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    received_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    status: Mapped[CapitationScheduleStatus] = mapped_column(
        Enum(CapitationScheduleStatus), default=CapitationScheduleStatus.DRAFT,
        nullable=False, index=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Snapshot of the enrollee ids counted for this month (for variance work).
    enrollee_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    #: HMO's own imported enrollee list + computed variance, when uploaded.
    hmo_list_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    contract: Mapped["CapitationContract"] = relationship(back_populates="schedule_lines")
    payments: Mapped[list["CapitationPayment"]] = relationship(back_populates="schedule_line")

    __table_args__ = (
        UniqueConstraint("contract_id", "period_code",
                         name="uq_capitation_contract_period"),
        CheckConstraint("enrollee_count >= 0", name="ck_capitation_line_count_nonneg"),
        CheckConstraint("expected_amount >= 0", name="ck_capitation_line_expected_nonneg"),
        CheckConstraint("received_amount >= 0", name="ck_capitation_line_received_nonneg"),
    )


class CapitationPayment(TenantTable):
    """A (possibly partial) capitation receipt from the HMO."""

    schedule_line_id: Mapped[int] = mapped_column(
        ForeignKey("capitation_schedule_line.id"), nullable=False, index=True)
    remittance_advice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("remittance_advice.id"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    paid_at: Mapped[date] = mapped_column(Date, nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    bank_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_account.id"), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    schedule_line: Mapped["CapitationScheduleLine"] = relationship(back_populates="payments")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_capitation_payment_amount_pos"),
    )


# ============================================================
# REMITTANCES (bulk payer payments allocated to claims/capitation)
# ============================================================


class RemittanceAdvice(TenantTable):
    """Header for one bulk payment received from an HMO/payer."""

    insurance_provider_id: Mapped[int] = mapped_column(
        ForeignKey("insurance_provider.id"), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    received_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    bank_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_account.id"), nullable=True, index=True)
    document_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[RemittanceAdviceStatus] = mapped_column(
        Enum(RemittanceAdviceStatus), default=RemittanceAdviceStatus.DRAFT,
        nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    insurance_provider: Mapped["InsuranceProvider"] = relationship()  # noqa: F821
    lines: Mapped[list["RemittanceLine"]] = relationship(
        back_populates="advice", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("total_amount > 0", name="ck_remittance_total_pos"),
        CheckConstraint("allocated_amount >= 0", name="ck_remittance_allocated_nonneg"),
        CheckConstraint("allocated_amount <= total_amount",
                        name="ck_remittance_allocated_le_total"),
    )


class RemittanceLine(TenantTable):
    """Allocation of part of a remittance to one claim or capitation line."""

    remittance_advice_id: Mapped[int] = mapped_column(
        ForeignKey("remittance_advice.id"), nullable=False, index=True)
    claim_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("insurance_claim.id"), nullable=True, index=True)
    capitation_schedule_line_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("capitation_schedule_line.id"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    advice: Mapped["RemittanceAdvice"] = relationship(back_populates="lines")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_remittance_line_amount_pos"),
        CheckConstraint(
            "(claim_id IS NOT NULL AND capitation_schedule_line_id IS NULL) OR "
            "(claim_id IS NULL AND capitation_schedule_line_id IS NOT NULL)",
            name="ck_remittance_line_one_target"),
    )


# ============================================================
# ACCOUNTING: CONFIG, MAPPING, SEQUENCES, COST CENTERS
# ============================================================


class SystemAccountMapping(TenantTable):
    """Tenant-editable mapping of a logical posting key to a ledger account."""

    key: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    account: Mapped["Account"] = relationship()  # noqa: F821


class AccountingConfig(TenantTable):
    """Single-row accounting configuration for the tenant."""

    #: Go-live date; ordinary postings before it are rejected.
    opening_balance_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    #: Manual journal entries at/above this need a second-person approval.
    journal_approval_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    #: True -> disallowances post to an expense account; False -> contra-revenue.
    disallowance_as_expense: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    #: Warn (False) or hard-block (True) ordering when pre-auth is missing.
    enforce_preauth_block: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: Prompt for eligibility check at check-in for insured patients.
    require_eligibility_check: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DocumentSequence(TenantTable):
    """Concurrency-safe per-document-type number sequences (receipts,
    credit notes, refunds, remittances, ...). Rows are locked with
    SELECT ... FOR UPDATE while allocating."""

    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    prefix: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    next_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    padding: Mapped[int] = mapped_column(Integer, default=6, nullable=False)


class CostCenter(TenantTable):
    """Departmental accounting dimension carried on journal lines."""

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("department.id"), nullable=True, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("facility.id"), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ============================================================
# BANKING & CASH
# ============================================================


class BankAccount(TenantTable):
    """A physical bank (or mobile-money) account, linked to one CoA account."""

    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    bank_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    account_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    account: Mapped["Account"] = relationship()  # noqa: F821


class BankStatementImport(TenantTable):
    """One uploaded bank statement (CSV) for a bank account."""

    bank_account_id: Mapped[int] = mapped_column(
        ForeignKey("bank_account.id"), nullable=False, index=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    statement_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    statement_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    line_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    bank_account: Mapped["BankAccount"] = relationship()
    lines: Mapped[list["BankStatementLine"]] = relationship(
        back_populates="statement_import", cascade="all, delete-orphan")


class BankStatementLine(TenantTable):
    """A single statement row; carries its match state across reconciliations."""

    import_id: Mapped[int] = mapped_column(
        ForeignKey("bank_statement_import.id"), nullable=False, index=True)
    line_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    debit: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    credit: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    #: Journal entry LINE this statement row is matched to (None = unmatched).
    matched_journal_line_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("journal_entry_line.id"), nullable=True, index=True)
    reconciliation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_reconciliation.id"), nullable=True, index=True)
    matched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    statement_import: Mapped["BankStatementImport"] = relationship(back_populates="lines")

    __table_args__ = (
        CheckConstraint("debit >= 0", name="ck_stmt_line_debit_nonneg"),
        CheckConstraint("credit >= 0", name="ck_stmt_line_credit_nonneg"),
    )


class BankReconciliation(TenantTable):
    """A reconciliation working session for one bank account and period."""

    bank_account_id: Mapped[int] = mapped_column(
        ForeignKey("bank_account.id"), nullable=False, index=True)
    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date] = mapped_column(Date, nullable=False)
    statement_closing_balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    book_closing_balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    status: Mapped[BankReconciliationStatus] = mapped_column(
        Enum(BankReconciliationStatus), default=BankReconciliationStatus.IN_PROGRESS,
        nullable=False, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    bank_account: Mapped["BankAccount"] = relationship()

    __table_args__ = (
        CheckConstraint("period_to >= period_from", name="ck_bank_rec_period_range"),
    )


class PettyCashFloat(TenantTable):
    """An imprest float held by a custodian, linked to one CoA account."""

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    custodian_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False, index=True)
    float_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    account: Mapped["Account"] = relationship()  # noqa: F821
    vouchers: Mapped[list["PettyCashVoucher"]] = relationship(back_populates="float")


class PettyCashVoucher(TenantTable):
    """A petty-cash expense voucher against a float."""

    float_id: Mapped[int] = mapped_column(
        ForeignKey("petty_cash_float.id"), nullable=False, index=True)
    voucher_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    expense_account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), nullable=False)
    cost_center_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cost_center.id"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    receipt_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[PettyCashVoucherStatus] = mapped_column(
        Enum(PettyCashVoucherStatus), default=PettyCashVoucherStatus.PENDING,
        nullable=False, index=True)
    requested_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    spent_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    float: Mapped["PettyCashFloat"] = relationship(back_populates="vouchers")
    expense_account: Mapped["Account"] = relationship()  # noqa: F821

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_pc_voucher_amount_pos"),
    )


class CashierSession(TenantTable):
    """A cash-point shift: opening float, payments taken, counted close."""

    cashier_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    service_delivery_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service_delivery_point.id"), nullable=True, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    opening_float: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    expected_cash: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    counted_cash: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    variance: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    status: Mapped[CashierSessionStatus] = mapped_column(
        Enum(CashierSessionStatus), default=CashierSessionStatus.OPEN,
        nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ============================================================
# AR / AP DOCUMENTS
# ============================================================


class CreditNote(TenantTable):
    """Credit issued against a patient/payer invoice."""

    credit_note_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoice.id"), nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    applied_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    status: Mapped[CreditNoteStatus] = mapped_column(
        Enum(CreditNoteStatus), default=CreditNoteStatus.DRAFT, nullable=False, index=True)
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    invoice: Mapped["Invoice"] = relationship()  # noqa: F821
    items: Mapped[list["CreditNoteItem"]] = relationship(
        back_populates="credit_note", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_credit_note_total_nonneg"),
        CheckConstraint("applied_amount >= 0", name="ck_credit_note_applied_nonneg"),
        CheckConstraint("applied_amount <= total_amount",
                        name="ck_credit_note_applied_le_total"),
    )


class CreditNoteItem(TenantTable):
    credit_note_id: Mapped[int] = mapped_column(
        ForeignKey("credit_note.id"), nullable=False, index=True)
    invoice_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoice_item.id"), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)

    credit_note: Mapped["CreditNote"] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_credit_note_item_amount_pos"),
    )


class Refund(TenantTable):
    """Money returned to a patient/payer from a bank account or petty cash."""

    refund_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    patient_id: Mapped[Optional[int]] = mapped_column(ForeignKey("patient.id"), nullable=True, index=True)
    insurance_provider_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("insurance_provider.id"), nullable=True, index=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoice.id"), nullable=True, index=True)
    credit_note_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("credit_note.id"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    bank_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_account.id"), nullable=True)
    petty_cash_float_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("petty_cash_float.id"), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus), default=RefundStatus.PENDING, nullable=False, index=True)
    paid_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_refund_amount_pos"),
        CheckConstraint(
            "(bank_account_id IS NOT NULL AND petty_cash_float_id IS NULL) OR "
            "(bank_account_id IS NULL AND petty_cash_float_id IS NOT NULL)",
            name="ck_refund_one_source"),
    )


class VendorCreditNote(TenantTable):
    """Credit received from a vendor against a vendor bill."""

    credit_note_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendor.id"), nullable=False, index=True)
    vendor_bill_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vendor_bill.id"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    applied_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issued_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    vendor: Mapped["Vendor"] = relationship()  # noqa: F821

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_vendor_cn_amount_pos"),
        CheckConstraint("applied_amount >= 0", name="ck_vendor_cn_applied_nonneg"),
    )


# ============================================================
# STATUTORY REMITTANCES (PAYE, pension, NHF, WHT, VAT, ...)
# ============================================================


class StatutoryRemittance(TenantTable):
    """One payment of an accumulated statutory liability to its authority
    (FIRS, State IRS, a PFA, NHF, NSITF, ITF...). Posting clears the matching
    payable account: Dr <liability payable> / Cr Bank."""

    #: PAYE, PENSION, NHF, WHT, VAT, NSITF, ITF, OTHER — validated in the
    #: service against the type -> payable-account map.
    remittance_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    period_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM
    authority: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    pension_provider_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("pension_provider.id"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    paid_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    bank_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_account.id"), nullable=True, index=True)
    reference: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    receipt_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_statutory_remittance_amount_pos"),
    )


# ============================================================
# AUDIT
# ============================================================


class AccountingAuditLog(TenantTable):
    """Immutable trail of sensitive accounting/insurance actions."""

    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detail: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
