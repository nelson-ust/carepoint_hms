# app/repositories/billing_repository.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.enums import BillingStatus
from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.all_models import (
    BillableService,
    Billing,
    BillingItem,
)
from app.utils.helpers import generate_uuid_str


class BillableServiceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, sid: int) -> Optional[BillableService]:
        return (
            self.db.query(BillableService)
            .filter(BillableService.id == sid, BillableService.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, sid: int) -> BillableService:
        s = self.get_by_id(sid)
        if not s:
            raise NotFoundError(message="Billable service not found.", detail={"id": sid})
        return s

    def get_by_code(self, code: str) -> Optional[BillableService]:
        return (
            self.db.query(BillableService)
            .filter(
                BillableService.code == code.strip().upper(),
                BillableService.is_deleted.is_(False),
            )
            .first()
        )

    def list_services(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
        category: Optional[str] = None,
    ) -> tuple[list[BillableService], int]:
        query = self.db.query(BillableService).filter(BillableService.is_deleted.is_(False))
        if category:
            query = query.filter(BillableService.category == category)
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                func.lower(BillableService.name).like(term),
            )
        total = query.with_entities(func.count(BillableService.id)).scalar() or 0
        items = query.order_by(BillableService.name.asc()).offset(skip).limit(limit).all()
        return items, int(total)

    def create(self, **kwargs) -> BillableService:
        if self.get_by_code(kwargs["code"]):
            raise AlreadyExistsError(
                message="A billable service with this code already exists.",
                detail={"code": kwargs["code"]},
            )
        s = BillableService(**kwargs)
        self.db.add(s)
        self.db.flush()
        self.db.refresh(s)
        return s

    def update(self, s: BillableService, **kwargs) -> BillableService:
        for field, value in kwargs.items():
            if value is not None:
                setattr(s, field, value)
        self.db.add(s)
        self.db.flush()
        self.db.refresh(s)
        return s

    def soft_delete(self, s: BillableService) -> BillableService:
        s.is_deleted = True
        self.db.add(s)
        self.db.flush()
        return s


class BillingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, billing_id: int) -> Optional[Billing]:
        return (
            self.db.query(Billing)
            .options(selectinload(Billing.items))
            .filter(Billing.id == billing_id, Billing.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, billing_id: int) -> Billing:
        b = self.get_by_id(billing_id)
        if not b:
            raise NotFoundError(message="Billing not found.", detail={"billing_id": billing_id})
        return b

    def list_for_visit(self, visit_id: int) -> list[Billing]:
        return (
            self.db.query(Billing)
            .options(selectinload(Billing.items))
            .filter(Billing.visit_id == visit_id, Billing.is_deleted.is_(False))
            .order_by(Billing.id.desc())
            .all()
        )

    def list_billings(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        patient_id: Optional[int] = None,
        visit_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> tuple[list[Billing], int]:
        query = self.db.query(Billing).options(selectinload(Billing.items)).filter(
            Billing.is_deleted.is_(False)
        )
        if patient_id is not None:
            query = query.filter(Billing.patient_id == patient_id)
        if visit_id is not None:
            query = query.filter(Billing.visit_id == visit_id)
        if status is not None:
            query = query.filter(Billing.status == status)

        total = query.with_entities(func.count(Billing.id)).scalar() or 0
        items = query.order_by(Billing.id.desc()).offset(skip).limit(limit).all()
        return items, int(total)

    def generate_billing_no(self) -> str:
        return f"BILL-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create_billing(
        self,
        *,
        patient_id: int,
        visit_id: Optional[int],
        patient_insurance_id: Optional[int],
        notes: Optional[str],
    ) -> Billing:
        b = Billing(
            patient_id=patient_id,
            visit_id=visit_id,
            patient_insurance_id=patient_insurance_id,
            billing_no=self.generate_billing_no(),
            billing_date=datetime.now(timezone.utc),
            status=str(BillingStatus.OPEN),
            gross_amount=Decimal("0"),
            discount_amount=Decimal("0"),
            net_amount=Decimal("0"),
            notes=notes,
        )
        self.db.add(b)
        self.db.flush()
        self.db.refresh(b)
        return b

    def add_item(
        self,
        *,
        billing: Billing,
        service_name: str,
        service_code: Optional[str],
        quantity: Decimal,
        unit_price: Decimal,
        discount_amount: Decimal,
        billable_service_id: Optional[int],
        source_reference: Optional[str],
    ) -> BillingItem:
        line_total = (Decimal(unit_price) * Decimal(quantity)) - Decimal(discount_amount)
        if line_total < 0:
            line_total = Decimal("0")
        item = BillingItem(
            billing_id=billing.id,
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

        # Update parent totals.
        billing.gross_amount = (billing.gross_amount or Decimal("0")) + (Decimal(unit_price) * Decimal(quantity))
        billing.discount_amount = (billing.discount_amount or Decimal("0")) + Decimal(discount_amount)
        billing.net_amount = billing.gross_amount - billing.discount_amount
        self.db.add(billing)
        self.db.flush()
        return item

    def save(self, b: Billing) -> Billing:
        self.db.add(b)
        self.db.flush()
        self.db.refresh(b)
        return b
