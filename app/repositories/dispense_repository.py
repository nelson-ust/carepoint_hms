# app/repositories/dispense_repository.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.enums import DispenseStatus
from app.core.exceptions import NotFoundError
from app.models.all_models import Dispense, DispenseItem
from app.utils.helpers import generate_uuid_str


class DispenseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, dispense_id: int) -> Optional[Dispense]:
        return (
            self.db.query(Dispense)
            .options(selectinload(Dispense.items))
            .filter(Dispense.id == dispense_id, Dispense.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, dispense_id: int) -> Dispense:
        d = self.get_by_id(dispense_id)
        if not d:
            raise NotFoundError(message="Dispense not found.", detail={"dispense_id": dispense_id})
        return d

    def list_for_prescription(self, prescription_id: int) -> list[Dispense]:
        return (
            self.db.query(Dispense)
            .options(selectinload(Dispense.items))
            .filter(
                Dispense.prescription_id == prescription_id,
                Dispense.is_deleted.is_(False),
            )
            .order_by(Dispense.id.desc())
            .all()
        )

    def generate_dispense_no(self) -> str:
        return f"DISP-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create_dispense(
        self,
        *,
        prescription_id: int,
        dispensed_by_staff_id: Optional[int],
        note: Optional[str],
    ) -> Dispense:
        d = Dispense(
            prescription_id=prescription_id,
            dispensed_by_staff_id=dispensed_by_staff_id,
            dispense_no=self.generate_dispense_no(),
            status=DispenseStatus.PENDING,
            dispensed_at=datetime.now(timezone.utc),
            note=note,
        )
        self.db.add(d)
        self.db.flush()
        self.db.refresh(d)
        return d

    def add_item(
        self,
        *,
        dispense_id: int,
        prescription_item_id: int,
        quantity_dispensed: Decimal,
        note: Optional[str] = None,
    ) -> DispenseItem:
        item = DispenseItem(
            dispense_id=dispense_id,
            prescription_item_id=prescription_item_id,
            quantity_dispensed=quantity_dispensed,
            note=note,
        )
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def save(self, d: Dispense) -> Dispense:
        self.db.add(d)
        self.db.flush()
        self.db.refresh(d)
        return d

    def list_for_visit(
        self, visit_id: int, *, skip: int = 0, limit: int = 50
    ):
        # Dispenses are tied to prescriptions, which carry visit_id.
        from app.models.all_models import Prescription
        query = (
            self.db.query(Dispense)
            .options(selectinload(Dispense.items))
            .join(Prescription, Prescription.id == Dispense.prescription_id)
            .filter(
                Prescription.visit_id == visit_id,
                Dispense.is_deleted.is_(False),
                Prescription.is_deleted.is_(False),
            )
        )
        total = query.with_entities(func.count(Dispense.id)).scalar() or 0
        items = query.order_by(Dispense.id.desc()).offset(skip).limit(limit).all()
        return items, int(total)
