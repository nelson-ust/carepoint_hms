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


def _try_send_email(*, subject: str, recipients: list[str], body: str) -> bool:
    """Best-effort email delivery. Failures are logged, not raised."""
    if not recipients:
        return False
    try:
        from app.utils.email_utils import send_email  # type: ignore
    except Exception:
        logger.warning("send_email helper unavailable; billing email skipped.")
        return False
    try:
        send_email(subject=subject, recipients=recipients, body_text=body)
        return True
    except Exception as exc:
        logger.warning("Billing email delivery failed: %s", exc)
        return False


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

        # Determine the next period.
        now = datetime.now(timezone.utc)
        prev_end = subscription.current_period_end or now
        if prev_end.tzinfo is None:
            prev_end = prev_end.replace(tzinfo=timezone.utc)
        period_start = prev_end if prev_end > now else now
        period_end = _period_end(plan, period_start)

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

        plan_amount: Decimal = Decimal(plan.price or 0)
        currency = str(plan.currency or "NGN").upper()

        line_items = [
            {
                "description": f"{plan.name} subscription ({plan.interval})",
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
            plan_interval_snapshot=str(getattr(plan.interval, "value", plan.interval) or "MONTHLY"),
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
        body = (
            f"Hello {tenant.billing_contact_name or tenant.name},\n\n"
            f"Your CarePoint HMS subscription is due for renewal.\n\n"
            f"Plan:        {plan.name} ({plan.code})\n"
            f"Interval:    {invoice.plan_interval_snapshot}\n"
            f"Period:      {invoice.period_start:%Y-%m-%d} to {invoice.period_end:%Y-%m-%d}\n"
            f"Amount due:  {invoice.currency} {invoice.amount_due:.2f}\n"
            f"Due date:    {invoice.due_date:%Y-%m-%d}\n\n"
            f"Invoice number: {invoice.invoice_number}\n\n"
            f"Please settle the invoice before the due date to avoid any "
            f"interruption of service. If you have already paid, please "
            f"disregard this message.\n\n"
            f"— The CarePoint HMS Team"
        )

        sent = _try_send_email(subject=subject, recipients=recipients, body=body)
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
        body = (
            f"Hello {tenant.billing_contact_name or tenant.name},\n\n"
            f"We've received your payment. Thank you!\n\n"
            f"Receipt number:  {payment.receipt_number}\n"
            f"Invoice number:  {invoice.invoice_number}\n"
            f"Amount received: {payment.currency} {payment.amount:.2f}\n"
            f"Method:          {payment.payment_method}\n"
            f"Paid at:         {payment.paid_at:%Y-%m-%d %H:%M UTC}\n"
            f"Outstanding:     {invoice.currency} {invoice.amount_due:.2f}\n\n"
            f"This serves as your official receipt.\n\n"
            f"— The CarePoint HMS Team"
        )

        sent = _try_send_email(subject=subject, recipients=recipients, body=body)
        payment.receipt_sent_to_email = ", ".join(recipients) if recipients else None
        payment.receipt_sent_at = datetime.now(timezone.utc) if sent else None
        if sent:
            self.db.commit()

    def _dispatch_overdue_email(self, tenant: Tenant, invoice: SubscriptionInvoice) -> None:
        recipients = _resolve_billing_recipients(tenant)
        subject = f"Overdue invoice {invoice.invoice_number} — please settle to avoid interruption"
        body = (
            f"Hello {tenant.billing_contact_name or tenant.name},\n\n"
            f"Invoice {invoice.invoice_number} is now overdue.\n"
            f"Amount due: {invoice.currency} {invoice.amount_due:.2f}\n"
            f"Due date:   {invoice.due_date:%Y-%m-%d}\n\n"
            f"Please settle this invoice as soon as possible to avoid any "
            f"interruption to your CarePoint HMS subscription.\n\n"
            f"— The CarePoint HMS Team"
        )
        _try_send_email(subject=subject, recipients=recipients, body=body)
