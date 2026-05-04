# app/services/dispense_service.py
from __future__ import annotations

"""
Service layer for pharmacy dispensing.

Behavior
--------
- For each line: deduct stock from a chosen InventoryStockItem (FEFO when
  unspecified) and post a DISPENSE StockMovement.
- Update PrescriptionItem.quantity_dispensed and the parent prescription
  status (PARTIALLY_DISPENSED / DISPENSED).
- Honor pre-paid policy: refuse to dispense if the prescription has any
  unsettled outstanding charges marked as pre-paid.
"""

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import DispenseStatus, PrescriptionStatus, StockMovementType
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import Dispense, InventoryStockItem
from app.repositories.dispense_repository import DispenseRepository
from app.repositories.inventory_repository import InventoryStockItemRepository
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.stock_movement_repository import StockMovementRepository
from app.schemas.dispense_schema import DispenseCreateSchema
from app.utils.charge_capture import has_outstanding_charges
from app.utils.payment_policy import requires_pre_payment
from app.utils.security_event_util import record_security_event


class DispenseService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DispenseRepository(db)
        self.prescription_repository = PrescriptionRepository(db)
        self.stock_repository = InventoryStockItemRepository(db)
        self.movement_repository = StockMovementRepository(db)

    # ============================================================
    # READ
    # ============================================================

    def list_for_visit(self, visit_id: int, *, skip: int = 0, limit: int = 50):
        return self.repository.list_for_visit(visit_id, skip=skip, limit=limit)

    def list_for_prescription(self, prescription_id: int) -> list[Dispense]:
        return self.repository.list_for_prescription(prescription_id)

    def get(self, dispense_id: int) -> Dispense:
        return self.repository.get_required_by_id(dispense_id)

    # ============================================================
    # CREATE
    # ============================================================

    def create_dispense(
        self,
        payload: DispenseCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Dispense:
        prescription = self.prescription_repository.get_required_by_id(payload.prescription_id)

        if prescription.status in {PrescriptionStatus.CANCELLED}:
            raise BadRequestError(
                message="Cancelled prescriptions cannot be dispensed.",
                detail={"status": str(prescription.status)},
            )

        if prescription.status == PrescriptionStatus.DISPENSED:
            raise BadRequestError(
                message="Prescription is already fully dispensed.",
                detail={"status": str(prescription.status)},
            )

        # Pre-paid policy guard: if pharmacy is pre-paid and the prescription
        # has unsettled pharmacy charges, refuse.
        if requires_pre_payment(source="PHARMACY"):
            if has_outstanding_charges(self.db, visit_id=prescription.visit_id, source_prefix="PRESCRIPTION_ITEM"):
                raise BadRequestError(
                    message="Outstanding pharmacy charges must be settled before dispensing.",
                    detail={"prescription_id": prescription.id, "visit_id": prescription.visit_id},
                )

        # Validate prescription items belong to this prescription.
        items_by_id = {i.id: i for i in self.prescription_repository.items_for_prescription(prescription.id)}

        # Pre-flight check: every line refers to a real prescription item and
        # cumulative dispensed quantity won't exceed prescribed.
        for line in payload.items:
            p_item = items_by_id.get(line.prescription_item_id)
            if p_item is None:
                raise NotFoundError(
                    message="Prescription item not found.",
                    detail={"prescription_item_id": line.prescription_item_id},
                )
            already = Decimal(p_item.quantity_dispensed or 0)
            requested = Decimal(line.quantity_dispensed)
            if already + requested > Decimal(p_item.quantity_prescribed):
                raise BadRequestError(
                    message="Quantity exceeds remaining prescribed amount.",
                    detail={
                        "prescription_item_id": p_item.id,
                        "already_dispensed": str(already),
                        "requested": str(requested),
                        "prescribed": str(p_item.quantity_prescribed),
                    },
                )

        # Create the dispense header first.
        dispense = self.repository.create_dispense(
            prescription_id=prescription.id,
            dispensed_by_staff_id=payload.dispensed_by_staff_id,
            note=payload.note,
        )

        # Process each line: pick stock, decrement, post movement, update line.
        for line in payload.items:
            p_item = items_by_id[line.prescription_item_id]

            stock_item = self._pick_stock_item(
                drug_id=p_item.drug_id,
                stock_item_id=line.stock_item_id,
                store_id=payload.store_id,
            )
            if stock_item is None:
                raise BadRequestError(
                    message="No stock available for the selected drug.",
                    detail={
                        "prescription_item_id": p_item.id,
                        "drug_id": p_item.drug_id,
                    },
                )

            quantity = Decimal(line.quantity_dispensed)
            if Decimal(stock_item.quantity_on_hand or 0) < quantity:
                raise BadRequestError(
                    message="Insufficient stock for dispense.",
                    detail={
                        "stock_item_id": stock_item.id,
                        "available": str(stock_item.quantity_on_hand),
                        "requested": str(quantity),
                    },
                )

            # Deduct stock.
            self.stock_repository.adjust_quantity(stock_item, -quantity)
            self.movement_repository.create(
                store_id=stock_item.store_id,
                stock_item_id=stock_item.id,
                movement_type=StockMovementType.DISPENSE,
                quantity=quantity,
                balance_after=Decimal(stock_item.quantity_on_hand),
                reference_no=dispense.dispense_no,
                note=line.note or f"Dispense for prescription {prescription.prescription_no}",
                performed_by_staff_id=payload.dispensed_by_staff_id,
            )

            # Append dispense item.
            self.repository.add_item(
                dispense_id=dispense.id,
                prescription_item_id=p_item.id,
                quantity_dispensed=quantity,
                note=line.note,
            )

            # Update prescription item totals.
            p_item.quantity_dispensed = Decimal(p_item.quantity_dispensed or 0) + quantity
            self.prescription_repository.save_item(p_item)

        # Roll up dispense + prescription status.
        items_for_dispense_qty_total = sum(
            Decimal(i.quantity_dispensed or 0) for i in (dispense.items or [])
        )
        if items_for_dispense_qty_total > 0:
            dispense.status = DispenseStatus.DISPENSED
        else:
            dispense.status = DispenseStatus.PARTIAL
        self.repository.save(dispense)

        self.prescription_repository.recompute_prescription_status(prescription)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="PRESCRIPTION_DISPENSED",
            severity="INFO",
            event_detail=(
                f"Dispense {dispense.dispense_no} posted against prescription "
                f"{prescription.prescription_no}."
            ),
            event_metadata={
                "dispense_id": dispense.id,
                "prescription_id": prescription.id,
                "visit_id": prescription.visit_id,
                "line_count": len(payload.items),
            },
        )

        self.db.commit()
        return self.repository.get_required_by_id(dispense.id)

    # ============================================================
    # INTERNAL
    # ============================================================

    def _pick_stock_item(
        self,
        *,
        drug_id: int,
        stock_item_id: Optional[int],
        store_id: Optional[int],
    ) -> Optional[InventoryStockItem]:
        if stock_item_id is not None:
            stock = self.stock_repository.get_required_by_id(stock_item_id)
            if stock.drug_id != drug_id:
                raise BadRequestError(
                    message="Stock item is not for the prescribed drug.",
                    detail={"stock_item_id": stock_item_id, "drug_id": drug_id},
                )
            return stock
        return self.stock_repository.find_first_dispensable_for_drug(drug_id, store_id=store_id)
