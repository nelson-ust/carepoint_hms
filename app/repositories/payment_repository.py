# app/repositories/payment_repository.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import PaymentStatus
from app.core.exceptions import NotFoundError
from app.models.all_models import Payment
from app.utils.helpers import generate_uuid_str


class PaymentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, payment_id: int) -> Optional[Payment]:
        return (
            self.db.query(Payment)
            .filter(Payment.id == payment_id, Payment.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, payment_id: int) -> Payment:
        p = self.get_by_id(payment_id)
        if not p:
            raise NotFoundError(message="Payment not found.", detail={"payment_id": payment_id})
        return p

    def list_for_invoice(self, invoice_id: int) -> list[Payment]:
        return (
            self.db.query(Payment)
            .filter(Payment.invoice_id == invoice_id, Payment.is_deleted.is_(False))
            .order_by(Payment.id.desc())
            .all()
        )

    def list_payments(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        invoice_id: Optional[int] = None,
        payment_method: Optional[str] = None,
        payment_status: Optional[PaymentStatus] = None,
    ) -> tuple[list[Payment], int]:
        query = self.db.query(Payment).filter(Payment.is_deleted.is_(False))
        if invoice_id is not None:
            query = query.filter(Payment.invoice_id == invoice_id)
        if payment_method is not None:
            query = query.filter(Payment.payment_method == payment_method)
        if payment_status is not None:
            query = query.filter(Payment.payment_status == payment_status)
        total = query.with_entities(func.count(Payment.id)).scalar() or 0
        items = query.order_by(Payment.id.desc()).offset(skip).limit(limit).all()
        return items, int(total)

    def generate_payment_reference(self) -> str:
        return f"PAY-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:10].upper()}"

    def create(
        self,
        *,
        invoice_id: int,
        amount: Decimal,
        currency: str,
        payment_method: str,
        received_by_staff_id: Optional[int],
        transaction_metadata: Optional[dict],
        note: Optional[str],
    ) -> Payment:
        p = Payment(
            invoice_id=invoice_id,
            received_by_staff_id=received_by_staff_id,
            payment_reference=self.generate_payment_reference(),
            payment_method=payment_method,
            payment_status=PaymentStatus.SUCCESSFUL,
            amount=amount,
            currency=currency,
            paid_at=datetime.now(timezone.utc),
            transaction_metadata=transaction_metadata,
            note=note,
        )
        self.db.add(p)
        self.db.flush()
        self.db.refresh(p)
        return p

    def save(self, p: Payment) -> Payment:
        self.db.add(p)
        self.db.flush()
        self.db.refresh(p)
        return p
