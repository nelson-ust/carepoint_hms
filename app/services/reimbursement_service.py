from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import ReimbursementStatus, ApprovalSubjectType
from app.models.all_models import ReimbursementRequest
from app.repositories.reimbursement_repository import ReimbursementRepository
from app.schemas.reimbursement_schemas import (
    ReimbursementCreateSchema, 
    ReimbursementUpdateSchema, 
    ReimbursementSubmitSchema
)
from app.services.approval_service import ApprovalRequestService
from app.schemas.approval_schemas import ApprovalRequestCreateSchema

class ReimbursementService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ReimbursementRepository(db)
        self.approval_service = ApprovalRequestService(db)

    def get_reimbursement(self, request_id: int) -> ReimbursementRequest:
        req = self.repository.get_by_id(request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reimbursement request not found")
        return req

    def list_reimbursements(self, staff_profile_id: int = None, skip: int = 0, limit: int = 100) -> Tuple[List[ReimbursementRequest], int]:
        return self.repository.list_requests(staff_profile_id, skip, limit)

    def create_reimbursement(self, data: ReimbursementCreateSchema) -> ReimbursementRequest:
        return self.repository.create(data)

    def update_reimbursement(self, request_id: int, data: ReimbursementUpdateSchema) -> ReimbursementRequest:
        req = self.get_reimbursement(request_id)
        if req.status != ReimbursementStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft reimbursement requests can be modified"
            )
        return self.repository.update(req, data)

    def delete_reimbursement(self, request_id: int) -> None:
        req = self.get_reimbursement(request_id)
        if req.status != ReimbursementStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft reimbursement requests can be deleted"
            )
        self.repository.delete(req)

    def submit_reimbursement(self, request_id: int, data: ReimbursementSubmitSchema, user_id: int) -> ReimbursementRequest:
        req = self.get_reimbursement(request_id)
        if req.status != ReimbursementStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft reimbursement requests can be submitted"
            )

        # Create approval request in the Approval Engine
        approval_payload = ApprovalRequestCreateSchema(
            flow_id=data.flow_id,
            subject_type=ApprovalSubjectType.REIMBURSEMENT,
            subject_id=req.id,
            title=data.title,
            submit_now=data.submit_now
        )
        
        self.approval_service.submit(approval_payload, requester_user_id=user_id)
        
        self.db.refresh(req)
        return req
