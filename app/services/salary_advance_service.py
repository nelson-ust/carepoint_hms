from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import SalaryAdvanceStatus, ApprovalSubjectType
from app.models.all_models import SalaryAdvance
from app.repositories.salary_advance_repository import SalaryAdvanceRepository
from app.schemas.salary_advance_schemas import (
    SalaryAdvanceCreateSchema, 
    SalaryAdvanceUpdateSchema, 
    SalaryAdvanceSubmitSchema
)
from app.services.approval_service import ApprovalRequestService
from app.schemas.approval_schemas import ApprovalRequestCreateSchema

class SalaryAdvanceService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = SalaryAdvanceRepository(db)
        self.approval_service = ApprovalRequestService(db)

    def get_salary_advance(self, request_id: int) -> SalaryAdvance:
        advance = self.repository.get_by_id(request_id)
        if not advance:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary advance request not found")
        return advance

    def list_salary_advances(self, staff_profile_id: int = None, skip: int = 0, limit: int = 100) -> Tuple[List[SalaryAdvance], int]:
        return self.repository.list_requests(staff_profile_id, skip, limit)

    def create_salary_advance(self, data: SalaryAdvanceCreateSchema) -> SalaryAdvance:
        return self.repository.create(data)

    def update_salary_advance(self, request_id: int, data: SalaryAdvanceUpdateSchema) -> SalaryAdvance:
        advance = self.get_salary_advance(request_id)
        if advance.status != SalaryAdvanceStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft requests can be modified"
            )
        return self.repository.update(advance, data)

    def delete_salary_advance(self, request_id: int) -> None:
        advance = self.get_salary_advance(request_id)
        if advance.status != SalaryAdvanceStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft requests can be deleted"
            )
        self.repository.delete(advance)

    def submit_salary_advance(self, request_id: int, data: SalaryAdvanceSubmitSchema, user_id: int) -> SalaryAdvance:
        advance = self.get_salary_advance(request_id)
        if advance.status != SalaryAdvanceStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft requests can be submitted"
            )

        approval_payload = ApprovalRequestCreateSchema(
            flow_id=data.flow_id,
            subject_type=ApprovalSubjectType.SALARY_ADVANCE,
            subject_id=advance.id,
            title=data.title,
            submit_now=data.submit_now
        )
        
        self.approval_service.submit(approval_payload, requester_user_id=user_id)
        self.db.refresh(advance)
        return advance
