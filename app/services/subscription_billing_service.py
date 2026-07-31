"""
SaaS-level subscription billing.

Responsibilities
----------------
* Generate invoices for subscriptions whose billing window is closing.
* Email each invoice to the tenant's ``billing_email`` (and CC the
  in-tenant admin so both sides see the renewal alert).
* Record payments against invoices and issue receipts.
* Roll the subscription's billing window forward when an invoice is
  fully paid.
* Sweep overdue invoices and dispatch dunning reminders.

This service operates on the **master** database. Receipt and invoice
notifications are sent via raw email helpers (``app.utils.email_utils``)
rather than the in-tenant :class:`NotificationDispatcher` because the
billing audience lives outside the tenant database — they are SaaS-side
contacts addressed by ``Tenant.billing_email``.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import (
    NotificationEvent,
    SubscriptionInvoiceStatus,
    SubscriptionPaymentStatus,
    SubscriptionStatus,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    SubscriptionInvoice,
    SubscriptionPayment,
    SubscriptionPlan,
    Tenant,
    TenantSubscription,
)


logger = logging.getLogger(__name__)


# Number of days before period_end to issue the renewal invoice.
DEFAULT_PRE_ISSUE_DAYS = 7
# Default invoice payment terms (days).
DEFAULT_PAYMENT_TERMS_DAYS = 14


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _period_end(plan: SubscriptionPlan, period_start: datetime) -> datetime:
    interval = str(getattr(plan.interval, "value", plan.interval) or "MONTHLY").upper()
    if interval in {"YEARLY", "ANNUAL"}:
        return period_start + timedelta(days=365)
    if interval == "QUARTERLY":
        return period_start + timedelta(days=91)
    if interval == "WEEKLY":
        return period_start + timedelta(days=7)
    if interval == "DAILY":
        return period_start + timedelta(days=1)
    return period_start + timedelta(days=30)


def _generate_invoice_number(tenant: Tenant) -> str:
    code = (tenant.code or "TNT").upper()
    suffix = secrets.token_hex(3).upper()
    return f"INV-{code}-{datetime.utcnow():%Y%m%d}-{suffix}"


def _generate_receipt_number(tenant: Tenant) -> str:
    code = (tenant.code or "TNT").upper()
    suffix = secrets.token_hex(3).upper()
    return f"RCT-{code}-{datetime.utcnow():%Y%m%d}-{suffix}"


def _try_send_email(
    *, subject: str, recipients: list[str], body: str, body_html: Optional[str] = None
) -> bool:
    """Best-effort email delivery. Failures are logged, not raised."""
    if not recipients:
        return False
    try:
        from app.utils.email_utils import send_email  # type: ignore
    except Exception:
        logger.warning("send_email helper unavailable; billing email skipped.")
        return False
    try:
        send_email(
            subject=subject,
            recipients=recipients,
            body_text=body,
            body_html=body_html,
        )
        return True
    except Exception as exc:
        logger.warning("Billing email delivery failed: %s", exc)
        return False


def _brand_name() -> str:
    from app.core.config import settings

    return str(getattr(settings, "APP_NAME", None) or "CarePoint HMS")


def _billing_portal_url() -> str:
    """Deep link tenants to the Plan & Billing screen from an email CTA."""
    from app.core.config import settings

    base = str(getattr(settings, "FRONTEND_URL", None) or "").rstrip("/")
    return f"{base}/settings/plan" if base else "/settings/plan"


def _billing_email_bodies(**kwargs) -> tuple[str, str]:
    """Render a billing email into (plain_text, html) via the shared template."""
    from app.utils.email_utils import render_branded_email, render_branded_email_text

    return render_branded_email_text(**kwargs), render_branded_email(**kwargs)


def _resolve_billing_recipients(tenant: Tenant) -> list[str]:
    """Return the list of email addresses to copy on billing communication."""
    recipients: list[str] = []
    if tenant.billing_email:
        recipients.append(tenant.billing_email)
    # The platform contact stays on the thread regardless.
    fallback = getattr(settings, "BILLING_NOTIFICATIONS_BCC", None)
    if fallback:
        recipients.append(fallback)
    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for r in recipients:
        norm = (r or "").strip().lower()
        if norm and norm not in seen:
            seen.add(norm)
            unique.append(norm)
    return unique


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SubscriptionBillingService:
    """
    Master-DB service for subscription invoicing and payment intake.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.pre_issue_days = int(getattr(settings, "BILLING_PRE_ISSUE_DAYS", DEFAULT_PRE_ISSUE_DAYS))
        self.payment_terms_days = int(getattr(settings, "BILLING_PAYMENT_TERMS_DAYS", DEFAULT_PAYMENT_TERMS_DAYS))

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def list_invoices(
        self,
        *,
        tenant_id: Optional[int] = None,
        status: Optional[SubscriptionInvoiceStatus] = None,
    ) -> list[SubscriptionInvoice]:
        q = self.db.query(SubscriptionInvoice).filter(SubscriptionInvoice.is_deleted.is_(False))
        if tenant_id is not None:
            q = q.filter(SubscriptionInvoice.tenant_id == tenant_id)
        if status is not None:
            q = q.filter(SubscriptionInvoice.status == status)
        return q.order_by(SubscriptionInvoice.id.desc()).all()

    def get_invoice(self, invoice_id: int) -> SubscriptionInvoice:
        rec = (
            self.db.query(SubscriptionInvoice)
            .filter(
                SubscriptionInvoice.id == invoice_id,
                SubscriptionInvoice.is_deleted.is_(False),
            )
            .first()
        )
        if not rec:
            raise NotFoundError(message="Subscription invoice not found.")
        return rec

    # ------------------------------------------------------------------
    # ISSUE
    # ------------------------------------------------------------------

    def issue_invoice_for_subscription(
        self,
        subscription: TenantSubscription,
        *,
        send_email: bool = True,
    ) -> SubscriptionInvoice:
        """
        Build and persist a new invoice for the next renewal period of
        ``subscription``. Idempotent: if an unpaid invoice for the same
        period already exists, that record is returned unchanged.
        """
        tenant = self.db.query(Tenant).filter(Tenant.id == subscription.tenant_id).first()
        if tenant is None:
            raise NotFoundError(message="Tenant for subscription was not found.")
        plan = subscription.plan or self.db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == subscription.plan_id
        ).first()
        if plan is None:
            raise BadRequestError(message="Subscription has no plan attached.")

        # The billing cycle chosen for this subscription (monthly / yearly)
        # drives both the amount and how far the period runs.
        from app.services.billing_interval import (
            effective_price,
            normalize_interval,
            period_end_for_interval,
        )

        interval = normalize_interval(getattr(subscription, "billing_interval", None) or plan.interval)

        # Determine the next period.
        now = datetime.now(timezone.utc)
        prev_end = subscription.current_period_end or now
        if prev_end.tzinfo is None:
            prev_end = prev_end.replace(tzinfo=timezone.utc)
        period_start = prev_end if prev_end > now else now
        period_end = period_end_for_interval(interval, period_start)

        # Idempotency: do we already have an open invoice for this exact period?
        existing = (
            self.db.query(SubscriptionInvoice)
            .filter(
                SubscriptionInvoice.subscription_id == subscription.id,
                SubscriptionInvoice.period_start == period_start,
                SubscriptionInvoice.period_end == period_end,
                SubscriptionInvoice.status.in_(
                    [
                        SubscriptionInvoiceStatus.DRAFT,
                        SubscriptionInvoiceStatus.ISSUED,
                        SubscriptionInvoiceStatus.PARTIALLY_PAID,
                        SubscriptionInvoiceStatus.OVERDUE,
                    ]
                ),
                SubscriptionInvoice.is_deleted.is_(False),
            )
            .first()
        )
        if existing is not None:
            return existing

        plan_amount: Decimal = effective_price(plan, interval)
        currency = str(plan.currency or "NGN").upper()
        cycle_label = "Annual" if interval == "YEARLY" else "Monthly"

        line_items = [
            {
                "description": f"{plan.name} subscription ({cycle_label})",
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "quantity": 1,
                "unit_price": float(plan_amount),
                "amount": float(plan_amount),
            }
        ]

        invoice = SubscriptionInvoice(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            plan_id=plan.id,
            invoice_number=_generate_invoice_number(tenant),
            plan_code_snapshot=plan.code,
            plan_name_snapshot=plan.name,
            plan_interval_snapshot=interval,
            currency=currency,
            subtotal=plan_amount,
            tax_amount=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            total_amount=plan_amount,
            amount_paid=Decimal("0.00"),
            amount_due=plan_amount,
            period_start=period_start,
            period_end=period_end,
            issued_at=now,
            due_date=now + timedelta(days=self.payment_terms_days),
            status=SubscriptionInvoiceStatus.ISSUED,
            line_items=line_items,
        )
        self.db.add(invoice)
        self.db.flush()

        # Update the parent subscription's next_invoice_at so we don't
        # re-issue on every scheduler tick.
        subscription.next_invoice_at = period_end - timedelta(days=self.pre_issue_days)

        self.db.commit()
        self.db.refresh(invoice)

        if send_email:
            self._dispatch_invoice_email(tenant, invoice, plan)

        return invoice

    def generate_due_invoices(self) -> dict:
        """
        Walk every active subscription whose ``next_invoice_at`` is due and
        issue an invoice for the next period.

        Designed to be safe to run on every scheduler tick — each
        subscription is invoiced at most once per period thanks to the
        idempotency check inside ``issue_invoice_for_subscription``.
        """
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=self.pre_issue_days)

        candidates = (
            self.db.query(TenantSubscription)
            .filter(
                TenantSubscription.is_deleted.is_(False),
                TenantSubscription.auto_renew.is_(True),
                TenantSubscription.status.in_(
                    [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
                ),
                or_(
                    TenantSubscription.next_invoice_at.is_(None),
                    TenantSubscription.next_invoice_at <= cutoff,
                ),
                or_(
                    TenantSubscription.current_period_end.is_(None),
                    TenantSubscription.current_period_end <= cutoff,
                ),
            )
            .all()
        )

        issued = 0
        skipped = 0
        for sub in candidates:
            try:
                invoice = self.issue_invoice_for_subscription(sub, send_email=True)
                if invoice.issued_at and invoice.issued_at >= now - timedelta(minutes=2):
                    issued += 1
                else:
                    skipped += 1
            except Exception as exc:
                logger.exception("Failed to issue invoice for subscription %s: %s", sub.id, exc)
                skipped += 1

        return {"candidates": len(candidates), "issued": issued, "skipped": skipped}

    # ------------------------------------------------------------------
    # PAYMENT
    # ------------------------------------------------------------------

    def record_payment(
        self,
        invoice_id: int,
        *,
        amount: float | Decimal,
        payment_method: str = "MANUAL",
        provider: Optional[str] = None,
        transaction_reference: Optional[str] = None,
        paid_at: Optional[datetime] = None,
        notes: Optional[str] = None,
        raw_payload: Optional[dict] = None,
        send_receipt: bool = True,
    ) -> SubscriptionPayment:
        """
        Record a payment against ``invoice_id``.

        On a successful payment we:

        * append a :class:`SubscriptionPayment` row,
        * update the parent invoice's ``amount_paid``/``amount_due``/``status``,
        * roll the subscription's billing window forward when the
          invoice is fully paid,
        * dispatch a receipt email to the billing contact.
        """
        invoice = self.get_invoice(invoice_id)
        if invoice.status in {
            SubscriptionInvoiceStatus.PAID,
            SubscriptionInvoiceStatus.CANCELLED,
            SubscriptionInvoiceStatus.REFUNDED,
        }:
            raise BadRequestError(message=f"Invoice cannot accept new payments in status {invoice.status}.")

        amount_dec = Decimal(str(amount))
        if amount_dec <= 0:
            raise BadRequestError(message="Payment amount must be greater than zero.")

        tenant = self.db.query(Tenant).filter(Tenant.id == invoice.tenant_id).first()
        if tenant is None:
            raise NotFoundError(message="Tenant not found for invoice.")

        payment = SubscriptionPayment(
            invoice_id=invoice.id,
            tenant_id=invoice.tenant_id,
            amount=amount_dec,
            currency=invoice.currency,
            payment_method=payment_method,
            transaction_reference=transaction_reference,
            provider=provider,
            status=SubscriptionPaymentStatus.SUCCEEDED,
            paid_at=paid_at or datetime.now(timezone.utc),
            receipt_number=_generate_receipt_number(tenant),
            notes=notes,
            raw_payload=raw_payload,
        )
        self.db.add(payment)
        self.db.flush()

        # Update invoice totals.
        new_paid = (invoice.amount_paid or Decimal("0")) + amount_dec
        invoice.amount_paid = new_paid
        invoice.amount_due = max(Decimal("0"), (invoice.total_amount or Decimal("0")) - new_paid)
        if invoice.amount_due <= Decimal("0"):
            invoice.status = SubscriptionInvoiceStatus.PAID
            invoice.paid_at = payment.paid_at
            self._roll_subscription_period_forward(invoice)
        else:
            invoice.status = SubscriptionInvoiceStatus.PARTIALLY_PAID

        self.db.commit()
        self.db.refresh(payment)
        self.db.refresh(invoice)

        if send_receipt:
            self._dispatch_payment_receipt(tenant, invoice, payment)

        return payment

    def _roll_subscription_period_forward(self, invoice: SubscriptionInvoice) -> None:
        sub = (
            self.db.query(TenantSubscription)
            .filter(TenantSubscription.id == invoice.subscription_id)
            .first()
        )
        if sub is None:
            return
        plan = sub.plan or self.db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.plan_id).first()
        if plan is None:
            return

        sub.current_period_start = invoice.period_start
        sub.current_period_end = invoice.period_end
        sub.next_invoice_at = invoice.period_end - timedelta(days=self.pre_issue_days)
        # PENDING / TRIALING → ACTIVE on first paid invoice.
        if sub.status != SubscriptionStatus.ACTIVE:
            sub.status = SubscriptionStatus.ACTIVE

    # ------------------------------------------------------------------
    # OVERDUE / DUNNING
    # ------------------------------------------------------------------

    def sweep_overdue(self) -> dict:
        """Mark issued invoices as OVERDUE once the due date has passed."""
        now = datetime.now(timezone.utc)
        targets = (
            self.db.query(SubscriptionInvoice)
            .filter(
                SubscriptionInvoice.is_deleted.is_(False),
                SubscriptionInvoice.status.in_(
                    [SubscriptionInvoiceStatus.ISSUED, SubscriptionInvoiceStatus.PARTIALLY_PAID]
                ),
                SubscriptionInvoice.due_date <= now,
            )
            .all()
        )
        for inv in targets:
            inv.status = SubscriptionInvoiceStatus.OVERDUE
            inv.last_reminder_at = now
            inv.reminder_count = (inv.reminder_count or 0) + 1
        if targets:
            self.db.commit()
        # Best-effort dispatch of dunning emails.
        for inv in targets:
            tenant = self.db.query(Tenant).filter(Tenant.id == inv.tenant_id).first()
            if tenant:
                self._dispatch_overdue_email(tenant, inv)
        return {"marked_overdue": len(targets)}

    # ------------------------------------------------------------------
    # NOTIFICATION DISPATCH
    # ------------------------------------------------------------------

    def _dispatch_invoice_email(
        self,
        tenant: Tenant,
        invoice: SubscriptionInvoice,
        plan: SubscriptionPlan,
    ) -> None:
        recipients = _resolve_billing_recipients(tenant)
        # Also CC the tenant admin email captured at onboarding.
        if tenant.onboarding_data:
            admin_email = (tenant.onboarding_data or {}).get("admin_email")
            if admin_email and admin_email.lower() not in recipients:
                recipients.append(admin_email.lower())

        subject = (
            f"Invoice {invoice.invoice_number} — {plan.name} subscription "
            f"renewal for {tenant.name}"
        )
        common = dict(
            title="Your subscription is due for renewal",
            intro=f"Hello {tenant.billing_contact_name or tenant.name}, your "
            f"{_brand_name()} subscription for {tenant.name} is due for renewal. "
            "A summary of this invoice is below.",
            highlight_label="Amount due",
            highlight_value=f"{invoice.currency} {invoice.amount_due:,.2f}",
            highlight_caption=f"Due by {invoice.due_date:%d %b %Y}",
            details_heading="Invoice details",
            details=[
                ("Invoice number", invoice.invoice_number),
                ("Plan", f"{plan.name} ({plan.code})"),
                ("Billing interval", invoice.plan_interval_snapshot),
                ("Billing period", f"{invoice.period_start:%d %b %Y} – {invoice.period_end:%d %b %Y}"),
                ("Amount due", f"{invoice.currency} {invoice.amount_due:,.2f}"),
                ("Due date", f"{invoice.due_date:%d %b %Y}"),
            ],
            cta_label="Review & pay invoice",
            cta_url=_billing_portal_url(),
            footer_note="Please settle this invoice before the due date to avoid any "
            "interruption of service. If you've already paid, kindly disregard this message.",
            preheader=f"Invoice {invoice.invoice_number}: {invoice.currency} "
            f"{invoice.amount_due:,.2f} due by {invoice.due_date:%d %b %Y}.",
        )
        body, body_html = _billing_email_bodies(**common)

        sent = _try_send_email(
            subject=subject, recipients=recipients, body=body, body_html=body_html
        )
        invoice.sent_to_email = ", ".join(recipients) if recipients else None
        invoice.sent_at = datetime.now(timezone.utc) if sent else None
        if sent:
            self.db.commit()


    def _dispatch_payment_receipt(
        self,
        tenant: Tenant,
        invoice: SubscriptionInvoice,
        payment: SubscriptionPayment,
    ) -> None:
        recipients = _resolve_billing_recipients(tenant)
        subject = (
            f"Receipt {payment.receipt_number} — payment received for "
            f"invoice {invoice.invoice_number}"
        )
        paid_at = payment.paid_at or datetime.now(timezone.utc)
        common = dict(
            title="Payment received — thank you",
            intro=f"Hello {tenant.billing_contact_name or tenant.name}, we've received "
            "your payment. This email is your official receipt.",
            highlight_label="Amount received",
            highlight_value=f"{payment.currency} {payment.amount:,.2f}",
            highlight_caption=f"Paid on {paid_at:%d %b %Y, %H:%M UTC}",
            details_heading="Receipt details",
            details=[
                ("Receipt number", payment.receipt_number),
                ("Invoice number", invoice.invoice_number),
                ("Amount received", f"{payment.currency} {payment.amount:,.2f}"),
                ("Payment method", (payment.payment_method or "—").replace("_", " ")),
                ("Paid at", f"{paid_at:%d %b %Y, %H:%M UTC}"),
                ("Outstanding balance", f"{invoice.currency} {invoice.amount_due:,.2f}"),
            ],
            footer_note="Keep this receipt for your records. If anything looks "
            "incorrect, reply to your account manager or contact support.",
            preheader=f"Receipt {payment.receipt_number}: {payment.currency} "
            f"{payment.amount:,.2f} received.",
        )
        body, body_html = _billing_email_bodies(**common)

        sent = _try_send_email(
            subject=subject, recipients=recipients, body=body, body_html=body_html
        )
        payment.receipt_sent_to_email = ", ".join(recipients) if recipients else None
        payment.receipt_sent_at = datetime.now(timezone.utc) if sent else None
        if sent:
            self.db.commit()

    def _dispatch_overdue_email(self, tenant: Tenant, invoice: SubscriptionInvoice) -> None:
        recipients = _resolve_billing_recipients(tenant)
        subject = f"Overdue invoice {invoice.invoice_number} — please settle to avoid interruption"
        common = dict(
            title="Your invoice is overdue",
            intro=f"Hello {tenant.billing_contact_name or tenant.name}, invoice "
            f"{invoice.invoice_number} is now past its due date. Please settle it as "
            "soon as possible to keep your subscription active.",
            highlight_label="Amount due",
            highlight_value=f"{invoice.currency} {invoice.amount_due:,.2f}",
            highlight_caption=f"Was due on {invoice.due_date:%d %b %Y}",
            details_heading="Invoice details",
            details=[
                ("Invoice number", invoice.invoice_number),
                ("Amount due", f"{invoice.currency} {invoice.amount_due:,.2f}"),
                ("Original due date", f"{invoice.due_date:%d %b %Y}"),
            ],
            cta_label="Settle invoice now",
            cta_url=_billing_portal_url(),
            footer_note="To avoid any interruption to your service, please make payment "
            "at your earliest convenience. If you've already paid, kindly disregard this notice.",
            preheader=f"Overdue: {invoice.currency} {invoice.amount_due:,.2f} on "
            f"invoice {invoice.invoice_number}.",
        )
        body, body_html = _billing_email_bodies(**common)
        _try_send_email(
            subject=subject, recipients=recipients, body=body, body_html=body_html
        )

    # ==================================================================
    # CHECKOUT SUPPORT — ensure there's an invoice to pay
    # ==================================================================

    def get_active_subscription(self, tenant_id: int) -> Optional[TenantSubscription]:
        """Return the tenant's current ACTIVE/TRIALING/PENDING/PAST_DUE subscription."""
        return (
            self.db.query(TenantSubscription)
            .filter(
                TenantSubscription.tenant_id == tenant_id,
                TenantSubscription.status.in_(
                    [
                        SubscriptionStatus.ACTIVE,
                        SubscriptionStatus.TRIALING,
                        SubscriptionStatus.PENDING,
                        SubscriptionStatus.PAST_DUE,
                    ]
                ),
            )
            .order_by(TenantSubscription.id.desc())
            .first()
        )

    def get_or_create_open_invoice(self, tenant_id: int) -> SubscriptionInvoice:
        """
        Return an open (payable) invoice for the tenant's current subscription,
        issuing one if none exists. Used by the checkout + manual-payment flows
        so the tenant always has something concrete to pay against.
        """
        subscription = self.get_active_subscription(tenant_id)
        if subscription is None:
            raise BadRequestError(
                message="No active subscription found. Select a plan before paying."
            )

        open_invoice = (
            self.db.query(SubscriptionInvoice)
            .filter(
                SubscriptionInvoice.subscription_id == subscription.id,
                SubscriptionInvoice.status.in_(
                    [
                        SubscriptionInvoiceStatus.DRAFT,
                        SubscriptionInvoiceStatus.ISSUED,
                        SubscriptionInvoiceStatus.PARTIALLY_PAID,
                        SubscriptionInvoiceStatus.OVERDUE,
                    ]
                ),
                SubscriptionInvoice.is_deleted.is_(False),
            )
            .order_by(SubscriptionInvoice.id.asc())
            .first()
        )
        if open_invoice is not None:
            return open_invoice

        # No open invoice — issue one for the current period immediately.
        return self.issue_invoice_for_subscription(subscription, send_email=False)

    # ==================================================================
    # MANUAL (bank counter / transfer) PAYMENT + SaaS CONFIRMATION
    # ==================================================================

    def record_manual_payment(
        self,
        invoice_id: int,
        *,
        amount: float | Decimal,
        payment_method: str = "BANK_TRANSFER",
        payer_bank_name: Optional[str] = None,
        payer_account_name: Optional[str] = None,
        payer_reference: Optional[str] = None,
        proof_file_path: Optional[str] = None,
        proof_file_name: Optional[str] = None,
        proof_content_type: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> SubscriptionPayment:
        """
        Record a tenant-submitted manual payment as PENDING (awaiting SaaS
        confirmation). Unlike :meth:`record_payment`, this does NOT touch the
        invoice totals or roll the subscription forward — that happens only
        when a platform admin confirms via :meth:`confirm_manual_payment`.
        """
        invoice = self.get_invoice(invoice_id)
        if invoice.status in {
            SubscriptionInvoiceStatus.PAID,
            SubscriptionInvoiceStatus.CANCELLED,
            SubscriptionInvoiceStatus.REFUNDED,
        }:
            raise BadRequestError(
                message=f"Invoice cannot accept new payments in status {invoice.status}."
            )

        amount_dec = Decimal(str(amount))
        if amount_dec <= 0:
            raise BadRequestError(message="Payment amount must be greater than zero.")

        payment = SubscriptionPayment(
            invoice_id=invoice.id,
            tenant_id=invoice.tenant_id,
            amount=amount_dec,
            currency=invoice.currency,
            payment_method=payment_method or "BANK_TRANSFER",
            provider="MANUAL",
            status=SubscriptionPaymentStatus.PENDING,
            paid_at=datetime.now(timezone.utc),
            payer_bank_name=payer_bank_name,
            payer_account_name=payer_account_name,
            payer_reference=payer_reference,
            proof_file_path=proof_file_path,
            proof_file_name=proof_file_name,
            proof_content_type=proof_content_type,
            notes=notes,
        )
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def confirm_manual_payment(
        self, payment_id: int, *, admin_id: Optional[int] = None
    ) -> SubscriptionPayment:
        """
        Promote a PENDING manual payment to SUCCEEDED (SaaS admin action):
        apply it to the invoice, roll the subscription window forward when the
        invoice is fully paid, and dispatch a receipt.
        """
        payment = (
            self.db.query(SubscriptionPayment)
            .filter(SubscriptionPayment.id == payment_id)
            .first()
        )
        if payment is None:
            raise NotFoundError(message="Payment not found.")
        if payment.status != SubscriptionPaymentStatus.PENDING:
            raise BadRequestError(
                message=f"Only PENDING payments can be confirmed (this one is {payment.status})."
            )

        invoice = self.get_invoice(payment.invoice_id)
        tenant = self.db.query(Tenant).filter(Tenant.id == payment.tenant_id).first()

        payment.status = SubscriptionPaymentStatus.SUCCEEDED
        payment.confirmed_by_admin_id = admin_id
        payment.confirmed_at = datetime.now(timezone.utc)
        payment.paid_at = payment.paid_at or datetime.now(timezone.utc)
        if not payment.receipt_number and tenant is not None:
            payment.receipt_number = _generate_receipt_number(tenant)
        self.db.flush()

        # Apply to the invoice.
        new_paid = (invoice.amount_paid or Decimal("0")) + payment.amount
        invoice.amount_paid = new_paid
        invoice.amount_due = max(Decimal("0"), (invoice.total_amount or Decimal("0")) - new_paid)
        if invoice.amount_due <= Decimal("0"):
            invoice.status = SubscriptionInvoiceStatus.PAID
            invoice.paid_at = payment.confirmed_at
            self._roll_subscription_period_forward(invoice)
        else:
            invoice.status = SubscriptionInvoiceStatus.PARTIALLY_PAID

        self.db.commit()
        self.db.refresh(payment)
        self.db.refresh(invoice)

        if tenant is not None:
            self._dispatch_payment_receipt(tenant, invoice, payment)
        return payment

    def reject_manual_payment(
        self, payment_id: int, *, admin_id: Optional[int] = None, reason: Optional[str] = None
    ) -> SubscriptionPayment:
        """Mark a PENDING manual payment as FAILED with a reason (SaaS action)."""
        payment = (
            self.db.query(SubscriptionPayment)
            .filter(SubscriptionPayment.id == payment_id)
            .first()
        )
        if payment is None:
            raise NotFoundError(message="Payment not found.")
        if payment.status != SubscriptionPaymentStatus.PENDING:
            raise BadRequestError(
                message=f"Only PENDING payments can be rejected (this one is {payment.status})."
            )
        payment.status = SubscriptionPaymentStatus.FAILED
        payment.confirmed_by_admin_id = admin_id
        payment.confirmed_at = datetime.now(timezone.utc)
        payment.rejected_reason = reason or "Rejected by platform administrator."
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def list_pending_payments(self) -> list[SubscriptionPayment]:
        """All PENDING manual payments across every tenant (SaaS review queue)."""
        return (
            self.db.query(SubscriptionPayment)
            .filter(SubscriptionPayment.status == SubscriptionPaymentStatus.PENDING)
            .order_by(SubscriptionPayment.id.desc())
            .all()
        )

    def list_payments(
        self,
        *,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 200,
    ) -> list[SubscriptionPayment]:
        """
        List subscription payments across every tenant for the SaaS lookup
        screen, optionally filtered by status and a free-text search over the
        tenant name, receipt number, and payer/transaction references.
        """
        query = self.db.query(SubscriptionPayment)

        if status:
            try:
                query = query.filter(
                    SubscriptionPayment.status == SubscriptionPaymentStatus(status.upper())
                )
            except ValueError:
                # Unknown status → no rows rather than a 500.
                return []

        if search:
            like = f"%{search.strip()}%"
            # Match tenant name via a subquery of matching tenant ids.
            tenant_ids = [
                t.id
                for t in self.db.query(Tenant.id).filter(Tenant.name.ilike(like)).all()
            ]
            conditions = [
                SubscriptionPayment.receipt_number.ilike(like),
                SubscriptionPayment.payer_reference.ilike(like),
                SubscriptionPayment.transaction_reference.ilike(like),
                SubscriptionPayment.payer_account_name.ilike(like),
            ]
            if tenant_ids:
                conditions.append(SubscriptionPayment.tenant_id.in_(tenant_ids))
            query = query.filter(or_(*conditions))

        return (
            query.order_by(SubscriptionPayment.id.desc()).limit(limit).all()
        )

    def get_payment(self, payment_id: int) -> SubscriptionPayment:
        payment = (
            self.db.query(SubscriptionPayment)
            .filter(SubscriptionPayment.id == payment_id)
            .first()
        )
        if payment is None:
            raise NotFoundError(message="Payment not found.")
        return payment

    # ==================================================================
    # GATEWAY (Flutterwave) PAYMENT — already-verified success path
    # ==================================================================

    def record_gateway_payment(
        self,
        invoice_id: int,
        *,
        amount: float | Decimal,
        provider: str,
        transaction_reference: str,
        raw_payload: Optional[dict] = None,
    ) -> SubscriptionPayment:
        """
        Idempotently record a verified gateway payment. If a payment with the
        same transaction_reference already exists, it is returned unchanged
        (protects against webhook + callback double-processing).
        """
        existing = (
            self.db.query(SubscriptionPayment)
            .filter(SubscriptionPayment.transaction_reference == transaction_reference)
            .first()
        )
        if existing is not None:
            return existing
        return self.record_payment(
            invoice_id,
            amount=amount,
            payment_method="CARD",
            provider=provider,
            transaction_reference=transaction_reference,
            raw_payload=raw_payload,
            send_receipt=True,
        )
