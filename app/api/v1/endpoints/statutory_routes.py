# app/api/v1/endpoints/statutory_routes.py
from __future__ import annotations

"""
Statutory remittances API: liability positions, remittance recording (posts
to the ledger), the WHT register, and filing schedules (PAYE / PENSION /
NHF / WHT) as JSON or XLSX.

Read = ACCOUNTING_READ · record remittances & WHT = ACCOUNTING_POST /
ACCOUNTING_MANAGE.
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

router = APIRouter(prefix="/statutory", tags=["Statutory Remittances"])

Reader = Annotated[User, Depends(require_permission("ACCOUNTING_READ", "ACCOUNTING_POST", "ACCOUNTING_MANAGE"))]
Poster = Annotated[User, Depends(require_permission("ACCOUNTING_POST", "ACCOUNTING_MANAGE"))]
Db = Annotated[Session, Depends(get_db)]


def _uid(actor) -> Optional[int]:
    return getattr(actor, "id", None)


class RemittanceCreateSchema(BaseModel):
    remittance_type: str = Field(..., description="PAYE, PENSION, NHF, WHT, VAT, OTHER")
    period_code: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    paid_at: date
    amount: Optional[Decimal] = Field(
        None, gt=0, description="Blank = the full outstanding balance for the type.")
    bank_account_id: Optional[int] = None
    authority: Optional[str] = Field(None, max_length=150)
    pension_provider_id: Optional[int] = None
    reference: Optional[str] = Field(None, max_length=150)
    receipt_url: Optional[str] = None
    notes: Optional[str] = None
    wht_record_ids: Optional[list[int]] = Field(
        None, description="WHT only: register records covered (blank = all "
                          "un-remitted records deducted in the period).")


class ManualWhtSchema(BaseModel):
    payee_name: str = Field(..., max_length=255)
    gross_amount: Decimal = Field(..., gt=0)
    rate_percent: Decimal = Field(..., gt=0, lt=100)
    payee_tax_id: Optional[str] = Field(None, max_length=60)
    payee_kind: Optional[str] = Field(None, max_length=40)
    notes: Optional[str] = None


class WhtCertificateSchema(BaseModel):
    certificate_no: Optional[str] = Field(None, max_length=120)
    certificate_url: Optional[str] = Field(None, max_length=500)


@router.get("/positions", summary="Accrued vs remitted vs outstanding, per statutory type")
def positions(actor: Reader, db: Db):
    from app.services.statutory_service import StatutoryService
    return {"success": True, "items": StatutoryService(db).positions()}


@router.get("/remittances", summary="Remittances made")
def list_remittances(actor: Reader, db: Db,
                     remittance_type: Optional[str] = Query(None, alias="type"),
                     period_code: Optional[str] = Query(None)):
    from app.services.statutory_service import StatutoryService
    return {"success": True, "items": StatutoryService(db).list_remittances(
        remittance_type=remittance_type, period_code=period_code)}


@router.post("/remittances", status_code=status.HTTP_201_CREATED,
             summary="Record a remittance (posts Dr payable / Cr bank)")
def create_remittance(payload: RemittanceCreateSchema, actor: Poster, db: Db):
    from app.services.statutory_service import StatutoryService
    return {"success": True, "remittance": StatutoryService(db).create_remittance(
        **payload.model_dump(exclude_none=True), user_id=_uid(actor))}


@router.get("/wht/register", summary="WHT register (deductions at source)")
def wht_register(actor: Reader, db: Db,
                 period_code: Optional[str] = Query(None),
                 wht_status: Optional[str] = Query(None, alias="status")):
    from app.services.statutory_service import StatutoryService
    return {"success": True, "items": StatutoryService(db).wht_register(
        period_code=period_code, status=wht_status)}


@router.post("/wht/records", status_code=status.HTTP_201_CREATED,
             summary="Record WHT withheld outside the AP flow")
def manual_wht(payload: ManualWhtSchema, actor: Poster, db: Db):
    from app.services.statutory_service import (
        StatutoryService, get_or_create_wht_tax_type)
    from app.services.tax_service import TaxService
    tt = get_or_create_wht_tax_type(db)
    rec = TaxService(db).record_withholding(
        tax_type_id=tt.id, payee_name=payload.payee_name,
        gross_amount=payload.gross_amount, rate_percent=payload.rate_percent,
        payee_tax_id=payload.payee_tax_id, payee_kind=payload.payee_kind,
        notes=payload.notes)
    return {"success": True, "record_id": rec.id,
            "wht_amount": str(rec.wht_amount)}


@router.post("/wht/{record_id}/certificate", summary="Attach the WHT credit-note/certificate")
def wht_certificate(record_id: int, payload: WhtCertificateSchema, actor: Poster, db: Db):
    from app.services.tax_service import TaxService
    rec = TaxService(db).mark_wht_remitted(
        record_id, certificate_no=payload.certificate_no,
        certificate_url=payload.certificate_url)
    return {"success": True, "record_id": rec.id,
            "status": rec.status.value if hasattr(rec.status, "value") else rec.status}


@router.get("/schedules/{kind}",
            summary="Filing schedule (PAYE / PENSION / NHF / WHT); "
                    "append .xlsx to the kind for the workbook")
def schedule(kind: str, actor: Reader, db: Db, period_code: str = Query(...)):
    from app.services.statutory_service import StatutoryService
    svc = StatutoryService(db)
    if kind.lower().endswith(".xlsx"):
        name, blob = svc.schedule_xlsx(kind[:-5], period_code=period_code)
        return Response(
            content=blob,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{name}"'})
    return {"success": True, **svc.schedule(kind, period_code=period_code)}
