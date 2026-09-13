# app/api/v1/endpoints/banking_routes.py
from __future__ import annotations

"""
Bank & cash management API: bank accounts, deposits/transfers, statement
import, reconciliations, petty cash and cashier sessions.

Read = ACCOUNTING_READ · money movements = ACCOUNTING_POST ·
reconciliation & configuration = ACCOUNTING_MANAGE.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models.all_models import User

router = APIRouter(prefix="/banking", tags=["Banking & Cash"])

Reader = Annotated[User, Depends(require_permission("ACCOUNTING_READ", "ACCOUNTING_POST", "ACCOUNTING_MANAGE"))]
Poster = Annotated[User, Depends(require_permission("ACCOUNTING_POST", "ACCOUNTING_MANAGE"))]
Manager = Annotated[User, Depends(require_permission("ACCOUNTING_MANAGE"))]
Db = Annotated[Session, Depends(get_db)]


def _uid(actor) -> Optional[int]:
    return getattr(actor, "id", None)


class BankAccountSchema(BaseModel):
    name: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    is_default: Optional[bool] = None
    ledger_code: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class DepositSchema(BaseModel):
    bank_account_id: int
    amount: Decimal = Field(..., gt=0)
    deposit_date: date
    reference: Optional[str] = None


class TransferSchema(BaseModel):
    from_bank_account_id: int
    to_bank_account_id: int
    amount: Decimal = Field(..., gt=0)
    transfer_date: date
    reference: Optional[str] = None


class ReconciliationStartSchema(BaseModel):
    bank_account_id: int
    period_from: date
    period_to: date
    statement_closing_balance: Optional[Decimal] = None


class ManualMatchSchema(BaseModel):
    statement_line_id: int
    journal_line_id: Optional[int] = None  # None = unmatch


class AdjustmentSchema(BaseModel):
    kind: str = Field(..., pattern="^(BANK_CHARGE|INTEREST|bank_charge|interest)$")
    amount: Decimal = Field(..., gt=0)
    adj_date: Optional[date] = None
    description: Optional[str] = None


class FloatCreateSchema(BaseModel):
    name: str
    custodian_user_id: Optional[int] = None


class TopUpSchema(BaseModel):
    amount: Decimal = Field(..., gt=0)
    bank_account_id: Optional[int] = None
    top_up_date: Optional[date] = None


class VoucherSchema(BaseModel):
    amount: Decimal = Field(..., gt=0)
    description: str
    expense_account_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    receipt_url: Optional[str] = None
    spent_at: Optional[date] = None


class VoucherDecisionSchema(BaseModel):
    approve: bool


class SessionOpenSchema(BaseModel):
    opening_float: Decimal = Field(0, ge=0)
    service_delivery_point_id: Optional[int] = None


class SessionCloseSchema(BaseModel):
    counted_cash: Decimal = Field(..., ge=0)
    notes: Optional[str] = None


class AttachPaymentSchema(BaseModel):
    payment_id: Optional[int] = None
    billing_payment_id: Optional[int] = None


# ---------------- bank accounts ----------------

@router.get("/accounts", summary="Bank accounts with live ledger balances")
def list_accounts(actor: Reader, db: Db):
    from app.services.banking_service import BankingService
    return {"success": True, "items": BankingService(db).list_accounts()}


@router.post("/accounts", status_code=status.HTTP_201_CREATED, summary="Add a bank account")
def create_account(payload: BankAccountSchema, actor: Manager, db: Db):
    from app.services.banking_service import BankingService
    data = payload.model_dump(exclude_none=True)
    if not data.get("name"):
        from app.core.exceptions import BadRequestError
        raise BadRequestError("name is required.")
    return {"success": True, "account": BankingService(db).create_account(**data)}


@router.put("/accounts/{bank_account_id}", summary="Update a bank account")
def update_account(bank_account_id: int, payload: BankAccountSchema, actor: Manager, db: Db):
    from app.services.banking_service import BankingService
    return {"success": True, "account": BankingService(db).update_account(
        bank_account_id, **payload.model_dump(exclude_none=True))}


@router.post("/deposits", summary="Bank a cash-point deposit (Dr Bank / Cr Undeposited Funds)")
def record_deposit(payload: DepositSchema, actor: Poster, db: Db):
    from app.services.banking_service import BankingService
    return {"success": True, "entry": BankingService(db).record_deposit(
        bank_account_id=payload.bank_account_id, amount=payload.amount,
        deposit_date=payload.deposit_date, reference=payload.reference,
        user_id=_uid(actor))}


@router.post("/transfers", summary="Inter-account transfer")
def record_transfer(payload: TransferSchema, actor: Poster, db: Db):
    from app.services.banking_service import BankingService
    return {"success": True, "entry": BankingService(db).record_transfer(
        from_bank_account_id=payload.from_bank_account_id,
        to_bank_account_id=payload.to_bank_account_id,
        amount=payload.amount, transfer_date=payload.transfer_date,
        reference=payload.reference, user_id=_uid(actor))}


# ---------------- statements & reconciliation ----------------

@router.post("/accounts/{bank_account_id}/statements/import",
             summary="Import a CSV bank statement")
async def import_statement(bank_account_id: int, actor: Manager, db: Db,
                           file: UploadFile = File(...)):
    from app.services.banking_service import BankingService
    content = await file.read()
    return {"success": True, **BankingService(db).import_statement_csv(
        bank_account_id=bank_account_id, content=content,
        file_name=file.filename, user_id=_uid(actor))}


@router.get("/reconciliations", summary="Reconciliation sessions")
def list_recs(actor: Reader, db: Db, bank_account_id: Optional[int] = Query(None)):
    from app.services.banking_service import BankingService
    return {"success": True, "items": BankingService(db).list_reconciliations(
        bank_account_id=bank_account_id)}


@router.post("/reconciliations", status_code=status.HTTP_201_CREATED,
             summary="Start a reconciliation (auto-matches by amount+date)")
def start_rec(payload: ReconciliationStartSchema, actor: Manager, db: Db):
    from app.services.banking_service import BankingService
    return {"success": True, **BankingService(db).start_reconciliation(
        bank_account_id=payload.bank_account_id,
        period_from=payload.period_from, period_to=payload.period_to,
        statement_closing_balance=payload.statement_closing_balance)}


@router.get("/reconciliations/{rec_id}", summary="Reconciliation working report")
def rec_report(rec_id: int, actor: Reader, db: Db):
    from app.services.banking_service import BankingService
    return {"success": True, **BankingService(db).reconciliation_report(rec_id)}


@router.post("/reconciliations/{rec_id}/auto-match", summary="Re-run auto-matching")
def rec_auto_match(rec_id: int, actor: Manager, db: Db):
    from app.services.banking_service import BankingService
    svc = BankingService(db)
    out = svc.auto_match(rec_id)
    db.commit()
    return {"success": True, **out}


@router.post("/reconciliations/{rec_id}/match", summary="Manually match / unmatch a line")
def rec_manual_match(rec_id: int, payload: ManualMatchSchema, actor: Manager, db: Db):
    from app.services.banking_service import BankingService
    return {"success": True, **BankingService(db).manual_match(
        rec_id, statement_line_id=payload.statement_line_id,
        journal_line_id=payload.journal_line_id)}


@router.post("/reconciliations/{rec_id}/adjustments",
             summary="Book a bank charge / interest found on the statement")
def rec_adjustment(rec_id: int, payload: AdjustmentSchema, actor: Manager, db: Db):
    from app.services.banking_service import BankingService
    return {"success": True, "entry": BankingService(db).add_adjustment(
        rec_id, kind=payload.kind.upper(), amount=payload.amount,
        adj_date=payload.adj_date, description=payload.description,
        user_id=_uid(actor))}


@router.post("/reconciliations/{rec_id}/complete", summary="Finish the reconciliation")
def rec_complete(rec_id: int, actor: Manager, db: Db):
    from app.services.banking_service import BankingService
    return {"success": True, **BankingService(db).complete_reconciliation(
        rec_id, user_id=_uid(actor))}


# ---------------- petty cash ----------------

@router.get("/petty-cash/floats", summary="Petty cash floats")
def list_floats(actor: Reader, db: Db):
    from app.services.cash_ops_service import PettyCashService
    return {"success": True, "items": PettyCashService(db).list_floats()}


@router.post("/petty-cash/floats", status_code=status.HTTP_201_CREATED,
             summary="Create a petty cash float")
def create_float(payload: FloatCreateSchema, actor: Manager, db: Db):
    from app.services.cash_ops_service import PettyCashService
    return {"success": True, "float": PettyCashService(db).create_float(
        name=payload.name, custodian_user_id=payload.custodian_user_id)}


@router.post("/petty-cash/floats/{float_id}/top-up", summary="Fund the float from a bank account")
def top_up_float(float_id: int, payload: TopUpSchema, actor: Poster, db: Db):
    from app.services.cash_ops_service import PettyCashService
    return {"success": True, "float": PettyCashService(db).top_up(
        float_id, amount=payload.amount, bank_account_id=payload.bank_account_id,
        top_up_date=payload.top_up_date, user_id=_uid(actor))}


@router.get("/petty-cash/vouchers", summary="Petty cash vouchers")
def list_vouchers(actor: Reader, db: Db,
                  float_id: Optional[int] = Query(None),
                  voucher_status: Optional[str] = Query(None, alias="status")):
    from app.services.cash_ops_service import PettyCashService
    return {"success": True, "items": PettyCashService(db).list_vouchers(
        float_id=float_id, status=voucher_status)}


@router.post("/petty-cash/floats/{float_id}/vouchers",
             status_code=status.HTTP_201_CREATED, summary="Raise an expense voucher")
def create_voucher(float_id: int, payload: VoucherSchema, actor: Reader, db: Db):
    from app.services.cash_ops_service import PettyCashService
    return {"success": True, "voucher": PettyCashService(db).create_voucher(
        float_id, amount=payload.amount, description=payload.description,
        expense_account_id=payload.expense_account_id,
        cost_center_id=payload.cost_center_id, receipt_url=payload.receipt_url,
        spent_at=payload.spent_at, user_id=_uid(actor))}


@router.post("/petty-cash/vouchers/{voucher_id}/decide", summary="Approve / reject a voucher")
def decide_voucher(voucher_id: int, payload: VoucherDecisionSchema, actor: Manager, db: Db):
    from app.services.cash_ops_service import PettyCashService
    return {"success": True, "voucher": PettyCashService(db).decide_voucher(
        voucher_id, approve=payload.approve, user_id=_uid(actor))}


@router.post("/petty-cash/floats/{float_id}/retire",
             summary="Retire approved vouchers (posts the spend)")
def retire_float(float_id: int, actor: Manager, db: Db):
    from app.services.cash_ops_service import PettyCashService
    return {"success": True, **PettyCashService(db).retire(float_id, user_id=_uid(actor))}


# ---------------- cashier sessions ----------------

@router.get("/cashier-sessions", summary="Cashier sessions")
def list_sessions(actor: Reader, db: Db,
                  session_status: Optional[str] = Query(None, alias="status"),
                  day: Optional[date] = Query(None)):
    from app.services.cash_ops_service import CashierSessionService
    return {"success": True, "items": CashierSessionService(db).list_sessions(
        status=session_status, day=day)}


@router.get("/cashier-sessions/mine", summary="My open session")
def my_session(actor: Reader, db: Db):
    from app.services.cash_ops_service import CashierSessionService
    return {"success": True,
            "session": CashierSessionService(db).current_for_user(_uid(actor))}


@router.post("/cashier-sessions/open", status_code=status.HTTP_201_CREATED,
             summary="Open a cash-point shift")
def open_session(payload: SessionOpenSchema, actor: Reader, db: Db):
    from app.services.cash_ops_service import CashierSessionService
    return {"success": True, "session": CashierSessionService(db).open_session(
        cashier_user_id=_uid(actor), opening_float=payload.opening_float,
        service_delivery_point_id=payload.service_delivery_point_id)}


@router.post("/cashier-sessions/{session_id}/attach-payment",
             summary="Attach a taken payment to the session")
def attach_payment(session_id: int, payload: AttachPaymentSchema, actor: Reader, db: Db):
    from app.services.cash_ops_service import CashierSessionService
    return {"success": True, "session": CashierSessionService(db).attach_payment(
        session_id=session_id, payment_id=payload.payment_id,
        billing_payment_id=payload.billing_payment_id)}


@router.post("/cashier-sessions/{session_id}/close",
             summary="Close the shift with a counted-cash declaration (Z-report)")
def close_session(session_id: int, payload: SessionCloseSchema, actor: Reader, db: Db):
    from app.services.cash_ops_service import CashierSessionService
    return {"success": True, "session": CashierSessionService(db).close_session(
        session_id, counted_cash=payload.counted_cash, notes=payload.notes,
        user_id=_uid(actor))}


@router.get("/cashier-sessions/daily-summary", summary="End-of-day cash summary")
def daily_summary(actor: Reader, db: Db, day: Optional[date] = Query(None)):
    from app.services.cash_ops_service import CashierSessionService
    return {"success": True, **CashierSessionService(db).daily_summary(day=day)}
