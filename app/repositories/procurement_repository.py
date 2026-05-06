from typing import List, Optional, Tuple
import uuid
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.models.all_models import PurchaseRequisition, PurchaseRequisitionItem
from app.schemas.procurement_schemas import PurchaseRequisitionCreateSchema, PurchaseRequisitionUpdateSchema

class ProcurementRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_requisition_by_id(self, requisition_id: int) -> Optional[PurchaseRequisition]:
        return self.db.scalars(
            select(PurchaseRequisition)
            .where(PurchaseRequisition.id == requisition_id)
            .options(joinedload(PurchaseRequisition.items))
        ).first()

    def list_requisitions(
        self, department_id: Optional[int] = None, skip: int = 0, limit: int = 100
    ) -> Tuple[List[PurchaseRequisition], int]:
        stmt = select(PurchaseRequisition)
        if department_id:
            stmt = stmt.where(PurchaseRequisition.department_id == department_id)
        
        stmt = stmt.order_by(PurchaseRequisition.id.desc())
        
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0
        
        items = list(self.db.scalars(stmt.offset(skip).limit(limit)).all())
        return items, total

    def create_requisition(self, data: PurchaseRequisitionCreateSchema) -> PurchaseRequisition:
        # Generate a unique requisition number if not provided
        requisition_no = f"REQ-{uuid.uuid4().hex[:8].upper()}"
        
        requisition = PurchaseRequisition(
            requisition_no=requisition_no,
            facility_id=data.facility_id,
            department_id=data.department_id,
            requested_by_staff_id=data.requested_by_staff_id,
            needed_by=data.needed_by,
            justification=data.justification
        )
        self.db.add(requisition)
        self.db.flush()  # Get ID

        estimated_total = 0
        for item_data in data.items:
            line_total = (item_data.quantity_requested * (item_data.estimated_unit_price or 0))
            item = PurchaseRequisitionItem(
                requisition_id=requisition.id,
                drug_id=item_data.drug_id,
                inventory_stock_item_id=item_data.inventory_stock_item_id,
                item_name=item_data.item_name,
                item_description=item_data.item_description,
                quantity_requested=item_data.quantity_requested,
                unit_of_measure=item_data.unit_of_measure,
                estimated_unit_price=item_data.estimated_unit_price,
                estimated_line_total=line_total
            )
            estimated_total += line_total
            self.db.add(item)
        
        requisition.estimated_total = estimated_total
        self.db.commit()
        self.db.refresh(requisition)
        return requisition

    def update_requisition(self, requisition: PurchaseRequisition, data: PurchaseRequisitionUpdateSchema) -> PurchaseRequisition:
        if data.facility_id is not None:
            requisition.facility_id = data.facility_id
        if data.department_id is not None:
            requisition.department_id = data.department_id
        if data.needed_by is not None:
            requisition.needed_by = data.needed_by
        if data.justification is not None:
            requisition.justification = data.justification
            
        if data.items is not None:
            # Simple approach: clear and recreate items
            for item in requisition.items:
                self.db.delete(item)
            
            estimated_total = 0
            for item_data in data.items:
                line_total = (item_data.quantity_requested * (item_data.estimated_unit_price or 0))
                item = PurchaseRequisitionItem(
                    requisition_id=requisition.id,
                    drug_id=item_data.drug_id,
                    inventory_stock_item_id=item_data.inventory_stock_item_id,
                    item_name=item_data.item_name,
                    item_description=item_data.item_description,
                    quantity_requested=item_data.quantity_requested,
                    unit_of_measure=item_data.unit_of_measure,
                    estimated_unit_price=item_data.estimated_unit_price,
                    estimated_line_total=line_total
                )
                estimated_total += line_total
                self.db.add(item)
            requisition.estimated_total = estimated_total
            
        self.db.commit()
        self.db.refresh(requisition)
        return requisition

    def delete_requisition(self, requisition: PurchaseRequisition) -> None:
        self.db.delete(requisition)
        self.db.commit()
