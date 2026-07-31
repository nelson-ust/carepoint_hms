from datetime import datetime, timezone
from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import SalaryAdvanceStatus, RequestTypeCode
from app.models.all_models import SalaryAdvance, StaffProfile
from app.repositories.salary_advance_repository import SalaryAdvanceRepository
from app.schemas.salary_advance_schemas import (
    SalaryAdvanceCreateSchema, 
    SalaryAdvanceUpdateSchema, 
    SalaryAdvanceSubmitSchema,
    SalaryAdvanceSelfCreateSchema,
)
from app.services.approval_service import ApprovalRequestService
from app.schemas.approval_schemas import ApprovalRequestCreateSchema

class SalaryAdvanceService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = SalaryAdvanceRepository(db)
        self.approval_service = ApprovalRequestService(db)

    def _validate_account(self, account_id) -> None:
        if account_id is None:
            return
        from app.models.all_models import Account
        acct = (
            self.db.query(Account)
            .filter(Account.id == account_id, Account.is_deleted.is_(False))
            .first()
        )
        if acct is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The selected account does not exist.",
            )

    def get_salary_advance(self, request_id: int) -> SalaryAdvance:
        advance = self.repository.get_by_id(request_id)
        if not advance:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary advance request not found")
        return advance

    def list_salary_advances(self, staff_profile_id: int = None, skip: int = 0, limit: int = 100) -> Tuple[List[SalaryAdvance], int]:
        return self.repository.list_requests(staff_profile_id, skip, limit)

    def create_salary_advance(self, data: SalaryAdvanceCreateSchema) -> SalaryAdvance:
        self._validate_account(data.account_id)
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

    def disburse_salary_advance(self, request_id: int, actor_user_id: int | None = None):
        """Mark an APPROVED advance as disbursed (PAID). Only disbursed
        advances are recovered by payroll and posted to the ledger."""
        from datetime import datetime, timezone
        advance = self.get_salary_advance(request_id)
        if advance.status != SalaryAdvanceStatus.APPROVED:
            raise BadRequestError(message=f"Only approved advances can be disbursed (status is {advance.status.value}).")
        advance.status = SalaryAdvanceStatus.PAID
        advance.paid_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(advance)
        return advance

    def submit_salary_advance(self, request_id: int, data: SalaryAdvanceSubmitSchema, user_id: int) -> SalaryAdvance:
        advance = self.get_salary_advance(request_id)
        if advance.status != SalaryAdvanceStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft requests can be submitted"
            )

        approval_payload = ApprovalRequestCreateSchema(
            flow_id=data.flow_id,
            request_type=RequestTypeCode.SALARY_ADVANCE,
            assigned_approver_user_id=data.assigned_approver_user_id,
            subject_id=advance.id,
            title=data.title,
        )
        approval_req = self.approval_service.submit(approval_payload, requester_user_id=user_id)
        if approval_req is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No approval flow is configured for SALARY_ADVANCE. Configure one under Approvals → Flows & Types.",
            )

        self.db.refresh(advance)
        if advance.status == SalaryAdvanceStatus.DRAFT:
            advance.status = SalaryAdvanceStatus.SUBMITTED
            advance.submitted_at = datetime.now(timezone.utc)
        advance.approval_request_id = approval_req.id
        self.db.add(advance)
        self.db.commit()
        self.db.refresh(advance)
        return advance

    # ── Self-service (individual staff acting for themselves) ──────────

    def _resolve_my_staff_profile_id(self, user_id: int) -> int:
        sp = (
            self.db.query(StaffProfile)
            .filter(StaffProfile.user_id == user_id, StaffProfile.is_deleted.is_(False))
            .first()
        )
        if sp is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your account is not linked to a staff profile. Contact HR.",
            )
        return sp.id

    def create_my_salary_advance(self, data: SalaryAdvanceSelfCreateSchema, user_id: int) -> SalaryAdvance:
        self._validate_account(data.account_id)
        staff_profile_id = self._resolve_my_staff_profile_id(user_id)
        full = SalaryAdvanceCreateSchema(staff_profile_id=staff_profile_id, **data.model_dump())
        return self.repository.create(full)

    def list_my_salary_advances(self, user_id: int, skip: int = 0, limit: int = 100):
        staff_profile_id = self._resolve_my_staff_profile_id(user_id)
        return self.repository.list_requests(staff_profile_id, skip, limit)

    def _assert_owns(self, request_id: int, user_id: int) -> SalaryAdvance:
        staff_profile_id = self._resolve_my_staff_profile_id(user_id)
        advance = self.get_salary_advance(request_id)
        if advance.staff_profile_id != staff_profile_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only act on your own salary advances.",
            )
        return advance

    def submit_my_salary_advance(self, request_id: int, data: SalaryAdvanceSubmitSchema, user_id: int) -> SalaryAdvance:
        self._assert_owns(request_id, user_id)
        return self.submit_salary_advance(request_id, data, user_id)

    def delete_my_salary_advance(self, request_id: int, user_id: int) -> None:
        self._assert_owns(request_id, user_id)
        self.delete_salary_advance(request_id)
