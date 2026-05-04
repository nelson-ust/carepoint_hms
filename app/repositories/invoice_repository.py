# app/repositories/invoice_repository.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.enums import InvoiceStatus
from app.core.exceptions import NotFoundError
from app.models.all_models import Invoice, InvoiceItem
from app.utils.helpers import generate_uuid_str


class InvoiceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, invoice_id: int) -> Optional[Invoice]:
        return (
            self.db.query(Invoice)
            .options(selectinload(Invoice.items))
            .filter(Invoice.id == invoice_id, Invoice.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, invoice_id: int) -> Invoice:
        i = self.get_by_id(invoice_id)
        if not i:
            raise NotFoundError(message="Invoice not found.", detail={"invoice_id": invoice_id})
        return i

    def list_for_visit(self, visit_id: int) -> list[Invoice]:
        return (
            self.db.query(Invoice)
            .options(selectinload(Invoice.items))
            .filter(Invoice.visit_id == visit_id, Invoice.is_deleted.is_(False))
            .order_by(Invoice.id.desc())
            .all()
        )

    def list_invoices(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        patient_id: Optional[int] = None,
        visit_id: Optional[int] = None,
        status: Optional[InvoiceStatus] = None,
    ) -> tuple[list[Invoice], int]:
        query = (
            self.db.query(Invoice)
            .options(selectinload(Invoice.items))
            .filter(Invoice.is_deleted.is_(False))
        )
        if patient_id is not None:
            query = query.filter(Invoice.patient_id == patient_id)
        if visit_id is not None:
            query = query.filter(Invoice.visit_id == visit_id)
        if status is not None:
            query = query.filter(Invoice.status == status)
        total = query.with_entities(func.count(Invoice.id)).scalar() or 0
        items = query.order_by(Invoice.id.desc()).offset(skip).limit(limit).all()
        return items, int(total)

    def generate_invoice_no(self) -> str:
        return f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create_invoice(
        self,
        *,
        patient_id: int,
        visit_id: Optional[int],
        billing_id: Optional[int],
        payer_id: Optional[int],
        due_date: Optional[datetime],
        note: Optional[str],
    ) -> Invoice:
        invoice = Invoice(
            patient_id=patient_id,
            visit_id=visit_id,
            billing_id=billing_id,
            payer_id=payer_id,
            invoice_no=self.generate_invoice_no(),
            status=InvoiceStatus.ISSUED,
            invoice_date=datetime.now(timezone.utc),
            due_date=due_date,
            subtotal_amount=Decimal("0"),
            discount_amount=Decimal("0"),
            tax_amount=Decimal("0"),
            total_amount=Decimal("0"),
            amount_paid=Decimal("0"),
            balance_due=Decimal("0"),
            note=note,
        )
        self.db.add(invoice)
        self.db.flush()
        self.db.refresh(invoice)
        return invoice

    def add_item(
        self,
        *,
        invoice: Invoice,
        service_name: str,
        service_code: Optional[str],
        quantity: Decimal,
        unit_price: Decimal,
        discount_amount: Decimal,
        billable_service_id: Optional[int],
        source_reference: Optional[str],
    ) -> InvoiceItem:
        line_total = (Decimal(unit_price) * Decimal(quantity)) - Decimal(discount_amount)
        if line_total < 0:
            line_total = Decimal("0")
        item = InvoiceItem(
            invoice_id=invoice.id,
            billable_service_id=billable_service_id,
            service_name=service_name,
            service_code=service_code,
            quantity=quantity,
            unit_price=unit_price,
            discount_amount=discount_amount,
            line_total=line_total,
            source_reference=source_reference,
        )
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def save(self, invoice: Invoice) -> Invoice:
        self.db.add(invoice)
        self.db.flush()
        self.db.refresh(invoice)
        return invoice

    def recompute_totals(self, invoice: Invoice) -> Invoice:
        items = (
            self.db.query(InvoiceItem)
            .filter(InvoiceItem.invoice_id == invoice.id, InvoiceItem.is_deleted.is_(False))
            .all()
        )
        subtotal = sum((Decimal(i.unit_price) * Decimal(i.quantity)) for i in items) or Decimal("0")
        discount = sum(Decimal(i.discount_amount) for i in items) or Decimal("0")
        invoice.subtotal_amount = subtotal
        invoice.discount_amount = discount
        invoice.total_amount = subtotal - discount + (invoice.tax_amount or Decimal("0"))
        invoice.balance_due = (invoice.total_amount or Decimal("0")) - (invoice.amount_paid or Decimal("0"))
        self.db.add(invoice)
        self.db.flush()
        self.db.refresh(invoice)
        return invoice
