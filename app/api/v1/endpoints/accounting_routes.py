# app/api/v1/endpoints/accounting_routes.py
from __future__ import annotations

"""
Accounting / General Ledger API (staff, JWT + permission gated).

Read = ACCOUNTING_READ · journal write = ACCOUNTING_POST ·
periods & auto-posting = ACCOUNTING_MANAGE.
"""

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models.all_models import User
from app.services.accounting_service import AccountingService
from app.services.finance_ops_service import BudgetService, FixedAssetService, VendorService

router = APIRouter(prefix="/accounting", tags=["Accounting"])

Reader = Annotated[User, Depends(require_permission("ACCOUNTING_READ", "ACCOUNTING_POST", "ACCOUNTING_MANAGE"))]
Poster = Annotated[User, Depends(require_permission("ACCOUNTING_POST", "ACCOUNTING_MANAGE"))]
Manager = Annotated[User, Depends(require_permission("ACCOUNTING_MANAGE"))]


class JournalLineSchema(BaseModel):
    account_id: int
    debit: float = Field(0, ge=0)
    credit: float = Field(0, ge=0)
    description: Optional[str] = Field(None, max_length=500)


class JournalEntryCreateSchema(BaseModel):
    entry_date: date
    memo: Optional[str] = Field(None, max_length=1000)
    lines: list[JournalLineSchema] = Field(..., min_length=2)
    auto_post: bool = False


class ReverseSchema(BaseModel):
    memo: Optional[str] = Field(None, max_length=1000)


def _svc(db: Session = Depends(get_db)) -> AccountingService:
    return AccountingService(db)


# ---------------- Journal entries ----------------

@router.get("/journal-entries", summary="List journal entries")
def list_entries(
    actor: Reader,
    svc: Annotated[AccountingService, Depends(_svc)],
    entry_status: Optional[str] = Query(None, alias="status"),
    source: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    return {"success": True, **svc.list_entries(
        status=entry_status, source=source, date_from=date_from, date_to=date_to,
        page=page, page_size=page_size)}


@router.post("/journal-entries", status_code=status.HTTP_201_CREATED,
             summary="Create a journal entry (balanced double-entry)")
def create_entry(payload: JournalEntryCreateSchema, actor: Poster,
                 svc: Annotated[AccountingService, Depends(_svc)]):
    entry = svc.create_entry(
        entry_date=payload.entry_date, memo=payload.memo,
        lines=[l.model_dump() for l in payload.lines],
        user_id=getattr(actor, "id", None), auto_post=payload.auto_post)
    return {"success": True, "entry": entry}


@router.get("/journal-entries/{entry_id}", summary="Journal entry detail")
def get_entry(entry_id: int, actor: Reader, svc: Annotated[AccountingService, Depends(_svc)]):
    return {"success": True, "entry": svc.get_entry(entry_id)}


@router.post("/journal-entries/{entry_id}/post", summary="Post a draft entry")
def post_entry(entry_id: int, actor: Poster, svc: Annotated[AccountingService, Depends(_svc)]):
    return {"success": True, "entry": svc.post_entry(entry_id, user_id=getattr(actor, "id", None))}


@router.post("/journal-entries/{entry_id}/reverse", summary="Reverse a posted entry")
def reverse_entry(entry_id: int, payload: ReverseSchema, actor: Poster,
                  svc: Annotated[AccountingService, Depends(_svc)]):
    return {"success": True, "entry": svc.reverse_entry(
        entry_id, user_id=getattr(actor, "id", None), memo=payload.memo)}


@router.delete("/journal-entries/{entry_id}", summary="Delete a draft entry")
def delete_entry(entry_id: int, actor: Poster, svc: Annotated[AccountingService, Depends(_svc)]):
    return {"success": True, **svc.delete_draft(entry_id)}


@router.post("/auto-post", summary="Sweep operational money events into the ledger (idempotent)")
def auto_post(actor: Manager, svc: Annotated[AccountingService, Depends(_svc)]):
    return {"success": True, **svc.auto_post_operations(user_id=getattr(actor, "id", None))}


# ---------------- Periods ----------------

@router.get("/periods", summary="List accounting periods")
def list_periods(actor: Reader, svc: Annotated[AccountingService, Depends(_svc)]):
    return {"success": True, "items": svc.list_periods()}


@router.post("/periods/{period_id}/close", summary="Close a period")
def close_period(period_id: int, actor: Manager, svc: Annotated[AccountingService, Depends(_svc)]):
    return {"success": True, "period": svc.set_period_status(
        period_id, close=True, user_id=getattr(actor, "id", None))}


@router.post("/periods/{period_id}/reopen", summary="Reopen a period")
def reopen_period(period_id: int, actor: Manager, svc: Annotated[AccountingService, Depends(_svc)]):
    return {"success": True, "period": svc.set_period_status(
        period_id, close=False, user_id=getattr(actor, "id", None))}


# ---------------- Ledger & reports ----------------

@router.get("/ledger/{account_id}", summary="Account ledger with running balance")
def ledger(account_id: int, actor: Reader, svc: Annotated[AccountingService, Depends(_svc)],
           date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None)):
    return {"success": True, **svc.account_ledger(account_id, date_from=date_from, date_to=date_to)}


