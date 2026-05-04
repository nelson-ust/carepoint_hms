"""
Tax-management endpoints.

Two audiences:

* **Tenant admin / finance** — configure tax types, rates, rules,
  exemptions; record withholding tax; trigger invoice tax computation.
* **Reports / audit** — read snapshot tax lines, tax audit log,
  withholding records.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser, CurrentActiveUser
from app.core.enums import (
    TaxApplicability,
    TaxExemptionScope,
    TaxKind,
    TaxPricingMode,
    TaxScope,
    WithholdingTaxStatus,
)
from app.models.all_models import (
    InvoiceTaxLine,
    TaxAuditLog,
    TaxExemption,
    TaxRate,
    TaxRule,
    TaxType,
    WithholdingTaxRecord,
)
from app.services.tax_service import TaxService


router = APIRouter(prefix="/tax", tags=["Tax Management"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TaxTypeCreateSchema(BaseModel):
    code: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=1, max_length=120)
    kind: TaxKind = TaxKind.OTHER
    description: Optional[str] = None
    country_code: Optional[str] = Field(None, min_length=2, max_length=2)
    is_withholding: bool = False
    is_active: bool = True


class TaxTypeUpdateSchema(BaseModel):
    name: Optional[str] = None
    kind: Optional[TaxKind] = None
    description: Optional[str] = None
    country_code: Optional[str] = None
    is_withholding: Optional[bool] = None
    is_active: Optional[bool] = None


class TaxTypeReadSchema(BaseModel):
    id: int
    code: str
    name: str
    kind: TaxKind
    description: Optional[str] = None
    country_code: Optional[str] = None
    is_withholding: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TaxRateCreateSchema(BaseModel):
    tax_type_id: int
    rate_percent: Decimal = Field(..., ge=0, le=100)
    effective_from: date
    effective_to: Optional[date] = None
    note: Optional[str] = None


class TaxRateReadSchema(BaseModel):
    id: int
    tax_type_id: int
    rate_percent: Decimal
    effective_from: date
    effective_to: Optional[date] = None
    note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TaxRuleCreateSchema(BaseModel):
    tax_type_id: int
    name: str
    scope: TaxScope = TaxScope.TENANT
    applicability: TaxApplicability = TaxApplicability.ALL
    match_values: Optional[list[str]] = None
    pricing_mode: TaxPricingMode = TaxPricingMode.EXCLUSIVE
    priority: int = 100
    facility_id: Optional[int] = None
    is_active: bool = True


class TaxRuleReadSchema(BaseModel):
    id: int
    tax_type_id: int
    name: str
    scope: TaxScope
    applicability: TaxApplicability
    match_values: Optional[list[str]] = None
    pricing_mode: TaxPricingMode
    priority: int
    facility_id: Optional[int] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TaxExemptionCreateSchema(BaseModel):
    tax_type_id: int
    scope: TaxExemptionScope
    target_id: int
    reason: Optional[str] = None
    starts_on: Optional[date] = None
    ends_on: Optional[date] = None
    supporting_document_url: Optional[str] = None


class TaxExemptionReadSchema(BaseModel):
    id: int
    tax_type_id: int
    scope: TaxExemptionScope
    target_id: int
    reason: Optional[str] = None
    starts_on: Optional[date] = None
    ends_on: Optional[date] = None
    supporting_document_url: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class InvoiceTaxLineReadSchema(BaseModel):
    id: int
    invoice_id: int
    invoice_item_id: Optional[int] = None
    tax_type_id: Optional[int] = None
    tax_type_code_snapshot: str
    tax_type_name_snapshot: str
    rate_percent_snapshot: Decimal
    taxable_base: Decimal
    tax_amount: Decimal
    pricing_mode: TaxPricingMode
    is_exempt: bool
    exemption_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class WHTRecordCreateSchema(BaseModel):
    tax_type_id: int
    payee_name: str
    gross_amount: Decimal = Field(..., ge=0)
    rate_percent: Optional[Decimal] = None
    related_invoice_id: Optional[int] = None
    related_payment_id: Optional[int] = None
    payee_tax_id: Optional[str] = None
    payee_kind: Optional[str] = None
    notes: Optional[str] = None


class WHTRecordReadSchema(BaseModel):
    id: int
    tax_type_id: int
    payee_name: str
    payee_tax_id: Optional[str] = None
    payee_kind: Optional[str] = None
    related_invoice_id: Optional[int] = None
    related_payment_id: Optional[int] = None
    gross_amount: Decimal
    rate_percent_snapshot: Decimal
    wht_amount: Decimal
    status: WithholdingTaxStatus
    deducted_at: Optional[datetime] = None
    remitted_at: Optional[datetime] = None
    certificate_no: Optional[str] = None
    certificate_url: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class WHTRemittanceSchema(BaseModel):
    certificate_no: Optional[str] = None
    certificate_url: Optional[str] = None


class TaxAuditLogReadSchema(BaseModel):
    id: int
    actor_user_id: Optional[int] = None
    entity: str
    entity_id: Optional[int] = None
    action: str
    before_data: Optional[dict[str, Any]] = None
    after_data: Optional[dict[str, Any]] = None
    occurred_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _service(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Optional[Any], Depends(lambda: None)] = None,
) -> TaxService:
    return TaxService(db, actor_user_id=getattr(actor, "id", None) if actor else None)


# ---------------------------------------------------------------------------
# Tax types
# ---------------------------------------------------------------------------


@router.get(
    "/types",
    response_model=list[TaxTypeReadSchema],
    summary="List tax types",
)
def list_types(
    _: CurrentActiveUser,
    service: Annotated[TaxService, Depends(_service)],
    only_active: bool = False,
):
    return service.list_tax_types(only_active=only_active)


@router.post(
    "/types",
    response_model=TaxTypeReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tax type (VAT, WHT, Service Tax, etc.)",
)
def create_type(
    payload: TaxTypeCreateSchema,
    _: AdminUser,
    service: Annotated[TaxService, Depends(_service)],
):
    return service.create_tax_type(**payload.model_dump())


@router.put(
    "/types/{tax_type_id}",
    response_model=TaxTypeReadSchema,
    summary="Update a tax type",
)
def update_type(
    tax_type_id: int,
    payload: TaxTypeUpdateSchema,
    _: AdminUser,
    service: Annotated[TaxService, Depends(_service)],
):
    return service.update_tax_type(tax_type_id, **payload.model_dump(exclude_none=True))


# ---------------------------------------------------------------------------
# Tax rates
# ---------------------------------------------------------------------------


@router.post(
    "/rates",
    response_model=TaxRateReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add an effective-dated tax rate",
)
def add_rate(
    payload: TaxRateCreateSchema,
    _: AdminUser,
    service: Annotated[TaxService, Depends(_service)],
):
    return service.add_rate(**payload.model_dump())


@router.get(
    "/rates",
    response_model=list[TaxRateReadSchema],
    summary="List tax rates",
)
def list_rates(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    tax_type_id: Optional[int] = None,
):
    q = db.query(TaxRate).filter(TaxRate.is_deleted.is_(False))
    if tax_type_id is not None:
        q = q.filter(TaxRate.tax_type_id == tax_type_id)
    return q.order_by(TaxRate.effective_from.desc()).all()


# ---------------------------------------------------------------------------
# Tax rules + exemptions
# ---------------------------------------------------------------------------


@router.post(
    "/rules",
    response_model=TaxRuleReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add a tax-applicability rule",
)
def add_rule(
    payload: TaxRuleCreateSchema,
    _: AdminUser,
    service: Annotated[TaxService, Depends(_service)],
):
    return service.add_rule(**payload.model_dump())


@router.get(
    "/rules",
    response_model=list[TaxRuleReadSchema],
    summary="List tax rules",
)
def list_rules(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    tax_type_id: Optional[int] = None,
):
    q = db.query(TaxRule).filter(TaxRule.is_deleted.is_(False))
    if tax_type_id is not None:
        q = q.filter(TaxRule.tax_type_id == tax_type_id)
    return q.order_by(TaxRule.priority.asc()).all()


@router.post(
    "/exemptions",
    response_model=TaxExemptionReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Mark an entity as tax-exempt",
)
def add_exemption(
    payload: TaxExemptionCreateSchema,
    _: AdminUser,
    service: Annotated[TaxService, Depends(_service)],
):
    return service.add_exemption(**payload.model_dump())


@router.get(
    "/exemptions",
    response_model=list[TaxExemptionReadSchema],
    summary="List tax exemptions",
)
def list_exemptions(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    tax_type_id: Optional[int] = None,
    only_active: bool = False,
):
    q = db.query(TaxExemption).filter(TaxExemption.is_deleted.is_(False))
    if tax_type_id is not None:
        q = q.filter(TaxExemption.tax_type_id == tax_type_id)
    if only_active:
        q = q.filter(TaxExemption.is_active.is_(True))
    return q.order_by(TaxExemption.id.desc()).all()


# ---------------------------------------------------------------------------
# Invoice tax computation + read
# ---------------------------------------------------------------------------


@router.post(
    "/invoices/{invoice_id}/compute",
    response_model=list[InvoiceTaxLineReadSchema],
    summary="Compute and snapshot tax lines for an invoice",
)
def compute_invoice_tax(
    invoice_id: int,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[TaxService, Depends(_service)],
):
    from app.models.all_models import Invoice

    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if inv is None:
        return []
    return service.compute_invoice_tax(inv)


@router.get(
    "/invoices/{invoice_id}/lines",
    response_model=list[InvoiceTaxLineReadSchema],
    summary="Read tax-line snapshots for an invoice",
)
def read_invoice_lines(
    invoice_id: int,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    return (
        db.query(InvoiceTaxLine)
        .filter(InvoiceTaxLine.invoice_id == invoice_id, InvoiceTaxLine.is_deleted.is_(False))
        .order_by(InvoiceTaxLine.id.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# Withholding tax
# ---------------------------------------------------------------------------


@router.post(
    "/withholding",
    response_model=WHTRecordReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record a withholding-tax deduction",
)
def record_withholding(
    payload: WHTRecordCreateSchema,
    _: AdminUser,
    service: Annotated[TaxService, Depends(_service)],
):
    return service.record_withholding(**payload.model_dump())


@router.get(
    "/withholding",
    response_model=list[WHTRecordReadSchema],
    summary="List withholding-tax records",
)
def list_withholding(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    wht_status: Optional[WithholdingTaxStatus] = None,
):
    q = db.query(WithholdingTaxRecord).filter(WithholdingTaxRecord.is_deleted.is_(False))
    if wht_status is not None:
        q = q.filter(WithholdingTaxRecord.status == wht_status)
    return q.order_by(WithholdingTaxRecord.id.desc()).all()


@router.post(
    "/withholding/{record_id}/remit",
    response_model=WHTRecordReadSchema,
    summary="Mark a WHT record as remitted (and optionally attach a certificate)",
)
def remit_withholding(
    record_id: int,
    payload: WHTRemittanceSchema,
    _: AdminUser,
    service: Annotated[TaxService, Depends(_service)],
):
    return service.mark_wht_remitted(
        record_id,
        certificate_no=payload.certificate_no,
        certificate_url=payload.certificate_url,
    )


# ---------------------------------------------------------------------------
# Audit log + reports
# ---------------------------------------------------------------------------


@router.get(
    "/audit-log",
    response_model=list[TaxAuditLogReadSchema],
    summary="List tax-configuration audit log entries",
)
def list_audit_log(
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    entity: Optional[str] = None,
    entity_id: Optional[int] = None,
):
    q = db.query(TaxAuditLog).filter(TaxAuditLog.is_deleted.is_(False))
    if entity is not None:
        q = q.filter(TaxAuditLog.entity == entity)
    if entity_id is not None:
        q = q.filter(TaxAuditLog.entity_id == entity_id)
    return q.order_by(TaxAuditLog.occurred_at.desc()).limit(500).all()


@router.get(
    "/reports/summary",
    summary="Tax summary report by period and tax type",
)
def tax_summary(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    period_start: date,
    period_end: date,
    tax_type_id: Optional[int] = None,
):
    from app.models.all_models import Invoice
    from sqlalchemy import func

    q = (
        db.query(
            InvoiceTaxLine.tax_type_code_snapshot.label("code"),
            InvoiceTaxLine.tax_type_name_snapshot.label("name"),
            func.sum(InvoiceTaxLine.taxable_base).label("taxable_base"),
            func.sum(InvoiceTaxLine.tax_amount).label("tax_amount"),
            func.count(InvoiceTaxLine.id).label("line_count"),
        )
        .join(Invoice, Invoice.id == InvoiceTaxLine.invoice_id)
        .filter(
            InvoiceTaxLine.is_deleted.is_(False),
            Invoice.invoice_date >= datetime.combine(period_start, datetime.min.time()),
            Invoice.invoice_date <= datetime.combine(period_end, datetime.max.time()),
        )
        .group_by(
            InvoiceTaxLine.tax_type_code_snapshot,
            InvoiceTaxLine.tax_type_name_snapshot,
        )
    )
    if tax_type_id is not None:
        q = q.filter(InvoiceTaxLine.tax_type_id == tax_type_id)

    rows = q.all()
    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "summary": [
            {
                "code": r.code,
                "name": r.name,
                "taxable_base": float(r.taxable_base or 0),
                "tax_amount": float(r.tax_amount or 0),
                "line_count": int(r.line_count or 0),
            }
            for r in rows
        ],
    }
