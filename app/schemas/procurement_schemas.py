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
