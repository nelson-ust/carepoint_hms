from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from app.core.enums import ProcurementRequisitionStatus

class PurchaseRequisitionItemBase(BaseModel):
    drug_id: Optional[int] = None
    inventory_stock_item_id: Optional[int] = None
    item_name: str
    item_description: Optional[str] = None
    quantity_requested: int = Field(..., gt=0)
    unit_of_measure: Optional[str] = None
    estimated_unit_price: float = Field(..., ge=0)

class PurchaseRequisitionItemCreateSchema(PurchaseRequisitionItemBase):
    pass

class PurchaseRequisitionItemReadSchema(PurchaseRequisitionItemBase):
    id: int
    requisition_id: int
    estimated_line_total: float
    
    model_config = ConfigDict(from_attributes=True)

class PurchaseRequisitionBase(BaseModel):
    facility_id: Optional[int] = None
    department_id: Optional[int] = None
    needed_by: Optional[date] = None
    justification: Optional[str] = None

class PurchaseRequisitionCreateSchema(PurchaseRequisitionBase):
    requested_by_staff_id: int
    items: List[PurchaseRequisitionItemCreateSchema]

class PurchaseRequisitionUpdateSchema(PurchaseRequisitionBase):
    items: Optional[List[PurchaseRequisitionItemCreateSchema]] = None

class PurchaseRequisitionSubmitSchema(BaseModel):
    flow_id: int
    title: str = "Procurement Requisition"
    submit_now: bool = True

class PurchaseRequisitionReadSchema(PurchaseRequisitionBase):
    id: int
    requisition_no: str
    requested_by_staff_id: int
    status: ProcurementRequisitionStatus
    estimated_total: float
    submitted_at: Optional[datetime] = None
    approval_request_id: Optional[int] = None
    items: List[PurchaseRequisitionItemReadSchema] = []
    
    model_config = ConfigDict(from_attributes=True)

# ── RFQ Schemas ───────────────────────────────────────────────────────

class RFQItemCreateSchema(BaseModel):
    requisition_item_id: Optional[int] = None
    quantity: float

class RequestForQuotationCreateSchema(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    bid_deadline: Optional[datetime] = None
    vendor_ids: List[int] = [] # These will be used to create RequestForQuotationVendor
    items: List[RFQItemCreateSchema]

class RequestForQuotationReadSchema(BaseModel):
    id: int
    rfq_no: str
    status: str
    model_config = ConfigDict(from_attributes=True)

# ── Purchase Order Schemas ───────────────────────────────────────────

class POItemCreateSchema(BaseModel):
    item_name: str
    quantity_ordered: float
    unit_price: float
    tax_amount: float = 0
    discount_amount: float = 0
    drug_id: Optional[int] = None
    inventory_stock_item_id: Optional[int] = None

class PurchaseOrderCreateSchema(BaseModel):
    supplier_id: int
    rfq_id: Optional[int] = None
    requisition_id: Optional[int] = None
    expected_delivery_date: Optional[date] = None
    notes: Optional[str] = None
    items: List[POItemCreateSchema]

class PurchaseOrderReadSchema(BaseModel):
    id: int
    po_no: str
    supplier_id: int
    status: str
    total_amount: float
    model_config = ConfigDict(from_attributes=True)
