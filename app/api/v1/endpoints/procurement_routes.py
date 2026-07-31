from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.procurement_service import ProcurementService
from app.schemas.procurement_schemas import (
    PurchaseRequisitionCreateSchema,
    PurchaseRequisitionUpdateSchema,
    PurchaseRequisitionReadSchema,
    PurchaseRequisitionSubmitSchema,
    RequestForQuotationCreateSchema,
    RequestForQuotationReadSchema,
    PurchaseOrderCreateSchema,
    PurchaseOrderReadSchema
)
from app.core.dependencies import get_current_user, require_plan_feature
from app.models.all_models import User

router = APIRouter(
    prefix="/procurements", 
    tags=["Procurement"],
    dependencies=[Depends(require_plan_feature("inventory"))]
)


def _requisition_dict(req, dept_map: dict, staff_map: dict) -> dict:
    """Serialize a requisition and attach human-readable department/requester."""
    data = PurchaseRequisitionReadSchema.model_validate(req).model_dump()
    data["department_name"] = dept_map.get(req.department_id)
    data["requested_by_name"] = staff_map.get(req.requested_by_staff_id)
    return data

# ... existing requisition routes ...

# ── RFQ Routes ────────────────────────────────────────────────────────

@router.post("/rfqs", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_rfq(
    payload: RequestForQuotationCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ProcurementService(db)
    rfq = service.create_rfq(payload)
    return {
        "success": True,
        "message": "Request for Quotation created successfully",
        "rfq": RequestForQuotationReadSchema.model_validate(rfq).model_dump()
    }

# ── PO Routes ─────────────────────────────────────────────────────────

@router.post("/purchase-orders", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_po(
    payload: PurchaseOrderCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ProcurementService(db)
    po = service.create_po(payload)
    return {
        "success": True,
        "message": "Purchase Order created successfully",
        "po": PurchaseOrderReadSchema.model_validate(po).model_dump()
    }

@router.post("/requisitions", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_requisition(
    payload: PurchaseRequisitionCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ProcurementService(db)
    requisition = service.create_requisition(payload, requested_by_user_id=current_user.id)
    return {
        "success": True,
        "message": "Procurement requisition created successfully",
        "requisition": PurchaseRequisitionReadSchema.model_validate(requisition).model_dump()
    }

@router.get("/stats", response_model=dict)
def procurement_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ProcurementService(db)
    return {"success": True, **service.get_stats()}


@router.get("/requisitions", response_model=dict)
def list_requisitions(
    department_id: int = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ProcurementService(db)
    items, total = service.list_requisitions(department_id, skip, limit)
    dept_map = service.department_name_map()
    staff_map = service.staff_name_map()
    return {
        "success": True,
        "items": [_requisition_dict(i, dept_map, staff_map) for i in items],
        "count": total,
        "meta": {"total": total, "skip": skip, "limit": limit},
    }

@router.get("/requisitions/{requisition_id}", response_model=dict)
def get_requisition(
    requisition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ProcurementService(db)
    requisition = service.get_requisition(requisition_id)
    return {
        "success": True,
        "requisition": PurchaseRequisitionReadSchema.model_validate(requisition).model_dump()
    }

@router.patch("/requisitions/{requisition_id}", response_model=dict)
def update_requisition(
    requisition_id: int,
    payload: PurchaseRequisitionUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ProcurementService(db)
    requisition = service.update_requisition(requisition_id, payload)
    return {
        "success": True,
        "message": "Procurement requisition updated successfully",
        "requisition": PurchaseRequisitionReadSchema.model_validate(requisition).model_dump()
    }

@router.delete("/requisitions/{requisition_id}", response_model=dict)
def delete_requisition(
    requisition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ProcurementService(db)
    service.delete_requisition(requisition_id)
    return {
        "success": True,
        "message": "Procurement requisition deleted successfully"
    }

@router.post("/requisitions/{requisition_id}/submit", response_model=dict)
def submit_requisition(
    requisition_id: int,
    payload: PurchaseRequisitionSubmitSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ProcurementService(db)
    requisition = service.submit_requisition(requisition_id, payload, current_user.id)
    return {
        "success": True,
        "message": "Procurement requisition submitted for approval",
        "requisition": PurchaseRequisitionReadSchema.model_validate(requisition).model_dump()
    }
