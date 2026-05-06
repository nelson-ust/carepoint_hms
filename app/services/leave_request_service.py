from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import LeaveStatus, ApprovalSubjectType
from app.models.all_models import LeaveRequest
from app.repositories.leave_request_repository import LeaveRequestRepository
from app.schemas.leave_request_schemas import (
    LeaveRequestCreateSchema, 
    LeaveRequestUpdateSchema, 
    LeaveRequestSubmitSchema
)
from app.services.approval_service import ApprovalRequestService
from app.schemas.approval_schemas import ApprovalRequestCreateSchema

class LeaveRequestService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = LeaveRequestRepository(db)
        self.approval_service = ApprovalRequestService(db)

    def get_leave_request(self, request_id: int) -> LeaveRequest:
        leave_req = self.repository.get_by_id(request_id)
        if not leave_req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
        return leave_req

    def list_leave_requests(self, staff_profile_id: int = None, skip: int = 0, limit: int = 100) -> Tuple[List[LeaveRequest], int]:
        return self.repository.list_requests(staff_profile_id, skip, limit)

    def create_leave_request(self, data: LeaveRequestCreateSchema) -> LeaveRequest:
        return self.repository.create(data)

    def update_leave_request(self, request_id: int, data: LeaveRequestUpdateSchema) -> LeaveRequest:
        leave_req = self.get_leave_request(request_id)
        if leave_req.status != LeaveStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft leave requests can be modified"
            )
        return self.repository.update(leave_req, data)

    def delete_leave_request(self, request_id: int) -> None:
        leave_req = self.get_leave_request(request_id)
        if leave_req.status != LeaveStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft leave requests can be deleted"
            )
        self.repository.delete(leave_req)

    def submit_leave_request(self, request_id: int, data: LeaveRequestSubmitSchema, user_id: int) -> LeaveRequest:
        leave_req = self.get_leave_request(request_id)
        if leave_req.status != LeaveStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft leave requests can be submitted"
            )

        # Create approval request in the Approval Engine
        approval_payload = ApprovalRequestCreateSchema(
            flow_id=data.flow_id,
            subject_type=ApprovalSubjectType.LEAVE_REQUEST,
            subject_id=leave_req.id,
            title=data.title,
            submit_now=data.submit_now
        )
        
        self.approval_service.submit(approval_payload, requester_user_id=user_id)
        
        # Depending on the workflow, it might immediately transition. Refresh to get latest status.
        self.db.refresh(leave_req)
        return leave_req
