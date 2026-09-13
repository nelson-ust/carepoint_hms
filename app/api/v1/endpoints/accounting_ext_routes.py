# app/api/v1/endpoints/accounting_ext_routes.py
from __future__ import annotations

"""
Accounting-module completeness API: chart-of-accounts tree & system account
mapping, accounting config, opening balances, cost centers, cash flow
statement, general ledger (+XLSX), departmental P&L, AR segmentation,
pre-close checklist, posting status, audit trail, credit notes, refunds,
invoice write-offs, statements, vendor credit notes and AP payment runs.

Read = ACCOUNTING_READ · documents & postings = ACCOUNTING_POST ·
configuration, write-offs & close = ACCOUNTING_MANAGE.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models.all_models import User

router = APIRouter(prefix="/accounting-ext", tags=["Accounting Extensions"])

Reader = Annotated[User, Depends(require_permission("ACCOUNTING_READ", "ACCOUNTING_POST", "ACCOUNTING_MANAGE"))]
Poster = Annotated[User, Depends(require_permission("ACCOUNTING_POST", "ACCOUNTING_MANAGE"))]
Manager = Annotated[User, Depends(require_permission("ACCOUNTING_MANAGE"))]
Db = Annotated[Session, Depends(get_db)]


def _uid(actor) -> Optional[int]:
    return getattr(actor, "id", None)


class MappingSchema(BaseModel):
    key: str
    account_id: int


class ConfigSchema(BaseModel):
    opening_balance_date: Optional[date] = None
    journal_approval_threshold: Optional[Decimal] = Field(None, ge=0)
    disallowance_as_expense: Optional[bool] = None
    enforce_preauth_block: Optional[bool] = None
    require_eligibility_check: Optional[bool] = None


class AccountUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_account_id: Optional[int] = None
    is_postable: Optional[bool] = None
    cash_flow_category: Optional[str] = None
    is_active: Optional[bool] = None


class OpeningBalanceLine(BaseModel):
    account_id: int
    debit: Decimal = Field(0, ge=0)
    credit: Decimal = Field(0, ge=0)


class OpeningBalancesSchema(BaseModel):
    as_of: date
    balances: list[OpeningBalanceLine] = Field(..., min_length=1)


class CostCenterSchema(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    department_id: Optional[int] = None
    facility_id: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CreditNoteItemSchema(BaseModel):
    invoice_item_id: Optional[int] = None
    description: Optional[str] = None
    amount: Decimal = Field(..., gt=0)


class CreditNoteCreateSchema(BaseModel):
    invoice_id: int
    reason: Optional[str] = None
    items: list[CreditNoteItemSchema] = Field(..., min_length=1)


class RefundCreateSchema(BaseModel):
    amount: Decimal = Field(..., gt=0)
    patient_id: Optional[int] = None
    insurance_provider_id: Optional[int] = None
    invoice_id: Optional[int] = None
    credit_note_id: Optional[int] = None
    bank_account_id: Optional[int] = None
    petty_cash_float_id: Optional[int] = None
    reason: Optional[str] = None


class InvoiceWriteOffSchema(BaseModel):
    amount: Optional[Decimal] = Field(None, gt=0)
    reason: Optional[str] = None


class VendorCnSchema(BaseModel):
    vendor_id: int
    amount: Decimal = Field(..., gt=0)
    vendor_bill_id: Optional[int] = None
    reason: Optional[str] = None


class PaymentRunSchema(BaseModel):
    bill_ids: list[int] = Field(..., min_length=1)
    bank_account_id: int
    paid_at: Optional[date] = None


# ---------------- CoA, mapping, config ----------------

@router.get("/accounts/tree", summary="Chart of accounts as a hierarchy")
def account_tree(actor: Reader, db: Db):
    from app.services.accounting_ext_service import AccountingExtService
    return {"success": True, "tree": AccountingExtService(db).account_tree()}


@router.put("/accounts/{account_id}", summary="Update account (parent, postable, cash-flow class)")
def update_account(account_id: int, payload: AccountUpdateSchema, actor: Manager, db: Db):
    from app.services.accounting_ext_service import AccountingExtService
    return {"success": True, "account": AccountingExtService(db).update_account(
        account_id, **payload.model_dump(exclude_none=True))}


@router.get("/system-accounts", summary="System account mapping")
def list_mappings(actor: Reader, db: Db):
    from app.services.system_accounts_service import list_system_account_mappings
    out = list_system_account_mappings(db)
    db.commit()
    return {"success": True, "items": out}


@router.put("/system-accounts", summary="Repoint a system posting key")
def set_mapping(payload: MappingSchema, actor: Manager, db: Db):
    from app.services.system_accounts_service import set_system_account_mapping
    return {"success": True, "mapping": set_system_account_mapping(
        db, key=payload.key, account_id=payload.account_id)}


@router.get("/config", summary="Accounting configuration")
def get_config(actor: Reader, db: Db):
    from app.services.system_accounts_service import config_read, get_accounting_config
    out = config_read(get_accounting_config(db))
    db.commit()
    return {"success": True, "config": out}


@router.put("/config", summary="Update accounting configuration")
def update_config(payload: ConfigSchema, actor: Manager, db: Db):
    from app.services.system_accounts_service import update_accounting_config
    return {"success": True, "config": update_accounting_config(
        db, **payload.model_dump(exclude_none=True))}


@router.post("/opening-balances", summary="Load go-live opening balances")
def opening_balances(payload: OpeningBalancesSchema, actor: Manager, db: Db):
    from app.services.accounting_ext_service import AccountingExtService
    return {"success": True, "entry": AccountingExtService(db).set_opening_balances(
        as_of=payload.as_of,
        balances=[b.model_dump() for b in payload.balances],
        user_id=_uid(actor))}


@router.post("/seed-default-coa", summary="Install the default hospital chart of accounts")
def seed_coa(actor: Manager, db: Db):
    from app.seeds.accounting_seed import seed_default_chart_of_accounts
    out = seed_default_chart_of_accounts(db)
    db.commit()
    return {"success": True, **out}


@router.post("/seed-demo-hmos", summary="Install two demo HMOs (capitation + fee-for-service)")
def seed_demo(actor: Manager, db: Db):
    from app.seeds.accounting_seed import seed_demo_hmos
    out = seed_demo_hmos(db)
    db.commit()
    return {"success": True, **out}


# ---------------- cost centers ----------------

@router.get("/cost-centers", summary="Cost centers")
def list_cost_centers(actor: Reader, db: Db):
    from app.services.accounting_ext_service import AccountingExtService
    return {"success": True, "items": AccountingExtService(db).list_cost_centers()}


@router.post("/cost-centers", status_code=status.HTTP_201_CREATED, summary="Create a cost center")
def create_cost_center(payload: CostCenterSchema, actor: Manager, db: Db):
    from app.services.accounting_ext_service import AccountingExtService
    return {"success": True, "cost_center": AccountingExtService(db).upsert_cost_center(
        **payload.model_dump(exclude_none=True))}


@router.put("/cost-centers/{cost_center_id}", summary="Update a cost center")
def update_cost_center(cost_center_id: int, payload: CostCenterSchema, actor: Manager, db: Db):
    from app.services.accounting_ext_service import AccountingExtService
    return {"success": True, "cost_center": AccountingExtService(db).upsert_cost_center(
        cost_center_id=cost_center_id, **payload.model_dump(exclude_none=True))}


@router.post("/cost-centers/generate-from-departments",
             summary="One-click cost center per department")
def generate_cost_centers(actor: Manager, db: Db):
    from app.services.accounting_ext_service import AccountingExtService
    return {"success": True, **AccountingExtService(db).generate_from_departments()}


# ---------------- reports ----------------

@router.get("/reports/cash-flow", summary="Cash flow statement")
def cash_flow(actor: Reader, db: Db,
              date_from: date = Query(...), date_to: date = Query(...)):
    from app.services.accounting_ext_service import AccountingExtService
    return {"success": True, **AccountingExtService(db).cash_flow_statement(
        date_from=date_from, date_to=date_to)}


@router.get("/reports/general-ledger", summary="General ledger")
def general_ledger(actor: Reader, db: Db,
                   date_from: date = Query(...), date_to: date = Query(...),
                   account_id: Optional[int] = Query(None),
                   cost_center_id: Optional[int] = Query(None)):
    from app.services.accounting_ext_service import AccountingExtService
    return {"success": True, **AccountingExtService(db).general_ledger(
        date_from=date_from, date_to=date_to, account_id=account_id,
        cost_center_id=cost_center_id)}


@router.get("/reports/general-ledger.xlsx", summary="General ledger XLSX export")
def general_ledger_xlsx(actor: Reader, db: Db,
                        date_from: date = Query(...), date_to: date = Query(...),
                        account_id: Optional[int] = Query(None)):
    from app.services.accounting_ext_service import AccountingExtService
    name, blob = AccountingExtService(db).general_ledger_xlsx(
        date_from=date_from, date_to=date_to, account_id=account_id)
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/reports/departmental-pnl", summary="P&L per cost center")
def departmental_pnl(actor: Reader, db: Db,
                     date_from: date = Query(...), date_to: date = Query(...)):
    from app.services.accounting_ext_service import AccountingExtService
    return {"success": True, **AccountingExtService(db).departmental_pnl(
        date_from=date_from, date_to=date_to)}


@router.get("/reports/ar-segments", summary="AR split: patient / HMO / capitation")
def ar_segments(actor: Reader, db: Db):
    from app.services.accounting_ext_service import AccountingExtService
    return {"success": True, **AccountingExtService(db).ar_segments()}


@router.get("/periods/{period_id}/pre-close-checklist", summary="Ready-to-close check")
def pre_close(period_id: int, actor: Reader, db: Db):
    from app.services.accounting_ext_service import AccountingExtService
    return {"success": True, **AccountingExtService(db).pre_close_checklist(period_id)}


@router.get("/posting-status", summary="Auto-posting sweep status per source")
def posting_status(actor: Reader, db: Db):
    from app.services.accounting_ext_service import AccountingExtService
    return {"success": True, **AccountingExtService(db).posting_status()}


@router.get("/audit-log", summary="Accounting audit trail")
def audit_log(actor: Manager, db: Db,
              entity_type: Optional[str] = Query(None),
              entity_id: Optional[int] = Query(None),
              limit: int = Query(100, ge=1, le=500)):
    from app.models.finance_models import AccountingAuditLog
    q = db.query(AccountingAuditLog).filter(AccountingAuditLog.is_deleted.is_(False))
    if entity_type:
        q = q.filter(AccountingAuditLog.entity_type == entity_type)
    if entity_id:
        q = q.filter(AccountingAuditLog.entity_id == entity_id)
    rows = q.order_by(AccountingAuditLog.id.desc()).limit(limit).all()
    return {"success": True, "items": [{
        "id": r.id, "actor_user_id": r.actor_user_id, "action": r.action,
        "entity_type": r.entity_type, "entity_id": r.entity_id,
        "summary": r.summary, "detail": r.detail,
        "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
    } for r in rows]}


# ---------------- AR documents ----------------

@router.get("/credit-notes", summary="Credit notes")
def list_credit_notes(actor: Reader, db: Db,
                      invoice_id: Optional[int] = Query(None),
                      cn_status: Optional[str] = Query(None, alias="status")):
    from app.services.ar_ops_service import ArOpsService
    return {"success": True, "items": ArOpsService(db).list_credit_notes(
        invoice_id=invoice_id, status=cn_status)}


@router.post("/credit-notes", status_code=status.HTTP_201_CREATED,
             summary="Draft a credit note")
def create_credit_note(payload: CreditNoteCreateSchema, actor: Poster, db: Db):
    from app.services.ar_ops_service import ArOpsService
    return {"success": True, "credit_note": ArOpsService(db).create_credit_note(
        invoice_id=payload.invoice_id, reason=payload.reason,
        items=[i.model_dump() for i in payload.items], user_id=_uid(actor))}


@router.post("/credit-notes/{credit_note_id}/issue",
             summary="Issue the credit note (posts contra-revenue)")
def issue_credit_note(credit_note_id: int, actor: Manager, db: Db):
    from app.services.ar_ops_service import ArOpsService
    return {"success": True, "credit_note": ArOpsService(db).issue_credit_note(
        credit_note_id, user_id=_uid(actor))}


@router.get("/refunds", summary="Refunds")
def list_refunds(actor: Reader, db: Db,
                 refund_status: Optional[str] = Query(None, alias="status")):
    from app.services.ar_ops_service import ArOpsService
    return {"success": True, "items": ArOpsService(db).list_refunds(status=refund_status)}


@router.post("/refunds", status_code=status.HTTP_201_CREATED, summary="Raise a refund")
def create_refund(payload: RefundCreateSchema, actor: Poster, db: Db):
    from app.services.ar_ops_service import ArOpsService
    return {"success": True, "refund": ArOpsService(db).create_refund(
        **payload.model_dump(exclude_none=True), user_id=_uid(actor))}


@router.post("/refunds/{refund_id}/pay", summary="Pay a refund out")
def pay_refund(refund_id: int, actor: Manager, db: Db):
    from app.services.ar_ops_service import ArOpsService
    return {"success": True, "refund": ArOpsService(db).pay_refund(
        refund_id, user_id=_uid(actor))}


@router.post("/invoices/{invoice_id}/write-off", summary="Bad-debt write-off")
def write_off_invoice(invoice_id: int, payload: InvoiceWriteOffSchema, actor: Manager, db: Db):
    from app.services.ar_ops_service import ArOpsService
    return {"success": True, **ArOpsService(db).write_off_invoice(
        invoice_id=invoice_id, amount=payload.amount, reason=payload.reason,
        user_id=_uid(actor))}


@router.get("/patients/{patient_id}/statement", summary="Patient statement of account")
def patient_statement(patient_id: int, actor: Reader, db: Db,
                      date_from: Optional[date] = Query(None),
                      date_to: Optional[date] = Query(None)):
    from app.services.ar_ops_service import ArOpsService
    return {"success": True, **ArOpsService(db).patient_statement(
        patient_id, date_from=date_from, date_to=date_to)}


# ---------------- AP documents ----------------

@router.post("/vendor-credit-notes", status_code=status.HTTP_201_CREATED,
             summary="Record a vendor credit note")
def vendor_credit_note(payload: VendorCnSchema, actor: Poster, db: Db):
    from app.services.ar_ops_service import ArOpsService
    return {"success": True, "credit_note": ArOpsService(db).create_vendor_credit_note(
        vendor_id=payload.vendor_id, amount=payload.amount,
        vendor_bill_id=payload.vendor_bill_id, reason=payload.reason,
        user_id=_uid(actor))}


@router.get("/vendors/{vendor_id}/statement", summary="Vendor statement of account")
def vendor_statement(vendor_id: int, actor: Reader, db: Db):
    from app.services.ar_ops_service import ArOpsService
    return {"success": True, **ArOpsService(db).vendor_statement(vendor_id)}


@router.post("/payment-runs", summary="Pay several vendor bills from one bank account")
def payment_run(payload: PaymentRunSchema, actor: Manager, db: Db):
    from app.services.ar_ops_service import ArOpsService
    return {"success": True, **ArOpsService(db).payment_run(
        bill_ids=payload.bill_ids, bank_account_id=payload.bank_account_id,
        paid_at=payload.paid_at, user_id=_uid(actor))}
