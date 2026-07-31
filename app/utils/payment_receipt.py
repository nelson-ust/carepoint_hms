# app/utils/payment_receipt.py
from __future__ import annotations

"""
Generic patient payment-receipt notifier.

Sends a payment confirmation (email + in-app) to a patient for ANY successful
payment method — cash, POS, card, bank transfer, mobile money, etc. Membership
-card debits already send their own richer receipt (with remaining balance) via
``MembershipCardService.debit_card``, so callers skip this helper for that
method to avoid a duplicate.

Everything here is best-effort: a missing patient email, an unconfigured SMTP
transport, or a template hiccup must never roll back or block a payment.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import NotificationChannel
from app.models.all_models import NotificationTemplate, Patient
from app.schemas.notification_schema import NotificationDispatchSchema
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

PAYMENT_RECEIPT_TEMPLATE_CODE = "PAYMENT_RECEIPT"

_SUBJECT = "Payment received — {amount}"
_BODY = (
    "Dear {patient_name},\n\n"
    "We confirm receipt of your payment.\n\n"
    "Amount: {amount}\n"
    "Paid for: {purpose}\n"
    "Payment method: {method}\n"
    "Date & time: {transaction_date}\n"
    "Reference: {reference}\n"
    "{balance_line}"
    "\nThank you,\n{hospital_name}"
)


def _hospital_name() -> str:
    from app.core.multitenancy import get_current_tenant

    try:
        tenant = get_current_tenant()
        if tenant and getattr(tenant, "name", None):
            return tenant.name
    except Exception:
        pass
    return "Your hospital"


def _humanize_method(method: Optional[str]) -> str:
    if not method:
        return "Payment"
    return method.replace("_", " ").title()


def _ensure_template(svc: NotificationService) -> Optional[NotificationTemplate]:
    try:
        existing = svc.template_repository.get_by_code(PAYMENT_RECEIPT_TEMPLATE_CODE)
        if existing is not None:
            return existing
        template = NotificationTemplate(
            name="Payment Receipt",
            code=PAYMENT_RECEIPT_TEMPLATE_CODE,
            channel=NotificationChannel.EMAIL,
            subject_template=_SUBJECT,
            body_template=_BODY,
        )
        svc.db.add(template)
        svc.db.commit()
        svc.db.refresh(template)
        return template
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not ensure payment-receipt template: %s", exc)
        try:
            svc.db.rollback()
        except Exception:
            pass
        return None


def send_payment_receipt(
    db: Session,
    *,
    patient_id: Optional[int],
    amount: Decimal,
    purpose: str,
    method: Optional[str],
    reference: str,
    paid_at: Optional[datetime] = None,
    balance_after: Optional[Decimal] = None,
    currency: str = "NGN",
    actor_user_id: Optional[int] = None,
) -> None:
    """Send an email + in-app payment receipt to the patient (best-effort)."""
    if not patient_id:
        return

    svc = NotificationService(db)
    template = _ensure_template(svc)
    if template is None:
        return

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    patient_name = "Patient"
    if patient is not None:
        parts = [getattr(patient, "first_name", "") or "", getattr(patient, "last_name", "") or ""]
        patient_name = " ".join(p for p in parts if p).strip() or "Patient"

    when = paid_at or datetime.utcnow()
    balance_line = ""
    if balance_after is not None:
        balance_line = f"Remaining balance: {currency} {Decimal(str(balance_after)):,.2f}\n"

    context = {
        "patient_name": patient_name,
        "amount": f"{currency} {Decimal(str(amount or 0)):,.2f}",
        "purpose": purpose or "Hospital services",
        "method": _humanize_method(method),
        "transaction_date": when.strftime("%d %b %Y, %I:%M %p"),
        "reference": reference or "N/A",
        "balance_line": balance_line,
        "hospital_name": _hospital_name(),
    }

    for channel in ("EMAIL", "IN_APP"):
        try:
            svc.dispatch_from_template(
                payload=NotificationDispatchSchema(
                    template_code=PAYMENT_RECEIPT_TEMPLATE_CODE,
                    patient_id=patient_id,
                    channel_override=channel,
                    context=context,
                ),
                actor_user_id=actor_user_id,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to send %s payment receipt: %s", channel, exc)
