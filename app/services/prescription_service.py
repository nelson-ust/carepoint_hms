# app/services/prescription_service.py
from __future__ import annotations

"""
Service layer for prescription authoring.

Lifecycle
---------
PRESCRIBED -> PARTIALLY_DISPENSED -> DISPENSED
PRESCRIBED -> CANCELLED
"""

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import PrescriptionStatus, VisitStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import Prescription
from app.repositories.drug_repository import DrugRepository
from app.repositories.prescription_repository import PrescriptionRepository
from app.schemas.prescription_schema import (
    PrescriptionCreateSchema,
)
from app.utils.charge_capture import (
    add_charge,
    find_billable_service,
    get_or_create_open_billing,
)
from app.utils.payment_policy import requires_pre_payment
from app.utils.security_event_util import record_security_event
from app.utils.visit_routing import route_visit_to_next_sdp


class PrescriptionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PrescriptionRepository(db)
        self.drug_repository = DrugRepository(db)

    # ============================================================
    # READ
    # ============================================================

    def list_for_visit(self, visit_id: int, *, skip: int = 0, limit: int = 50):
        return self.repository.list_for_visit(visit_id, skip=skip, limit=limit)

    def list_pharmacy_worklist(self, *, skip=0, limit=50):
        return self.repository.list_pharmacy_worklist(skip=skip, limit=limit)

    def get(self, prescription_id: int) -> Prescription:
        return self.repository.get_required_by_id(prescription_id)

    # ============================================================
    # CREATE
    # ============================================================

    def create_prescription(
        self,
        payload: PrescriptionCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Prescription:
        visit = self.repository.get_visit(payload.visit_id)
        if not visit:
            raise NotFoundError(message="Visit not found.", detail={"visit_id": payload.visit_id})
        if visit.status in {VisitStatus.COMPLETED, VisitStatus.CANCELLED}:
            raise BadRequestError(
                message="Cannot prescribe drugs for a closed visit.",
                detail={"visit_status": str(visit.status)},
            )

        items_payload: list[dict] = []
        drugs_by_id = {}
        for entry in payload.items:
            drug = self.drug_repository.get_required_by_id(entry.drug_id)
            drugs_by_id[drug.id] = drug
            items_payload.append({
                "drug_id": drug.id,
                "dosage": entry.dosage,
                "frequency": entry.frequency,
                "duration": entry.duration,
                "route": entry.route,
                "quantity_prescribed": Decimal(entry.quantity_prescribed),
                "instructions": entry.instructions,
            })

        prescription = self.repository.create_prescription(
            visit_id=visit.id,
            consultation_id=payload.consultation_id,
            prescribed_by_staff_id=payload.prescribed_by_staff_id,
            note=payload.note,
            items_payload=items_payload,
        )

        # Auto-capture charges (one billing line per prescribed drug).
        if payload.auto_capture_charge:
            billing = get_or_create_open_billing(self.db, visit=visit)
            for item in self.repository.items_for_prescription(prescription.id):
                drug = drugs_by_id.get(item.drug_id)
                if drug is None:
                    continue
                unit_price = Decimal(drug.unit_price or 0)
                billable = find_billable_service(self.db, code=f"DRUG-{drug.sku}" if drug.sku else None)
                add_charge(
                    self.db,
                    billing=billing,
                    service_name=f"Drug: {drug.name}"
                    + (f" ({drug.strength})" if drug.strength else ""),
                    service_code=f"DRUG-{drug.sku or drug.id}",
                    unit_price=unit_price,
                    quantity=Decimal(item.quantity_prescribed),
                    billable_service_id=billable.id if billable else None,
                    source_reference=f"PRESCRIPTION_ITEM:{item.id}",
                )

        # Routing.
        next_sdp_id: Optional[int] = None
        if requires_pre_payment(source="PHARMACY"):
            next_sdp_id = (
                payload.route_to_cashier_service_delivery_point_id
                or payload.route_to_pharmacy_service_delivery_point_id
            )
        else:
            next_sdp_id = (
                payload.route_to_pharmacy_service_delivery_point_id
                or payload.route_to_cashier_service_delivery_point_id
            )

        if next_sdp_id is not None:
            route_visit_to_next_sdp(
                self.db,
                visit_id=visit.id,
                target_service_delivery_point_id=next_sdp_id,
                routed_by_id=actor_user_id,
                notes="Routed by prescription.",
            )

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="PRESCRIPTION_CREATED",
            severity="INFO",
            event_detail=(
                f"Prescription {prescription.prescription_no} created for visit {visit.id}."
            ),
            event_metadata={
                "prescription_id": prescription.id,
                "visit_id": visit.id,
                "item_count": len(items_payload),
            },
        )

        self.db.commit()
        return self.repository.get_required_by_id(prescription.id)

    # ============================================================
    # CANCEL
    # ============================================================

    def cancel_prescription(
        self,
        prescription_id: int,
        *,
        reason: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> Prescription:
        prescription = self.repository.get_required_by_id(prescription_id)
        if prescription.status in {PrescriptionStatus.DISPENSED, PrescriptionStatus.CANCELLED}:
            raise BadRequestError(
                message="Prescription is already in a terminal state.",
                detail={"status": str(prescription.status)},
            )
        prescription.status = PrescriptionStatus.CANCELLED
        if reason:
            existing = prescription.note or ""
            prescription.note = (existing + ("\n\n" if existing else "") + f"[CANCELLED] {reason}").strip()
        self.repository.save(prescription)
        self.db.commit()
        return self.repository.get_required_by_id(prescription.id)
