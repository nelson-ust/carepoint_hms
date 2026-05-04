# app/services/payment_service.py
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import BillingStatus, InvoiceStatus, PaymentStatus
from app.core.exceptions import BadRequestError
from app.models.all_models import Payment
from app.repositories.billing_repository import BillingRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.payment_schema import PaymentReceiveSchema, PaymentRefundSchema
from app.schemas.membership_card_schemas import MembershipCardDebit
from app.services.membership_card_service import MembershipCardService
from app.utils.security_event_util import record_security_event


class PaymentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PaymentRepository(db)
        self.invoice_repository = InvoiceRepository(db)
        self.billing_repository = BillingRepository(db)

    def list_for_invoice(self, invoice_id: int) -> list[Payment]:
        return self.repository.list_for_invoice(invoice_id)

    def list_payments(self, **kwargs):
        status = kwargs.pop("payment_status", None)
        if status:
            kwargs["payment_status"] = PaymentStatus(status)
        return self.repository.list_payments(**kwargs)

    def get(self, payment_id: int) -> Payment:
        return self.repository.get_required_by_id(payment_id)

    def receive_payment(
        self,
        payload: PaymentReceiveSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Payment:
        invoice = self.invoice_repository.get_required_by_id(payload.invoice_id)
        if invoice.status in {InvoiceStatus.VOIDED, InvoiceStatus.CANCELLED}:
            raise BadRequestError(
                message="Cannot receive payment on a voided/cancelled invoice.",
                detail={"status": str(invoice.status)},
            )

        amount = Decimal(payload.amount)
        balance_due = Decimal(invoice.balance_due or 0)
        if amount > balance_due:
            raise BadRequestError(
                message="Payment exceeds the invoice balance due.",
                detail={"balance_due": str(balance_due), "amount": str(amount)},
            )

        # Handle Membership Card Debit if applicable
        if payload.payment_method == "MEMBERSHIP_CARD":
            if not payload.membership_card_id:
                raise BadRequestError("membership_card_id is required for MEMBERSHIP_CARD payment method.")
            
            card_service = MembershipCardService(self.db)
            # Find facility_id - fallback to invoice facility or default
            facility_id = getattr(invoice, "facility_id", None) or 1
            
            card_service.debit_card(
                card_id=payload.membership_card_id,
                payload=MembershipCardDebit(
                    amount=amount,
                    invoice_id=invoice.id,
                    visit_id=invoice.visit_id,
                    narration=f"Payment for invoice {invoice.invoice_no}",
                ),
                processed_by_id=actor_user_id or 1,
                facility_id=facility_id,
            )
            
        # Handle Insurance Payment validation
        if payload.payment_method == "INSURANCE":
            if not invoice.billing_id:
                 raise BadRequestError("Insurance payment method requires an associated billing record.")
            billing = self.billing_repository.get_by_id(invoice.billing_id)
            if not billing or not billing.patient_insurance_id:
                raise BadRequestError("This invoice is not linked to an insurance policy.")

        payment = self.repository.create(
            invoice_id=invoice.id,
            amount=amount,
            currency=payload.currency,
            payment_method=payload.payment_method,
            received_by_staff_id=payload.received_by_staff_id,
            transaction_metadata=payload.transaction_metadata,
            note=payload.note,
        )

        # Update invoice totals.
        invoice.amount_paid = (invoice.amount_paid or Decimal("0")) + amount
        invoice.balance_due = (invoice.total_amount or Decimal("0")) - invoice.amount_paid
        if invoice.balance_due <= Decimal("0"):
            invoice.balance_due = Decimal("0")
            invoice.status = InvoiceStatus.PAID
        else:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
        self.invoice_repository.save(invoice)

        # When the invoice is fully paid, mark the originating billing SETTLED.
        if invoice.status == InvoiceStatus.PAID and invoice.billing_id:
            billing = self.billing_repository.get_by_id(invoice.billing_id)
            if billing is not None:
                billing.status = str(BillingStatus.SETTLED)
                self.billing_repository.save(billing)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="PAYMENT_RECEIVED",
            severity="INFO",
            event_detail=(
                f"Payment {payment.payment_reference} of {payment.amount} {payment.currency} "
                f"received against invoice {invoice.invoice_no}."
            ),
            event_metadata={
                "payment_id": payment.id,
                "invoice_id": invoice.id,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "method": payment.payment_method,
            },
        )

        self.db.commit()
        return self.repository.get_required_by_id(payment.id)

    def refund_payment(
        self,
        payload: PaymentRefundSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Payment:
        payment = self.repository.get_required_by_id(payload.payment_id)
        if payment.payment_status in {PaymentStatus.REVERSED, PaymentStatus.CANCELLED, PaymentStatus.FAILED}:
            raise BadRequestError(
                message="Payment is not in a refundable state.",
                detail={"status": str(payment.payment_status)},
            )

        invoice = self.invoice_repository.get_required_by_id(payment.invoice_id)
        amount = Decimal(payment.amount or 0)

        invoice.amount_paid = (invoice.amount_paid or Decimal("0")) - amount
        if invoice.amount_paid < 0:
            invoice.amount_paid = Decimal("0")
        invoice.balance_due = (invoice.total_amount or Decimal("0")) - invoice.amount_paid
        if invoice.amount_paid <= Decimal("0"):
            invoice.status = InvoiceStatus.ISSUED
        else:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
        self.invoice_repository.save(invoice)

        payment.payment_status = PaymentStatus.REVERSED
        if payload.reason:
            payment.note = (
                (payment.note + "\n" if payment.note else "") + f"[REFUNDED] {payload.reason}"
            ).strip()
        self.repository.save(payment)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="PAYMENT_REFUNDED",
            severity="WARNING",
            event_detail=f"Payment {payment.payment_reference} refunded.",
            event_metadata={"payment_id": payment.id, "invoice_id": invoice.id, "reason": payload.reason},
        )

        self.db.commit()
        return self.repository.get_required_by_id(payment.id)
