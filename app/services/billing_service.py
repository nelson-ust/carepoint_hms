# app/services/billing_service.py
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import BillingStatus
from app.core.exceptions import BadRequestError
from app.models.all_models import BillableService, Billing
from app.repositories.billing_repository import (
    BillableServiceRepository,
    BillingRepository,
)
from app.schemas.billing_schemas import (
    BillableServiceCreateSchema,
    BillableServiceUpdateSchema,
    BillingCreateSchema,
    BillingItemCreateSchema,
)


class BillableServiceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = BillableServiceRepository(db)

    def list(self, *, skip=0, limit=50, search=None, category=None):
        return self.repository.list_services(
            skip=skip, limit=limit, search=search, category=category
        )

    def get(self, sid: int) -> BillableService:
        return self.repository.get_required_by_id(sid)

    def create(self, payload: BillableServiceCreateSchema) -> BillableService:
        s = self.repository.create(**payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(s.id)

    def update(self, sid: int, payload: BillableServiceUpdateSchema) -> BillableService:
        s = self.repository.get_required_by_id(sid)
        updated = self.repository.update(s, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def soft_delete(self, sid: int) -> BillableService:
        s = self.repository.get_required_by_id(sid)
        deleted = self.repository.soft_delete(s)
        self.db.commit()
        return deleted


class BillingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = BillingRepository(db)

    def list_for_visit(self, visit_id: int) -> list[Billing]:
        return self.repository.list_for_visit(visit_id)

    def list_billings(self, **kwargs):
        return self.repository.list_billings(**kwargs)

    def get(self, billing_id: int) -> Billing:
        return self.repository.get_required_by_id(billing_id)

    def create_billing(self, payload: BillingCreateSchema) -> Billing:
        b = self.repository.create_billing(
            patient_id=payload.patient_id,
            visit_id=payload.visit_id,
            patient_insurance_id=payload.patient_insurance_id,
            notes=payload.notes,
        )
        for line in payload.items:
            self.repository.add_item(
                billing=b,
                service_name=line.service_name,
                service_code=line.service_code,
                quantity=Decimal(line.quantity),
                unit_price=Decimal(line.unit_price),
                discount_amount=Decimal(line.discount_amount),
                billable_service_id=line.billable_service_id,
                source_reference=line.source_reference,
            )
        self.db.commit()
        return self.repository.get_required_by_id(b.id)

    def add_item(self, billing_id: int, line: BillingItemCreateSchema) -> Billing:
        billing = self.repository.get_required_by_id(billing_id)
        if billing.status not in {str(BillingStatus.OPEN), str(BillingStatus.DRAFT)}:
            raise BadRequestError(
                message="Cannot add items to a billing that is not OPEN/DRAFT.",
                detail={"status": billing.status},
            )
        self.repository.add_item(
            billing=billing,
            service_name=line.service_name,
            service_code=line.service_code,
            quantity=Decimal(line.quantity),
            unit_price=Decimal(line.unit_price),
            discount_amount=Decimal(line.discount_amount),
            billable_service_id=line.billable_service_id,
            source_reference=line.source_reference,
        )
        self.db.commit()
        return self.repository.get_required_by_id(billing.id)

    def cancel_billing(self, billing_id: int, *, reason: Optional[str] = None) -> Billing:
        billing = self.repository.get_required_by_id(billing_id)
        if billing.status in {str(BillingStatus.SETTLED), str(BillingStatus.INVOICED)}:
            raise BadRequestError(
                message="Cannot cancel an invoiced/settled billing.",
                detail={"status": billing.status},
            )
        billing.status = str(BillingStatus.CANCELLED)
        if reason:
            existing = billing.notes or ""
            billing.notes = (existing + ("\n\n" if existing else "") + f"[CANCELLED] {reason}").strip()
        self.repository.save(billing)
        self.db.commit()
        return self.repository.get_required_by_id(billing.id)
