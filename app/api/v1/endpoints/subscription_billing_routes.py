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
    SubscriptionStatus,
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
    SubscriptionPayment,
    SubscriptionPlan,
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


# ---------------------------------------------------------------------------
# Tenant self-service: plans catalog, current subscription, plan upgrade
# ---------------------------------------------------------------------------


class PlanFeatureFlagsMixin(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")


class PlanCatalogEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: Optional[str] = None
    price: Decimal
    # Effective yearly price (explicit annual price, or 12x monthly) plus the
    # amount saved vs. paying monthly, so the UI can offer an annual option.
    annual_price: Decimal = Decimal("0")
    annual_savings: Decimal = Decimal("0")
    currency: str
    interval: str
    trial_days: int = 0
    max_facilities: Optional[int] = None
    max_branches: Optional[int] = None
    max_users: Optional[int] = None
    max_patients: Optional[int] = None
    modules: dict[str, bool] = {}


class MySubscriptionSchema(BaseModel):
    plan: Optional[PlanCatalogEntrySchema] = None
    status: Optional[str] = None
    billing_interval: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    trial_end_date: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    auto_renew: Optional[bool] = None

    # --- Billing state (so the tenant UI can show paid / due / under-review) ---
    #: True when the current period's invoice is fully settled (nothing owed).
    current_period_paid: bool = False
    #: Outstanding amount on the open invoice (0 when nothing is owed).
    amount_due: Decimal = Decimal("0")
    #: True while a tenant-submitted manual payment is awaiting SaaS confirmation.
    has_pending_payment: bool = False
    #: Status of the most relevant invoice (open one, else the latest).
    latest_invoice_status: Optional[str] = None
    currency: Optional[str] = None


def _compute_billing_state(db: Session, subscription: TenantSubscription) -> dict:
    """
    Derive the tenant's payable state for the Plan & Billing screen:
    whether the current period is paid, how much is still due, and whether a
    manual payment is sitting in the SaaS review queue.
    """
    open_statuses = [
        SubscriptionInvoiceStatus.DRAFT,
        SubscriptionInvoiceStatus.ISSUED,
        SubscriptionInvoiceStatus.PARTIALLY_PAID,
        SubscriptionInvoiceStatus.OVERDUE,
    ]
    open_invoice = (
        db.query(SubscriptionInvoice)
        .filter(
            SubscriptionInvoice.subscription_id == subscription.id,
            SubscriptionInvoice.status.in_(open_statuses),
            SubscriptionInvoice.is_deleted.is_(False),
        )
        .order_by(SubscriptionInvoice.id.desc())
        .first()
    )
    latest_invoice = (
        db.query(SubscriptionInvoice)
        .filter(
            SubscriptionInvoice.subscription_id == subscription.id,
            SubscriptionInvoice.is_deleted.is_(False),
        )
        .order_by(SubscriptionInvoice.id.desc())
        .first()
    )

    # A manual payment awaiting confirmation for this tenant.
    pending_payment = (
        db.query(SubscriptionPayment)
        .filter(
            SubscriptionPayment.tenant_id == subscription.tenant_id,
            SubscriptionPayment.status == SubscriptionPaymentStatus.PENDING,
        )
        .order_by(SubscriptionPayment.id.desc())
        .first()
    )

    if open_invoice is not None:
        amount_due = open_invoice.amount_due
        if amount_due is None:
            amount_due = (open_invoice.total_amount or Decimal("0")) - (
                open_invoice.amount_paid or Decimal("0")
            )
        amount_due = max(Decimal("0"), Decimal(str(amount_due)))
        current_period_paid = amount_due <= Decimal("0")
        latest_status = open_invoice.status
        currency = open_invoice.currency
    elif latest_invoice is not None:
        # No open invoice → the current period is settled.
        amount_due = Decimal("0")
        current_period_paid = latest_invoice.status == SubscriptionInvoiceStatus.PAID
        latest_status = latest_invoice.status
        currency = latest_invoice.currency
    else:
        amount_due = Decimal("0")
        current_period_paid = False
        latest_status = None
        currency = None

    return {
        "current_period_paid": bool(current_period_paid),
        "amount_due": amount_due,
        "has_pending_payment": pending_payment is not None,
        "latest_invoice_status": (
            latest_status.value if hasattr(latest_status, "value") else (str(latest_status) if latest_status else None)
        ),
        "currency": currency,
    }


def _valid_billing_interval(value: Optional[str]) -> str:
    from app.services.billing_interval import normalize_interval

    return normalize_interval(value)


class ChangeMyPlanSchema(BaseModel):
    plan_code: str = Field(..., min_length=2, max_length=50)
    billing_interval: str = Field(default="MONTHLY")


def _plan_to_catalog_entry(plan: SubscriptionPlan) -> dict:
    from app.services.tenant_module_service import SUPPORTED_MODULES
    from app.services.billing_interval import annual_price, annual_savings

    return {
        "id": plan.id,
        "code": plan.code,
        "name": plan.name,
        "description": plan.description,
        "price": plan.price,
        "annual_price": annual_price(plan),
        "annual_savings": annual_savings(plan),
        "currency": plan.currency,
        "interval": plan.interval.value if hasattr(plan.interval, "value") else str(plan.interval),
        "trial_days": plan.trial_days,
        "max_facilities": plan.max_facilities,
        "max_branches": plan.max_branches,
        "max_users": plan.max_users,
        "max_patients": plan.max_patients,
        "modules": {
            code: bool(getattr(plan, f"has_{code}", False)) for code, _ in SUPPORTED_MODULES
        },
    }


from app.core.dependencies import AdminUser as TenantAdminUser  # noqa: E402


@router.get(
    "/plans",
    response_model=list[PlanCatalogEntrySchema],
    summary="List active subscription plans (tenant-facing catalog)",
)
def list_plans_catalog(
    _: TenantAdminUser,
    db: Annotated[Session, Depends(get_master_db)],
):
    """
    The plan catalog a tenant administrator sees when choosing an upgrade:
    every active plan with pricing, limits and the module matrix.
    """
    plans = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.is_active.is_(True), SubscriptionPlan.is_deleted.is_(False))
        .order_by(SubscriptionPlan.price.asc())
        .all()
    )
    return [_plan_to_catalog_entry(p) for p in plans]


