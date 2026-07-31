# app/services/invoice_service.py
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import BillingStatus, InvoiceStatus, PaymentStatus
from app.core.exceptions import BadRequestError
from app.models.all_models import Invoice, Payment
from app.repositories.billing_repository import BillingRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.invoice_schema import InvoiceIssueFromBillingSchema
from app.utils.security_event_util import record_security_event


class InvoiceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = InvoiceRepository(db)
        self.billing_repository = BillingRepository(db)

    # ============================================================
    # READ
    # ============================================================

    def list_for_visit(self, visit_id: int) -> list[Invoice]:
        return self.repository.list_for_visit(visit_id)

    def list_invoices(self, **kwargs):
        status = kwargs.pop("status", None)
        if status:
            kwargs["status"] = InvoiceStatus(status)
        return self.repository.list_invoices(**kwargs)

    def get(self, invoice_id: int) -> Invoice:
        return self.repository.get_required_by_id(invoice_id)

    # ============================================================
    # ISSUE FROM BILLING
    # ============================================================

    def issue_from_billing(
        self,
        payload: InvoiceIssueFromBillingSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Invoice:
        billing = self.billing_repository.get_required_by_id(payload.billing_id)
        if billing.status not in {str(BillingStatus.OPEN), str(BillingStatus.DRAFT)}:
            raise BadRequestError(
                message="Only OPEN/DRAFT billings can be invoiced.",
                detail={"status": billing.status},
            )
        if not (billing.items or []):
            raise BadRequestError(message="Billing has no items to invoice.")

        invoice = self.repository.create_invoice(
            patient_id=billing.patient_id,
            visit_id=billing.visit_id,
            billing_id=billing.id,
            payer_id=payload.payer_id,
            due_date=payload.due_date,
            note=payload.note,
        )

        for line in (billing.items or []):
            if line.is_deleted:
                continue
            self.repository.add_item(
                invoice=invoice,
                service_name=line.service_name,
                service_code=line.service_code,
                quantity=Decimal(line.quantity),
                unit_price=Decimal(line.unit_price),
                discount_amount=Decimal(line.discount_amount),
                billable_service_id=line.billable_service_id,
                source_reference=line.source_reference,
            )

        self.repository.recompute_totals(invoice)

        # Carry forward incremental payments already taken against the charge
        # sheet during the visit, so the final invoice reflects all services
        # while the outstanding balance is only the still-unpaid portion.
        carried_paid = Decimal("0")
        for bp in (billing.billing_payments or []):
            if bp.is_deleted or bp.payment_status != PaymentStatus.SUCCESSFUL:
                continue
            if bp.invoice_id:  # already carried
                continue
            carried = Payment(
                invoice_id=invoice.id,
                amount=Decimal(str(bp.amount or 0)),
                currency=bp.currency or "NGN",
                payment_method=bp.payment_method,
                payment_status=PaymentStatus.SUCCESSFUL,
                payment_reference=bp.payment_reference,
                paid_at=bp.paid_at,
                received_by_staff_id=bp.received_by_staff_id,
                transaction_metadata=bp.transaction_metadata,
                note=(bp.note or "Carried forward from visit charge-sheet payment."),
            )
            self.db.add(carried)
            bp.invoice_id = invoice.id
            self.db.add(bp)
            carried_paid += Decimal(str(bp.amount or 0))

        if carried_paid > 0:
            self.db.flush()
            invoice.amount_paid = (invoice.amount_paid or Decimal("0")) + carried_paid
            invoice.balance_due = (invoice.total_amount or Decimal("0")) - invoice.amount_paid
            if invoice.balance_due <= Decimal("0"):
                invoice.balance_due = Decimal("0")
                invoice.status = InvoiceStatus.PAID
            else:
                invoice.status = InvoiceStatus.PARTIALLY_PAID
            self.repository.save(invoice)

        # Mark billing as INVOICED so it cannot be re-invoiced.
        billing.status = str(BillingStatus.INVOICED)
        self.billing_repository.save(billing)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="INVOICE_ISSUED",
            severity="INFO",
            event_detail=f"Invoice {invoice.invoice_no} issued from billing {billing.billing_no}.",
            event_metadata={
                "invoice_id": invoice.id,
                "billing_id": billing.id,
                "patient_id": invoice.patient_id,
            },
        )

        # INSURANCE CLAIM AUTOMATION
        # If the patient has insurance, create a draft claim automatically.
        if billing.patient_insurance_id:
            from app.services.insurance_claim_service import InsuranceClaimService
            from app.schemas.insurance_claim_schemas import InsuranceClaimCreateSchema, InsuranceClaimItemCreateSchema
            
            claim_service = InsuranceClaimService(self.db)
            
            # Prepare items for claim
            claim_items = []
            for inv_item in invoice.items:
                if inv_item.is_deleted:
                    continue
                claim_items.append(InsuranceClaimItemCreateSchema(
                    invoice_item_id=inv_item.id,
                    billable_service_id=inv_item.billable_service_id,
                    service_date=invoice.invoice_date.date() if invoice.invoice_date else None,
                    description=inv_item.service_name,
                    quantity=inv_item.quantity,
                    unit_price=inv_item.unit_price,
                    procedure_code=inv_item.service_code
                ))
            
            if claim_items:
                try:
                    claim_service.create_claim(
                        payload=InsuranceClaimCreateSchema(
                            patient_id=invoice.patient_id,
                            patient_insurance_id=billing.patient_insurance_id,
                            insurance_provider_id=billing.patient_insurance.insurance_provider_id,
                            visit_id=invoice.visit_id,
                            invoice_id=invoice.id,
                            facility_id=billing.facility_id or 1,
                            service_date=invoice.invoice_date.date() if invoice.invoice_date else None,
                            items=claim_items
                        ),
                        actor_user_id=actor_user_id
                    )
                except Exception as e:
                    # Log error but don't fail invoice issuance
                    print(f"Error creating automatic insurance claim: {e}")

        self.db.commit()
        return self.repository.get_required_by_id(invoice.id)

    def issue_for_visit(
        self,
        visit_id: int,
        *,
        actor_user_id: Optional[int] = None,
        payer_id: Optional[int] = None,
        due_date=None,
        note: Optional[str] = None,
    ) -> Invoice:
        """
        Finalize a visit's billing: issue a single invoice from the visit's
        OPEN/DRAFT charge sheet (carrying forward any partial payments already
        taken). Idempotent-ish: if the charge sheet is already invoiced, the
        existing invoice is returned.
        """
        billings = [
            b
            for b in self.billing_repository.list_for_visit(visit_id)
            if not b.is_deleted and b.status != str(BillingStatus.CANCELLED)
        ]
        if not billings:
            raise BadRequestError(message="This visit has no charges to invoice.")

        open_billing = next(
            (b for b in billings if b.status in {str(BillingStatus.OPEN), str(BillingStatus.DRAFT)}),
            None,
        )
        if open_billing is None:
            # Already invoiced — return the existing invoice if present.
            for b in billings:
                for inv in (b.invoices or []):
                    if not inv.is_deleted:
                        return self.repository.get_required_by_id(inv.id)
            raise BadRequestError(message="This visit's billing has already been finalized.")

        return self.issue_from_billing(
            InvoiceIssueFromBillingSchema(
                billing_id=open_billing.id,
                payer_id=payer_id,
                due_date=due_date,
                note=note,
            ),
            actor_user_id=actor_user_id,
        )

    def void_invoice(
        self,
        invoice_id: int,
        *,
        reason: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> Invoice:
        invoice = self.repository.get_required_by_id(invoice_id)
        if invoice.status in {InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID}:
            raise BadRequestError(
                message="An invoice with payments cannot be voided. Refund payments first.",
                detail={"status": str(invoice.status)},
            )
        if invoice.status in {InvoiceStatus.VOIDED, InvoiceStatus.CANCELLED}:
            raise BadRequestError(
                message="Invoice is already void/cancelled.",
                detail={"status": str(invoice.status)},
            )
        invoice.status = InvoiceStatus.VOIDED
        if reason:
            invoice.note = (
                (invoice.note + "\n" if invoice.note else "") + f"[VOIDED] {reason}"
            ).strip()
        self.repository.save(invoice)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="INVOICE_VOIDED",
            severity="WARNING",
            event_detail=f"Invoice {invoice.invoice_no} voided. Reason: {reason}",
            event_metadata={"invoice_id": invoice.id, "reason": reason},
        )
        self.db.commit()
        return self.repository.get_required_by_id(invoice.id)
