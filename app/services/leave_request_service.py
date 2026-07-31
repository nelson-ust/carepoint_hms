from datetime import datetime, timezone, date, timedelta
from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import LeaveStatus, RequestTypeCode
from app.models.all_models import LeaveRequest, StaffProfile, LeaveType
from app.repositories.leave_request_repository import LeaveRequestRepository
from app.schemas.leave_request_schemas import (
    LeaveRequestCreateSchema, 
    LeaveRequestUpdateSchema, 
    LeaveRequestSubmitSchema,
    LeaveRequestSelfCreateSchema,
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

    def create_my_leave_request(self, data: LeaveRequestSelfCreateSchema, user_id: int) -> LeaveRequest:
        staff_profile_id = self._resolve_my_staff_profile_id(user_id)
        full = LeaveRequestCreateSchema(staff_profile_id=staff_profile_id, **data.model_dump())
        return self.repository.create(full)

    def list_my_leave_requests(self, user_id: int, skip: int = 0, limit: int = 100):
        staff_profile_id = self._resolve_my_staff_profile_id(user_id)
        return self.repository.list_requests(staff_profile_id, skip, limit)

    def list_my_leave_days(self, user_id: int, start: date, end: date) -> List[dict]:
        """Expand the caller's APPROVED leave into individual dates that fall
        within [start, end]. Used by the timesheet form to auto-populate
        (non-editable) leave days. Earliest matching leave wins on overlap."""
        if end < start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end date must be on or after start date.",
            )
        staff_profile_id = self._resolve_my_staff_profile_id(user_id)
        reqs = (
            self.db.query(LeaveRequest)
            .filter(
                LeaveRequest.staff_profile_id == staff_profile_id,
                LeaveRequest.status == LeaveStatus.APPROVED,
                LeaveRequest.start_date <= end,
                LeaveRequest.end_date >= start,
            )
            .order_by(LeaveRequest.start_date.asc(), LeaveRequest.id.asc())
            .all()
        )
        # leave-type id → name lookup
        type_ids = {r.leave_type_id for r in reqs}
        names: dict[int, str] = {}
        if type_ids:
            for lt in self.db.query(LeaveType).filter(LeaveType.id.in_(type_ids)).all():
                names[lt.id] = lt.name

        by_date: dict[date, dict] = {}
        for r in reqs:
            d = max(r.start_date, start)
            last = min(r.end_date, end)
            while d <= last:
                if d not in by_date:
                    by_date[d] = {
                        "date": d,
                        "leave_type_id": r.leave_type_id,
                        "leave_type_name": names.get(r.leave_type_id) or f"Leave #{r.leave_type_id}",
                        "leave_request_id": r.id,
                        "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                    }
                d = d + timedelta(days=1)
        return [by_date[k] for k in sorted(by_date.keys())]

    def _assert_owns(self, request_id: int, user_id: int) -> LeaveRequest:
        staff_profile_id = self._resolve_my_staff_profile_id(user_id)
        leave_req = self.get_leave_request(request_id)
        if leave_req.staff_profile_id != staff_profile_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only act on your own leave requests.",
            )
        return leave_req

    def submit_my_leave_request(self, request_id: int, data: LeaveRequestSubmitSchema, user_id: int) -> LeaveRequest:
        self._assert_owns(request_id, user_id)
        return self.submit_leave_request(request_id, data, user_id)

    def delete_my_leave_request(self, request_id: int, user_id: int) -> None:
        self._assert_owns(request_id, user_id)
        self.delete_leave_request(request_id)

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

        # Route through the generic Approval Engine.
        approval_payload = ApprovalRequestCreateSchema(
            flow_id=data.flow_id,
            request_type=RequestTypeCode.LEAVE_REQUEST,
            assigned_approver_user_id=data.assigned_approver_user_id,
            subject_id=leave_req.id,
            title=data.title,
        )
        req = self.approval_service.submit(approval_payload, requester_user_id=user_id)
        if req is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No approval flow is configured for LEAVE_REQUEST. Configure one under Approvals → Flows & Types.",
            )

        # The engine may have finalized immediately (a zero-step flow auto-approves,
        # setting the row to APPROVED); otherwise reflect the pending state.
        self.db.refresh(leave_req)
        if leave_req.status == LeaveStatus.DRAFT:
            leave_req.status = LeaveStatus.PENDING
            leave_req.submitted_at = datetime.now(timezone.utc)
        leave_req.approval_request_id = req.id
        self.db.add(leave_req)
        self.db.commit()
        self.db.refresh(leave_req)
        return leave_req