@router.get(
    "/me/subscription",
    response_model=MySubscriptionSchema,
    summary="Get the current tenant's active subscription",
)
def get_my_subscription(
    _: TenantAdminUser,
    db: Annotated[Session, Depends(get_master_db)],
):
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        return MySubscriptionSchema()
    sub = (
        db.query(TenantSubscription)
        .filter(
            TenantSubscription.tenant_id == tenant_id,
            TenantSubscription.status.in_(
                [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
            ),
        )
        .order_by(TenantSubscription.id.desc())
        .first()
    )
    if sub is None:
        return MySubscriptionSchema()
    billing = _compute_billing_state(db, sub)
    return MySubscriptionSchema(
        plan=_plan_to_catalog_entry(sub.plan) if sub.plan else None,
        status=sub.status.value if hasattr(sub.status, "value") else str(sub.status),
        billing_interval=_valid_billing_interval(getattr(sub, "billing_interval", None)),
        start_date=sub.start_date,
        end_date=sub.end_date,
        trial_end_date=sub.trial_end_date,
        current_period_end=sub.current_period_end,
        auto_renew=sub.auto_renew,
        current_period_paid=billing["current_period_paid"],
        amount_due=billing["amount_due"],
        has_pending_payment=billing["has_pending_payment"],
        latest_invoice_status=billing["latest_invoice_status"],
        currency=billing["currency"],
    )


@router.post(
    "/me/change-plan",
    response_model=dict,
    summary="Change the current tenant's subscription plan (tenant admin)",
)
def change_my_plan(
    payload: ChangeMyPlanSchema,
    _: TenantAdminUser,
    db: Annotated[Session, Depends(get_master_db)],
):
    """
    Self-service plan change for tenant administrators. The tenant is taken
    from the request context (never from the payload), so an admin can only
    ever change their own hospital's plan. Module availability updates
    immediately — the sidebar re-reads /tenant-modules/me/list.
    """
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        raise NotFoundError(message="No tenant context resolved for this request.")

    from app.services.tenant_service import TenantService

    service = TenantService(db)
    subscription = service.change_subscription_plan(
        tenant_id, payload.plan_code, billing_interval=payload.billing_interval
    )
    plan = subscription.plan
    return {
        "success": True,
        "message": f"Subscription changed to '{plan.name if plan else payload.plan_code}'.",
        "plan_code": plan.code if plan else payload.plan_code.upper(),
        "status": subscription.status.value if hasattr(subscription.status, "value") else str(subscription.status),
        "billing_interval": getattr(subscription, "billing_interval", "MONTHLY"),
        "start_date": subscription.start_date,
    }


# ===========================================================================
# SUBSCRIPTION PAYMENTS — Flutterwave checkout, manual bank payment + upload,
# 14-day trial, and SaaS-admin confirmation.
# ===========================================================================

import asyncio
import os
import uuid as _uuid

from fastapi import File, Form, Header, Request, Response, UploadFile
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.models.all_models import SubscriptionPayment, Tenant
from app.services.flutterwave_service import FlutterwaveService
from app.services.paystack_service import PaystackService


def _active_payment_gateway() -> str:
    """The platform-configured subscription gateway (flutterwave | paystack)."""
    gateway = (getattr(settings, "PAYMENT_GATEWAY", None) or "flutterwave").strip().lower()
    return gateway if gateway in {"flutterwave", "paystack"} else "flutterwave"


def _prepare_subscription_payment(db: Session, payload: "FlutterwaveCheckoutSchema"):
    """
    Shared checkout prep: optionally switch the plan, ensure an open invoice
    exists, and resolve the outstanding amount. Returns
    ``(tenant, service, invoice, amount_due)``.
    """
    tenant = _tenant_for_context(db)
    service = SubscriptionBillingService(db)

    if payload.plan_code:
        from app.services.tenant_service import TenantService

        TenantService(db).change_subscription_plan(
            tenant.id, payload.plan_code, billing_interval=payload.billing_interval
        )

    invoice = service.get_or_create_open_invoice(tenant.id)
    amount_due = (
        invoice.amount_due if invoice.amount_due and invoice.amount_due > 0 else invoice.total_amount
    )
    if not amount_due or Decimal(str(amount_due)) <= 0:
        raise BadRequestError(message="This invoice has nothing outstanding to pay.")
    return tenant, service, invoice, amount_due


def _billing_service(db: Annotated[Session, Depends(get_master_db)]) -> SubscriptionBillingService:
    return SubscriptionBillingService(db)


def _proof_storage_dir() -> str:
    base = settings.UPLOADS_DIR or os.path.join(os.getcwd(), "uploads")
    path = os.path.join(base, "subscription_proofs")
    os.makedirs(path, exist_ok=True)
    return path


def _tenant_for_context(db: Session) -> Tenant:
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        raise NotFoundError(message="No tenant context resolved for this request.")
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        raise NotFoundError(message="Tenant not found.")
    return tenant


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class StartTrialSchema(BaseModel):
    plan_code: str = Field(..., min_length=2, max_length=50)
    billing_interval: str = Field(default="MONTHLY")


class FlutterwaveCheckoutSchema(BaseModel):
    # Optional: change plan first, then pay. Omit to pay the current plan.
    plan_code: Optional[str] = Field(default=None, max_length=50)
    billing_interval: str = Field(default="MONTHLY")


class ManualPaymentReviewSchema(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class SubscriptionPaymentReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_id: int
    tenant_id: int
    amount: Decimal
    currency: str
    payment_method: str
    provider: Optional[str] = None
    status: str
    transaction_reference: Optional[str] = None
    payer_bank_name: Optional[str] = None
    payer_account_name: Optional[str] = None
    payer_reference: Optional[str] = None
    proof_file_name: Optional[str] = None
    has_proof: bool = False
    notes: Optional[str] = None
    rejected_reason: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    receipt_number: Optional[str] = None


def _payment_to_read(p: SubscriptionPayment, tenant_name: Optional[str] = None) -> dict:
    return {
        "id": p.id,
        "invoice_id": p.invoice_id,
        "tenant_id": p.tenant_id,
        "tenant_name": tenant_name,
        "amount": p.amount,
        "currency": p.currency,
        "payment_method": p.payment_method,
        "provider": p.provider,
        "status": p.status.value if hasattr(p.status, "value") else str(p.status),
        "transaction_reference": p.transaction_reference,
        "payer_bank_name": p.payer_bank_name,
        "payer_account_name": p.payer_account_name,
        "payer_reference": p.payer_reference,
        "proof_file_name": p.proof_file_name,
        "has_proof": bool(p.proof_file_path),
        "notes": p.notes,
        "rejected_reason": p.rejected_reason,
        "confirmed_at": p.confirmed_at,
        "paid_at": p.paid_at,
        "receipt_number": p.receipt_number,
    }


# ---------------------------------------------------------------------------
# Tenant self-service: trial, Flutterwave checkout, manual payment
# ---------------------------------------------------------------------------


@router.post("/me/start-trial", response_model=dict, summary="Start a free trial on a plan")
def start_trial(
    payload: StartTrialSchema,
    _: TenantAdminUser,
    db: Annotated[Session, Depends(get_master_db)],
):
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        raise NotFoundError(message="No tenant context resolved for this request.")
    from app.services.tenant_service import TenantService

    trial_days = int(getattr(settings, "SUBSCRIPTION_TRIAL_DAYS", 14))
    sub = TenantService(db).start_trial(
        tenant_id,
        payload.plan_code,
        trial_days=trial_days,
        billing_interval=payload.billing_interval,
    )
    return {
        "success": True,
        "message": f"Your {trial_days}-day free trial has started.",
        "plan_code": sub.plan.code if sub.plan else payload.plan_code.upper(),
        "status": sub.status.value if hasattr(sub.status, "value") else str(sub.status),
        "billing_interval": getattr(sub, "billing_interval", "MONTHLY"),
        "trial_end_date": sub.trial_end_date,
        "trial_days": trial_days,
    }


@router.get("/me/payment-config", response_model=dict, summary="Active subscription payment gateway")
def subscription_payment_config(_: TenantAdminUser):
    """
    Report the platform-configured subscription gateway (from ``PAYMENT_GATEWAY``)
    and whether it's configured, so the tenant billing UI shows the right option.
    Subscription payments always use the SaaS/platform gateway credentials.
    """
    gateway = _active_payment_gateway()
    if gateway == "paystack":
        return {
            "gateway": "paystack",
            "configured": bool(settings.PAYSTACK_SECRET_KEY),
            "public_key": settings.PAYSTACK_PUBLIC_KEY,
            "manual_enabled": True,
        }
    return {
        "gateway": "flutterwave",
        "configured": bool(settings.FLUTTERWAVE_SECRET_KEY),
        "public_key": settings.FLUTTERWAVE_PUBLIC_KEY,
        "manual_enabled": True,
    }


@router.post("/me/checkout", response_model=dict, summary="Start a subscription payment via the platform gateway")
def subscription_checkout(
    payload: FlutterwaveCheckoutSchema,
    _: TenantAdminUser,
    db: Annotated[Session, Depends(get_master_db)],
):
    """
    Start an online subscription payment using the SaaS/platform-configured
    gateway (``PAYMENT_GATEWAY`` = flutterwave | paystack). Ensures the tenant is
    on the requested plan, guarantees an open invoice, and returns a
    ``payment_link`` the browser is redirected to. Works for both gateways.
    """
    gateway = _active_payment_gateway()
    tenant, service, invoice, amount_due = _prepare_subscription_payment(db, payload)

    callback_base = settings.PAYMENT_CALLBACK_URL or "http://localhost:5173/billing/callback"
    email = tenant.billing_email or f"billing+{tenant.code.lower()}@carepointhms.com"
    meta = {
        "tenant_id": tenant.id,
        "tenant_code": tenant.code,
        "invoice_id": invoice.id,
        "purpose": "subscription",
    }

    if gateway == "paystack":
        if not settings.PAYSTACK_SECRET_KEY:
            raise BadRequestError(
                message="Online payments are not configured. Please use manual bank payment."
            )
        ps = PaystackService(db)
        reference = f"SUB-{tenant.code}-{invoice.id}-{_uuid.uuid4().hex[:8].upper()}"
        redirect_url = (
            f"{callback_base}?tenant={tenant.code}&invoice_id={invoice.id}"
            f"&gateway=paystack&reference={reference}"
        )
        data = asyncio.run(
            ps.initialize_checkout(
                email=email,
                amount=amount_due,
                reference=reference,
                callback_url=redirect_url,
                currency=invoice.currency,
                metadata=meta,
            )
        )
        return {
            "success": True,
            "message": "Checkout created.",
            "gateway": "paystack",
            "payment_link": data.get("authorization_url"),
            "reference": data.get("reference", reference),
            "invoice_id": invoice.id,
            "amount": float(amount_due),
            "currency": invoice.currency,
        }

    # Default: Flutterwave.
    flw = FlutterwaveService()
    if not flw.is_configured:
        raise BadRequestError(
            message="Online payments are not configured. Please use manual bank payment."
        )
    tx_ref = flw.new_reference()
    redirect_url = f"{callback_base}?tenant={tenant.code}&invoice_id={invoice.id}&gateway=flutterwave"
    data = asyncio.run(
        flw.initialize_payment(
            amount=amount_due,
            currency=invoice.currency,
            tx_ref=tx_ref,
            customer_email=email,
            customer_name=tenant.billing_contact_name or tenant.name,
            customer_phone=tenant.billing_phone or "",
            redirect_url=redirect_url,
            meta=meta,
        )
    )
    return {
        "success": True,
        "message": "Checkout created.",
        "gateway": "flutterwave",
        "payment_link": data.get("link"),
        "reference": tx_ref,
        "invoice_id": invoice.id,
        "amount": float(amount_due),
        "currency": invoice.currency,
    }


@router.post("/me/checkout/flutterwave", response_model=dict, summary="Start a Flutterwave subscription payment")
def flutterwave_checkout(
    payload: FlutterwaveCheckoutSchema,
    _: TenantAdminUser,
    db: Annotated[Session, Depends(get_master_db)],
):
    """
    Ensure the tenant is on the requested plan (changing it first if a
    ``plan_code`` is supplied), guarantee an open invoice exists, then create a
    Flutterwave hosted-checkout link for the amount due. Returns the payment
    link the frontend redirects the browser to.
    """
    tenant = _tenant_for_context(db)
    service = SubscriptionBillingService(db)

    if payload.plan_code:
        from app.services.tenant_service import TenantService

        TenantService(db).change_subscription_plan(
            tenant.id, payload.plan_code, billing_interval=payload.billing_interval
        )

    invoice = service.get_or_create_open_invoice(tenant.id)
    amount_due = invoice.amount_due if invoice.amount_due and invoice.amount_due > 0 else invoice.total_amount
    if not amount_due or Decimal(str(amount_due)) <= 0:
        raise BadRequestError(message="This invoice has nothing outstanding to pay.")

    flw = FlutterwaveService()
    if not flw.is_configured:
        raise BadRequestError(message="Online payments are not configured. Please use manual bank payment.")

    tx_ref = flw.new_reference()
    email = tenant.billing_email or f"billing+{tenant.code.lower()}@carepointhms.com"
    callback_base = settings.PAYMENT_CALLBACK_URL or "http://localhost:5173/billing/callback"
    # Encode the tenant so the callback can re-resolve context if needed.
    redirect_url = f"{callback_base}?tenant={tenant.code}&invoice_id={invoice.id}"

    data = asyncio.run(
        flw.initialize_payment(
            amount=amount_due,
            currency=invoice.currency,
            tx_ref=tx_ref,
            customer_email=email,
            customer_name=tenant.billing_contact_name or tenant.name,
            customer_phone=tenant.billing_phone or "",
            redirect_url=redirect_url,
            meta={
                "tenant_id": tenant.id,
                "tenant_code": tenant.code,
                "invoice_id": invoice.id,
                "purpose": "subscription",
            },
        )
    )

    # Stamp the pending reference on the invoice notes for reconciliation.
    return {
        "success": True,
        "message": "Checkout created.",
        "payment_link": data.get("link"),
        "tx_ref": tx_ref,
        "invoice_id": invoice.id,
        "amount": float(amount_due),
        "currency": invoice.currency,
    }


@router.get("/me/checkout/verify", response_model=dict, summary="Verify a subscription payment (any gateway)")
def subscription_checkout_verify(
    _: TenantAdminUser,
    db: Annotated[Session, Depends(get_master_db)],
    tx_ref: Optional[str] = None,
    transaction_id: Optional[str] = None,
    reference: Optional[str] = None,
    invoice_id: Optional[int] = None,
    gateway: Optional[str] = None,
):
    """
    Called by the frontend callback page. Verifies the transaction with the
    appropriate gateway and records a SUCCEEDED gateway payment (idempotently).

    Paystack returns to the callback with ``?reference=&trxref=`` (and we add
    ``gateway=paystack``); Flutterwave returns ``?tx_ref=&transaction_id=``.
    """
    gw = (gateway or "").strip().lower()
    use_paystack = gw == "paystack" or (
        not gw and reference and not transaction_id and not tx_ref
        and _active_payment_gateway() == "paystack"
    )
    service = SubscriptionBillingService(db)

    if use_paystack:
        ref = reference or tx_ref
        if not ref:
            raise BadRequestError(message="A payment reference is required to verify.")
        ps = PaystackService(db)
        data = asyncio.run(ps.verify_transaction(ref))
        status_str = str(data.get("status", "")).lower()  # Paystack success == "success"
        if status_str != "success":
            return {"success": False, "message": f"Payment not successful (status: {status_str}).", "status": status_str}

        meta = data.get("metadata") or {}
        resolved_invoice_id = invoice_id or (meta.get("invoice_id") if isinstance(meta, dict) else None)
        if not resolved_invoice_id:
            raise BadRequestError(message="Could not resolve which invoice this payment settles.")
        # Paystack amounts are in the minor unit (kobo) — convert back.
        amount_major = Decimal(str(data.get("amount", 0))) / Decimal("100")
        payment = service.record_gateway_payment(
            int(resolved_invoice_id),
            amount=amount_major,
            provider="PAYSTACK",
            transaction_reference=str(data.get("reference") or ref),
            raw_payload=data,
        )
    else:
        flw = FlutterwaveService()
        if transaction_id:
            data = asyncio.run(flw.verify_transaction(transaction_id))
        elif tx_ref:
            data = asyncio.run(flw.verify_transaction_by_ref(tx_ref))
        else:
            raise BadRequestError(message="A transaction_id or tx_ref is required to verify.")

        status_str = str(data.get("status", "")).lower()
        if status_str != "successful":
            return {"success": False, "message": f"Payment not successful (status: {status_str}).", "status": status_str}

        meta = data.get("meta") or {}
        resolved_invoice_id = invoice_id or meta.get("invoice_id")
        if not resolved_invoice_id:
            raise BadRequestError(message="Could not resolve which invoice this payment settles.")
        payment = service.record_gateway_payment(
            int(resolved_invoice_id),
            amount=data.get("amount", 0),
            provider="FLUTTERWAVE",
            transaction_reference=str(data.get("tx_ref") or data.get("flw_ref") or data.get("id")),
            raw_payload=data,
        )

    return {
        "success": True,
        "message": "Payment confirmed. Your subscription is now active.",
        "payment_id": payment.id,
        "amount": float(payment.amount),
        "status": payment.status.value if hasattr(payment.status, "value") else str(payment.status),
    }


@router.post("/me/manual-payment", response_model=dict, summary="Submit a manual bank payment with proof")
def submit_manual_payment(
    _: TenantAdminUser,
    db: Annotated[Session, Depends(get_master_db)],
    amount: float = Form(...),
    payment_method: str = Form("BANK_TRANSFER"),
    payer_bank_name: Optional[str] = Form(None),
    payer_account_name: Optional[str] = Form(None),
    payer_reference: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    plan_code: Optional[str] = Form(None),
    billing_interval: str = Form("MONTHLY"),
    proof: UploadFile = File(...),
):
    """
    A tenant admin who paid at a bank counter or via online transfer uploads
    the evidence here. The payment is recorded PENDING and appears in the SaaS
    review queue for confirmation.
    """
    tenant = _tenant_for_context(db)
    service = SubscriptionBillingService(db)

    if plan_code:
        from app.services.tenant_service import TenantService

        TenantService(db).change_subscription_plan(
            tenant.id, plan_code, billing_interval=billing_interval
        )

    invoice = service.get_or_create_open_invoice(tenant.id)

    # Persist the proof file.
    max_bytes = int(getattr(settings, "MAX_UPLOAD_SIZE_MB", 20)) * 1024 * 1024
    raw = proof.file.read()
    if len(raw) == 0:
        raise BadRequestError(message="The uploaded proof file is empty.")
    if len(raw) > max_bytes:
        raise BadRequestError(message=f"Proof file exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB limit.")

    safe_name = os.path.basename(proof.filename or "proof")
    ext = os.path.splitext(safe_name)[1][:10]
    stored_name = f"{tenant.code}_{invoice.id}_{_uuid.uuid4().hex[:12]}{ext}"
    dest = os.path.join(_proof_storage_dir(), stored_name)
    with open(dest, "wb") as fh:
        fh.write(raw)

    payment = service.record_manual_payment(
        invoice.id,
        amount=amount,
        payment_method=payment_method,
        payer_bank_name=payer_bank_name,
        payer_account_name=payer_account_name,
        payer_reference=payer_reference,
        proof_file_path=dest,
        proof_file_name=safe_name,
        proof_content_type=proof.content_type,
        notes=notes,
    )
    return {
        "success": True,
        "message": "Payment evidence submitted. A platform administrator will confirm it shortly.",
        "payment_id": payment.id,
        "invoice_id": invoice.id,
        "status": payment.status.value if hasattr(payment.status, "value") else str(payment.status),
    }


# ---------------------------------------------------------------------------
# SaaS admin: review queue, confirm/reject, proof download
# ---------------------------------------------------------------------------


@router.get("/payments/pending", response_model=list[dict], summary="List manual payments awaiting confirmation")
def list_pending_payments(
    _: CurrentSaaSAdmin,
    db: Annotated[Session, Depends(get_master_db)],
):
    service = SubscriptionBillingService(db)
    payments = service.list_pending_payments()
    tenant_names = {
        t.id: t.name
        for t in db.query(Tenant).filter(Tenant.id.in_([p.tenant_id for p in payments])).all()
    } if payments else {}
    return [_payment_to_read(p, tenant_names.get(p.tenant_id)) for p in payments]


@router.get(
    "/payments",
    response_model=list[dict],
    summary="Look up subscription payments (SaaS admin) — all statuses",
)
def list_payments(
    _: CurrentSaaSAdmin,
    db: Annotated[Session, Depends(get_master_db)],
    payment_status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 200,
):
    """
    Cross-tenant payment lookup for the SaaS console. Defaults to confirmed
    (SUCCEEDED) payments so the platform team can look up money already
    received; pass ``payment_status`` to widen or narrow the view, and
    ``search`` to match a tenant name, receipt number, or payer reference.
    """
    service = SubscriptionBillingService(db)
    # Default the lookup to confirmed payments unless a status is specified.
    effective_status = payment_status if payment_status is not None else "SUCCEEDED"
    if effective_status == "ALL":
        effective_status = None
    payments = service.list_payments(
        status=effective_status, search=search, limit=max(1, min(limit, 1000))
    )
    tenant_names = {
        t.id: t.name
        for t in db.query(Tenant).filter(Tenant.id.in_([p.tenant_id for p in payments])).all()
    } if payments else {}
    return [_payment_to_read(p, tenant_names.get(p.tenant_id)) for p in payments]


@router.post("/payments/{payment_id}/confirm", response_model=dict, summary="Confirm a manual payment (SaaS admin)")
def confirm_payment(
    payment_id: int,
    current_admin: CurrentSaaSAdmin,
    db: Annotated[Session, Depends(get_master_db)],
):
    service = SubscriptionBillingService(db)
    payment = service.confirm_manual_payment(payment_id, admin_id=getattr(current_admin, "id", None))
    return {
        "success": True,
        "message": "Payment confirmed — the tenant's subscription has been activated.",
        "payment_id": payment.id,
        "status": payment.status.value if hasattr(payment.status, "value") else str(payment.status),
    }


@router.post("/payments/{payment_id}/reject", response_model=dict, summary="Reject a manual payment (SaaS admin)")
def reject_payment(
    payment_id: int,
    payload: ManualPaymentReviewSchema,
    current_admin: CurrentSaaSAdmin,
    db: Annotated[Session, Depends(get_master_db)],
):
    service = SubscriptionBillingService(db)
    payment = service.reject_manual_payment(
        payment_id, admin_id=getattr(current_admin, "id", None), reason=payload.reason
    )
    return {
        "success": True,
        "message": "Payment rejected. The tenant has been notified to re-submit.",
        "payment_id": payment.id,
        "status": payment.status.value if hasattr(payment.status, "value") else str(payment.status),
    }


@router.get("/payments/{payment_id}/proof", summary="Download the proof-of-payment file (SaaS admin)")
def download_proof(
    payment_id: int,
    _: CurrentSaaSAdmin,
    db: Annotated[Session, Depends(get_master_db)],
):
    service = SubscriptionBillingService(db)
    payment = service.get_payment(payment_id)
    if not payment.proof_file_path or not os.path.exists(payment.proof_file_path):
        raise NotFoundError(message="No proof file is attached to this payment.")
    return FileResponse(
        payment.proof_file_path,
        media_type=payment.proof_content_type or "application/octet-stream",
        filename=payment.proof_file_name or os.path.basename(payment.proof_file_path),
    )
