# app/repositories/prescription_repository.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.enums import PrescriptionStatus
from app.core.exceptions import NotFoundError
from app.models.all_models import Prescription, PrescriptionItem, Visit
from app.utils.helpers import generate_uuid_str


class PrescriptionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_visit(self, visit_id: int) -> Optional[Visit]:
        return (
            self.db.query(Visit)
            .filter(Visit.id == visit_id, Visit.is_deleted.is_(False))
            .first()
        )

    def get_by_id(self, prescription_id: int) -> Optional[Prescription]:
        return (
            self.db.query(Prescription)
            .options(selectinload(Prescription.items))
            .filter(Prescription.id == prescription_id, Prescription.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, prescription_id: int) -> Prescription:
        p = self.get_by_id(prescription_id)
        if not p:
            raise NotFoundError(message="Prescription not found.", detail={"prescription_id": prescription_id})
        return p

    def get_item_by_id(self, item_id: int) -> Optional[PrescriptionItem]:
        return (
            self.db.query(PrescriptionItem)
            .filter(PrescriptionItem.id == item_id, PrescriptionItem.is_deleted.is_(False))
            .first()
        )

    def get_required_item_by_id(self, item_id: int) -> PrescriptionItem:
        i = self.get_item_by_id(item_id)
        if not i:
            raise NotFoundError(message="Prescription item not found.", detail={"item_id": item_id})
        return i

    def list_for_visit(
        self, visit_id: int, *, skip: int = 0, limit: int = 50
    ) -> tuple[list[Prescription], int]:
        query = (
            self.db.query(Prescription)
            .options(selectinload(Prescription.items))
            .filter(Prescription.visit_id == visit_id, Prescription.is_deleted.is_(False))
        )
        total = query.with_entities(func.count(Prescription.id)).scalar() or 0
        items = query.order_by(Prescription.id.desc()).offset(skip).limit(limit).all()
        return items, int(total)

    def list_pharmacy_worklist(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Prescription], int]:
        query = (
            self.db.query(Prescription)
            .options(selectinload(Prescription.items))
            .filter(Prescription.is_deleted.is_(False))
            .filter(Prescription.status.in_([
                PrescriptionStatus.PRESCRIBED,
                PrescriptionStatus.PARTIALLY_DISPENSED,
            ]))
        )
        total = query.with_entities(func.count(Prescription.id)).scalar() or 0
        items = query.order_by(Prescription.prescribed_at.asc()).offset(skip).limit(limit).all()
        return items, int(total)

    def generate_prescription_no(self) -> str:
        return f"RX-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create_prescription(
        self,
        *,
        visit_id: int,
        consultation_id: Optional[int],
        prescribed_by_staff_id: Optional[int],
        visit_flow_step_id: Optional[int] = None,
        note: Optional[str],
        items_payload: list[dict],
    ) -> Prescription:
        p = Prescription(
            visit_id=visit_id,
            visit_flow_step_id=visit_flow_step_id,
            consultation_id=consultation_id,
            prescribed_by_staff_id=prescribed_by_staff_id,
            note=note,
            prescription_no=self.generate_prescription_no(),
            status=PrescriptionStatus.PRESCRIBED,
            prescribed_at=datetime.now(timezone.utc),
        )
        self.db.add(p)
        self.db.flush()
        self.db.refresh(p)

        for entry in items_payload:
            item = PrescriptionItem(
                prescription_id=p.id,
                drug_id=entry["drug_id"],
                dosage=entry.get("dosage"),
                frequency=entry.get("frequency"),
                duration=entry.get("duration"),
                route=entry.get("route"),
                quantity_prescribed=entry["quantity_prescribed"],
                quantity_dispensed=0,
                instructions=entry.get("instructions"),
            )
            self.db.add(item)

        self.db.flush()
        self.db.refresh(p)
        return p

    def save(self, p: Prescription) -> Prescription:
        self.db.add(p)
        self.db.flush()
        self.db.refresh(p)
        return p

    def save_item(self, i: PrescriptionItem) -> PrescriptionItem:
        self.db.add(i)
        self.db.flush()
        self.db.refresh(i)
        return i

    def items_for_prescription(self, prescription_id: int) -> list[PrescriptionItem]:
        return (
            self.db.query(PrescriptionItem)
            .filter(
                PrescriptionItem.prescription_id == prescription_id,
                PrescriptionItem.is_deleted.is_(False),
            )
            .all()
        )

    def recompute_prescription_status(self, p: Prescription) -> Prescription:
        items = self.items_for_prescription(p.id)
        if not items:
            return p

        all_dispensed = all(i.quantity_dispensed >= i.quantity_prescribed for i in items)
        any_dispensed = any(i.quantity_dispensed > 0 for i in items)

        if all_dispensed:
            p.status = PrescriptionStatus.DISPENSED
        elif any_dispensed:
            p.status = PrescriptionStatus.PARTIALLY_DISPENSED
        # else: leave as-is.

        self.db.add(p)
        self.db.flush()
        self.db.refresh(p)
        return p
