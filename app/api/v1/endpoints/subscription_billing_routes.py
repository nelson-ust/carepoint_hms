"""
SaaS-side subscription billing endpoints.

Two audiences:

* SaaS admins — list every tenant's invoices, manually issue an invoice
  for a subscription, record manual payments, and run the daily
  generate / sweep-overdue jobs on demand.
* Tenant admins — list their own tenant's invoices via ``/me`` (gated by
  the tenant context resolved from subdomain or token).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_master_db
from app.core.dependencies import CurrentSaaSAdmin
from app.core.enums import (
    SubscriptionInvoiceStatus,
    SubscriptionPaymentStatus,
)
from app.core.exceptions import NotFoundError
from app.core.multitenancy import get_current_tenant_id
from app.dependencies.auth import (
    require_saas_billing_admin,
    require_saas_super_admin,
)
from app.models.all_models import (
    SaaSAdmin,
    SubscriptionInvoice,
    TenantSubscription,
)
from app.services.subscription_billing_service import SubscriptionBillingService


router = APIRouter(prefix="/subscription-billing", tags=["SaaS - Subscription Billing"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class InvoiceLineItem(BaseModel):
    description: str
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    quantity: float = 1
    unit_price: float = 0
    amount: float = 0


class InvoiceReadSchema(BaseModel):
    id: int
    tenant_id: int
    subscription_id: int
    plan_id: int
    invoice_number: str
    plan_code_snapshot: str
    plan_name_snapshot: str
    plan_interval_snapshot: str
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    amount_due: Decimal
    period_start: datetime
    period_end: datetime
    issued_at: datetime
    due_date: datetime
    paid_at: Optional[datetime] = None
    status: SubscriptionInvoiceStatus
    line_items: Optional[list[InvoiceLineItem]] = None
    sent_to_email: Optional[str] = None
    sent_at: Optional[datetime] = None
    reminder_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class InvoiceIssueSchema(BaseModel):
    subscription_id: int
    send_email: bool = True


class PaymentRecordSchema(BaseModel):
    amount: float = Field(..., gt=0)
    payment_method: str = "MANUAL"
    provider: Optional[str] = None
    transaction_reference: Optional[str] = None
    paid_at: Optional[datetime] = None
    notes: Optional[str] = None
    send_receipt: bool = True


class PaymentReadSchema(BaseModel):
    id: int
    invoice_id: int
    tenant_id: int
    amount: Decimal
    currency: str
    payment_method: str
    transaction_reference: Optional[str] = None
    provider: Optional[str] = None
    status: SubscriptionPaymentStatus
    paid_at: datetime
    receipt_number: Optional[str] = None
    receipt_sent_to_email: Optional[str] = None
    receipt_sent_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


def _service(db: Annotated[Session, Depends(get_master_db)]) -> SubscriptionBillingService:
    return SubscriptionBillingService(db)


# ---------------------------------------------------------------------------
# Routes — SaaS admin
# ---------------------------------------------------------------------------


@router.get(
    "/invoices",
    response_model=list[InvoiceReadSchema],
    summary="List all subscription invoices (SaaS admin)",
)
def list_invoices(
    _admin: Annotated[SaaSAdmin, Depends(require_saas_billing_admin)],
    service: Annotated[SubscriptionBillingService, Depends(_service)],
    tenant_id: Optional[int] = None,
    invoice_status: Optional[SubscriptionInvoiceStatus] = None,
):
    return service.list_invoices(tenant_id=tenant_id, status=invoice_status)


@router.post(
    "/invoices/issue",
    response_model=InvoiceReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Manually issue an invoice for a subscription",
)
def issue_invoice(
    payload: InvoiceIssueSchema,
    _admin: Annotated[SaaSAdmin, Depends(require_saas_billing_admin)],
    service: Annotated[SubscriptionBillingService, Depends(_service)],
    db: Annotated[Session, Depends(get_master_db)],
):
    sub = (
        db.query(TenantSubscription)
        .filter(TenantSubscription.id == payload.subscription_id)
        .first()
    )
    if sub is None:
        raise NotFoundError(message="Subscription not found.")
    return service.issue_invoice_for_subscription(sub, send_email=payload.send_email)


@router.post(
    "/invoices/run-due",
    summary="Generate invoices for every subscription whose period is closing",
)
def run_due_invoice_generation(
    _admin: Annotated[SaaSAdmin, Depends(require_saas_billing_admin)],
    service: Annotated[SubscriptionBillingService, Depends(_service)],
):
    return service.generate_due_invoices()


@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=PaymentReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record a payment against an invoice",
)
def record_payment(
    invoice_id: int,
    payload: PaymentRecordSchema,
    _admin: Annotated[SaaSAdmin, Depends(require_saas_billing_admin)],
    service: Annotated[SubscriptionBillingService, Depends(_service)],
):
    return service.record_payment(
        invoice_id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        provider=payload.provider,
        transaction_reference=payload.transaction_reference,
        paid_at=payload.paid_at,
        notes=payload.notes,
        send_receipt=payload.send_receipt,
    )


@router.post(
    "/invoices/sweep-overdue",
    summary="Mark all due invoices as OVERDUE and dispatch reminders",
)
def sweep_overdue(
    _admin: Annotated[SaaSAdmin, Depends(require_saas_super_admin)],
    service: Annotated[SubscriptionBillingService, Depends(_service)],
):
    return service.sweep_overdue()


# ---------------------------------------------------------------------------
# Routes — tenant self-service
# ---------------------------------------------------------------------------


@router.get(
    "/invoices/me",
    response_model=list[InvoiceReadSchema],
    summary="List invoices for the current tenant",
)
def list_my_invoices(
    service: Annotated[SubscriptionBillingService, Depends(_service)],
    invoice_status: Optional[SubscriptionInvoiceStatus] = None,
):
    """
    Surface a tenant's own invoices to its administrators.

    Tenant identification flows in via the standard tenant resolution
    middleware (subdomain / X-Tenant-Code / JWT). If the request reaches
    this endpoint without a tenant context an empty list is returned so
    the platform marketing site can probe the route without leaking data.
    """
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        return []
    return service.list_invoices(tenant_id=tenant_id, status=invoice_status)
