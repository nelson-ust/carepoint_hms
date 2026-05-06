from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import ProcurementRequisitionStatus, ApprovalSubjectType
from app.models.all_models import PurchaseRequisition
from app.repositories.procurement_repository import ProcurementRepository
from app.schemas.procurement_schemas import (
    PurchaseRequisitionCreateSchema, 
    PurchaseRequisitionUpdateSchema, 
    PurchaseRequisitionSubmitSchema
)
from app.services.approval_service import ApprovalRequestService
from app.schemas.approval_schemas import ApprovalRequestCreateSchema

class ProcurementService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProcurementRepository(db)
        self.approval_service = ApprovalRequestService(db)

    def get_requisition(self, requisition_id: int) -> PurchaseRequisition:
        requisition = self.repository.get_requisition_by_id(requisition_id)
        if not requisition:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Procurement requisition not found")
        return requisition

    def list_requisitions(self, department_id: int = None, skip: int = 0, limit: int = 100) -> Tuple[List[PurchaseRequisition], int]:
        return self.repository.list_requisitions(department_id, skip, limit)

    def create_requisition(self, data: PurchaseRequisitionCreateSchema) -> PurchaseRequisition:
        return self.repository.create_requisition(data)

    def update_requisition(self, requisition_id: int, data: PurchaseRequisitionUpdateSchema) -> PurchaseRequisition:
        requisition = self.get_requisition(requisition_id)
        if requisition.status != ProcurementRequisitionStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft requisitions can be modified"
            )
        return self.repository.update_requisition(requisition, data)

    def delete_requisition(self, requisition_id: int) -> None:
        requisition = self.get_requisition(requisition_id)
        if requisition.status != ProcurementRequisitionStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft requisitions can be deleted"
            )
        self.repository.delete_requisition(requisition)

    def submit_requisition(self, requisition_id: int, data: PurchaseRequisitionSubmitSchema, user_id: int) -> PurchaseRequisition:
        requisition = self.get_requisition(requisition_id)
        if requisition.status != ProcurementRequisitionStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft requisitions can be submitted"
            )

        approval_payload = ApprovalRequestCreateSchema(
            flow_id=data.flow_id,
            subject_type=ApprovalSubjectType.PROCUREMENT,
            subject_id=requisition.id,
            title=data.title,
            submit_now=data.submit_now
        )
        
        self.approval_service.submit(approval_payload, requester_user_id=user_id)
        self.db.refresh(requisition)
        return requisition