@router.get("/reports/trial-balance", summary="Trial balance")
def trial_balance(actor: Reader, svc: Annotated[AccountingService, Depends(_svc)],
                  date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None)):
    return {"success": True, **svc.trial_balance(date_from=date_from, date_to=date_to)}


@router.get("/reports/profit-and-loss", summary="Profit & loss (income statement)")
def profit_and_loss(actor: Reader, svc: Annotated[AccountingService, Depends(_svc)],
                    date_from: date = Query(...), date_to: date = Query(...)):
    return {"success": True, **svc.profit_and_loss(date_from=date_from, date_to=date_to)}


@router.get("/reports/balance-sheet", summary="Balance sheet")
def balance_sheet(actor: Reader, svc: Annotated[AccountingService, Depends(_svc)],
                  as_of: date = Query(...)):
    return {"success": True, **svc.balance_sheet(as_of=as_of)}


# ---------------- Accounts payable ----------------

class VendorSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None


class BillCreateSchema(BaseModel):
    vendor_id: int
    bill_date: date
    due_date: Optional[date] = None
    total_amount: float = Field(..., gt=0)
    expense_account_id: int
    description: Optional[str] = Field(None, max_length=1000)
    bill_no: Optional[str] = Field(None, max_length=100)


class BillPaySchema(BaseModel):
    amount: float = Field(..., gt=0)
    paid_at: date
    payment_method: Optional[str] = "BANK_TRANSFER"
    reference: Optional[str] = Field(None, max_length=120)


def _vendors(db: Session = Depends(get_db)) -> VendorService:
    return VendorService(db)


@router.get("/vendors", summary="List vendors")
def list_vendors(actor: Reader, svc: Annotated[VendorService, Depends(_vendors)],
                 search: Optional[str] = Query(None)):
    return {"success": True, "items": svc.list_vendors(search=search)}


@router.post("/vendors", status_code=status.HTTP_201_CREATED, summary="Create a vendor")
def create_vendor(payload: VendorSchema, actor: Poster, svc: Annotated[VendorService, Depends(_vendors)]):
    return {"success": True, "vendor": svc.upsert_vendor(**payload.model_dump())}


@router.put("/vendors/{vendor_id}", summary="Update a vendor")
def update_vendor(vendor_id: int, payload: VendorSchema, actor: Poster,
                  svc: Annotated[VendorService, Depends(_vendors)]):
    return {"success": True, "vendor": svc.upsert_vendor(vendor_id=vendor_id, **payload.model_dump(exclude_unset=True))}


@router.get("/vendor-bills", summary="List vendor bills")
def list_bills(actor: Reader, svc: Annotated[VendorService, Depends(_vendors)],
               bill_status: Optional[str] = Query(None, alias="status"),
               vendor_id: Optional[int] = Query(None)):
    return {"success": True, "items": svc.list_bills(status=bill_status, vendor_id=vendor_id)}


@router.post("/vendor-bills", status_code=status.HTTP_201_CREATED,
             summary="Book a vendor bill (posts Dr expense / Cr Accounts Payable)")
