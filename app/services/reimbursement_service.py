from datetime import datetime, timezone
from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import ReimbursementStatus, RequestTypeCode
from app.models.all_models import ReimbursementRequest, StaffProfile
from app.repositories.reimbursement_repository import ReimbursementRepository
from app.schemas.reimbursement_schemas import (
    ReimbursementCreateSchema, 
    ReimbursementUpdateSchema, 
    ReimbursementSubmitSchema,
    ReimbursementSelfCreateSchema,
)
from app.services.approval_service import ApprovalRequestService
from app.schemas.approval_schemas import ApprovalRequestCreateSchema

class ReimbursementService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ReimbursementRepository(db)
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

    def get_reimbursement(self, request_id: int) -> ReimbursementRequest:
        req = self.repository.get_by_id(request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reimbursement request not found")
        return req

    def list_reimbursements(self, staff_profile_id: int = None, skip: int = 0, limit: int = 100) -> Tuple[List[ReimbursementRequest], int]:
        return self.repository.list_requests(staff_profile_id, skip, limit)

    def create_reimbursement(self, data: ReimbursementCreateSchema) -> ReimbursementRequest:
        self._validate_account(data.account_id)
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

        # Route through the generic Approval Engine.
        approval_payload = ApprovalRequestCreateSchema(
            flow_id=data.flow_id,
            request_type=RequestTypeCode.REIMBURSEMENT,
            assigned_approver_user_id=data.assigned_approver_user_id,
            subject_id=req.id,
            title=data.title,
        )
        approval_req = self.approval_service.submit(approval_payload, requester_user_id=user_id)
        if approval_req is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No approval flow is configured for REIMBURSEMENT. Configure one under Approvals → Flows & Types.",
            )

        # The engine may have finalized immediately (zero-step flow auto-approves);
        # otherwise reflect the pending state.
        self.db.refresh(req)
        if req.status == ReimbursementStatus.DRAFT:
            req.status = ReimbursementStatus.PENDING
            req.submitted_at = datetime.now(timezone.utc)
        req.approval_request_id = approval_req.id
        self.db.add(req)
        self.db.commit()
        self.db.refresh(req)
        return req

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

    def create_my_reimbursement(self, data: ReimbursementSelfCreateSchema, user_id: int) -> ReimbursementRequest:
        self._validate_account(data.account_id)
        staff_profile_id = self._resolve_my_staff_profile_id(user_id)
        full = ReimbursementCreateSchema(staff_profile_id=staff_profile_id, **data.model_dump())
        return self.repository.create(full)

    def list_my_reimbursements(self, user_id: int, skip: int = 0, limit: int = 100):
        staff_profile_id = self._resolve_my_staff_profile_id(user_id)
        return self.repository.list_requests(staff_profile_id, skip, limit)

    def _assert_owns(self, request_id: int, user_id: int) -> ReimbursementRequest:
        staff_profile_id = self._resolve_my_staff_profile_id(user_id)
        req = self.get_reimbursement(request_id)
        if req.staff_profile_id != staff_profile_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only act on your own expense claims.",
            )
        return req

    def submit_my_reimbursement(self, request_id: int, data: ReimbursementSubmitSchema, user_id: int) -> ReimbursementRequest:
        self._assert_owns(request_id, user_id)
        return self.submit_reimbursement(request_id, data, user_id)

    def delete_my_reimbursement(self, request_id: int, user_id: int) -> None:
        self._assert_owns(request_id, user_id)
        self.delete_reimbursement(request_id)
