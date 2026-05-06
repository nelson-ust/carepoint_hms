from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.procurement_service import ProcurementService
from app.schemas.procurement_schemas import (
    PurchaseRequisitionCreateSchema,
    PurchaseRequisitionUpdateSchema,
    PurchaseRequisitionReadSchema,
    PurchaseRequisitionSubmitSchema
)
from app.dependencies.auth import get_current_user
from app.models.all_models import User

router = APIRouter(prefix="/procurements", tags=["Procurement"])

@router.post("/requisitions", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_requisition(
    payload: PurchaseRequisitionCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ProcurementService(db)
    requisition = service.create_requisition(payload)
    return {
        "success": True,
        "message": "Procurement requisition created successfully",
        "requisition": PurchaseRequisitionReadSchema.model_validate(requisition).model_dump()
    }

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
    return {
        "success": True,
        "items": [PurchaseRequisitionReadSchema.model_validate(i).model_dump() for i in items],
        "count": total
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
