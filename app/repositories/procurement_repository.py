from typing import List, Optional, Tuple
import uuid
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.models.all_models import (
    PurchaseRequisition, 
    PurchaseRequisitionItem,
    RequestForQuotation,
    RequestForQuotationItem,
    RequestForQuotationVendor,
    PurchaseOrder,
    PurchaseOrderItem
)
from app.schemas.procurement_schemas import (
    PurchaseRequisitionCreateSchema, 
    PurchaseRequisitionUpdateSchema,
    RequestForQuotationCreateSchema,
    PurchaseOrderCreateSchema
)

class ProcurementRepository:
    def __init__(self, db: Session):
        self.db = db

    # ... existing methods ...

    # ── RFQ Methods ───────────────────────────────────────────────────

    def create_rfq(self, data: RequestForQuotationCreateSchema) -> RequestForQuotation:
        rfq_no = f"RFQ-{uuid.uuid4().hex[:8].upper()}"
        rfq = RequestForQuotation(
            rfq_no=rfq_no,
            status="DRAFT", # Matches RFQStatus.DRAFT
            notes=data.description
        )
        self.db.add(rfq)
        self.db.flush()

        for vendor_id in data.vendor_ids:
            self.db.add(RequestForQuotationVendor(rfq_id=rfq.id, vendor_id=vendor_id))

        for item_data in data.items:
            self.db.add(RequestForQuotationItem(
                rfq_id=rfq.id,
                requisition_item_id=item_data.requisition_item_id,
                quantity=item_data.quantity
            ))
        
        self.db.flush()
        return rfq

    # ── PO Methods ────────────────────────────────────────────────────

    def create_po(self, data: PurchaseOrderCreateSchema) -> PurchaseOrder:
        po_no = f"PO-{uuid.uuid4().hex[:8].upper()}"
        po = PurchaseOrder(
            po_no=po_no,
            supplier_id=data.supplier_id,
            rfq_id=data.rfq_id,
            requisition_id=data.requisition_id,
            expected_delivery_date=data.expected_delivery_date,
            notes=data.notes,
            status="DRAFT" # Matches PurchaseOrderStatus.DRAFT
        )
        self.db.add(po)
        self.db.flush()

        total_amount = 0
        subtotal_amount = 0
        tax_amount = 0
        discount_amount = 0

        for item_data in data.items:
            line_subtotal = (item_data.quantity_ordered * item_data.unit_price)
            line_total = line_subtotal + item_data.tax_amount - item_data.discount_amount
            
            self.db.add(PurchaseOrderItem(
                purchase_order_id=po.id,
                item_name=item_data.item_name,
                quantity_ordered=item_data.quantity_ordered,
                unit_price=item_data.unit_price,
                line_total=line_total,
                drug_id=item_data.drug_id,
                inventory_stock_item_id=item_data.inventory_stock_item_id
            ))
            
            subtotal_amount += line_subtotal
            tax_amount += item_data.tax_amount
            discount_amount += item_data.discount_amount
            total_amount += line_total
        
        po.subtotal_amount = subtotal_amount
        po.tax_amount = tax_amount
        po.discount_amount = discount_amount
        po.total_amount = total_amount
        
        self.db.flush()
        return po

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