def create_bill(payload: BillCreateSchema, actor: Poster,
                svc: Annotated[VendorService, Depends(_vendors)]):
    return {"success": True, "bill": svc.create_bill(
        user_id=getattr(actor, "id", None), **payload.model_dump())}


@router.post("/vendor-bills/{bill_id}/pay",
             summary="Pay a bill (posts Dr Accounts Payable / Cr cash)")
def pay_bill(bill_id: int, payload: BillPaySchema, actor: Poster,
             svc: Annotated[VendorService, Depends(_vendors)]):
    return {"success": True, "bill": svc.pay_bill(
        bill_id=bill_id, user_id=getattr(actor, "id", None), **payload.model_dump())}


@router.get("/reports/ap-aging", summary="Accounts-payable ageing")
def ap_aging(actor: Reader, svc: Annotated[VendorService, Depends(_vendors)],
             as_of: Optional[date] = Query(None)):
    return {"success": True, **svc.ap_aging(as_of=as_of)}


@router.get("/reports/ar-aging", summary="Accounts-receivable ageing (patient/insurer invoices)")
def ar_aging(actor: Reader, svc: Annotated[AccountingService, Depends(_svc)],
             as_of: Optional[date] = Query(None)):
    return {"success": True, **svc.ar_aging(as_of=as_of)}


# ---------------- Fixed assets ----------------

class AssetCreateSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    category: Optional[str] = None
    acquisition_date: date
    cost: float = Field(..., gt=0)
    salvage_value: float = Field(0, ge=0)
    useful_life_months: int = Field(..., gt=0, le=1200)
    code: Optional[str] = None
    book_acquisition: bool = False
    funding_account_id: Optional[int] = None


class DepreciationRunSchema(BaseModel):
    period_code: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}$")


def _assets(db: Session = Depends(get_db)) -> FixedAssetService:
    return FixedAssetService(db)


@router.get("/fixed-assets", summary="Fixed-asset register")
def list_assets(actor: Reader, svc: Annotated[FixedAssetService, Depends(_assets)]):
    return {"success": True, "items": svc.list_assets()}


@router.post("/fixed-assets", status_code=status.HTTP_201_CREATED, summary="Register a fixed asset")
def create_asset(payload: AssetCreateSchema, actor: Poster,
                 svc: Annotated[FixedAssetService, Depends(_assets)]):
    return {"success": True, "asset": svc.create_asset(
        user_id=getattr(actor, "id", None), **payload.model_dump())}


@router.post("/fixed-assets/run-depreciation",
             summary="Post monthly depreciation for all active assets (idempotent)")
def run_depreciation(payload: DepreciationRunSchema, actor: Manager,
                     svc: Annotated[FixedAssetService, Depends(_assets)]):
    return {"success": True, **svc.run_depreciation(
        period_code=payload.period_code, user_id=getattr(actor, "id", None))}


# ---------------- Budgets ----------------

class BudgetUpsertSchema(BaseModel):
    account_id: int
    period_code: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    amount: float = Field(..., ge=0)


def _budgets(db: Session = Depends(get_db)) -> BudgetService:
    return BudgetService(db)


@router.post("/budgets", summary="Set the budget for an account in a period")
def upsert_budget(payload: BudgetUpsertSchema, actor: Manager,
                  svc: Annotated[BudgetService, Depends(_budgets)]):
    return {"success": True, "budget": svc.upsert(**payload.model_dump())}


@router.get("/reports/budget-vs-actual", summary="Budget vs actual (revenue & expense accounts)")
def budget_vs_actual(actor: Reader, svc: Annotated[BudgetService, Depends(_budgets)],
                     date_from: date = Query(...), date_to: date = Query(...)):
    return {"success": True, **svc.budget_vs_actual(date_from=date_from, date_to=date_to)}


# ---------------- Year-end close ----------------

class YearCloseSchema(BaseModel):
    year: int = Field(..., ge=2000, le=2100)


@router.post("/close-year", summary="Post the year-end closing entry to retained earnings")
def close_year(payload: YearCloseSchema, actor: Manager,
               svc: Annotated[AccountingService, Depends(_svc)]):
    return {"success": True, **svc.close_fiscal_year(
        year=payload.year, user_id=getattr(actor, "id", None))}
