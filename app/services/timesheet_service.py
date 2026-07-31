from datetime import datetime, timezone
from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import TimesheetStatus, RequestTypeCode
from app.models.all_models import Timesheet, StaffProfile
from app.repositories.timesheet_repository import TimesheetRepository
from app.schemas.timesheet_schemas import TimesheetCreateSchema, TimesheetUpdateSchema, TimesheetSubmitSchema, TimesheetSelfCreateSchema
from app.services.approval_service import ApprovalRequestService
from app.schemas.approval_schemas import ApprovalRequestCreateSchema

class TimesheetService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = TimesheetRepository(db)
        self.approval_service = ApprovalRequestService(db)

    def get_timesheet(self, timesheet_id: int) -> Timesheet:
        timesheet = self.repository.get_by_id(timesheet_id)
        if not timesheet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timesheet not found")
        return timesheet

    def list_timesheets(self, staff_profile_id: int = None, skip: int = 0, limit: int = 100) -> Tuple[List[Timesheet], int]:
        return self.repository.list_timesheets(staff_profile_id, skip, limit)

    def create_timesheet(self, data: TimesheetCreateSchema) -> Timesheet:
        return self.repository.create(data)

    # ── Self-service (individual staff acting for themselves) ──────────

    def _find_my_staff_profile_id(self, user_id: int) -> int | None:
        """The caller's staff-profile id, or None when the account (e.g. a
        pure admin/superuser login) has no staff profile."""
        sp = (
            self.db.query(StaffProfile)
            .filter(StaffProfile.user_id == user_id, StaffProfile.is_deleted.is_(False))
            .first()
        )
        return sp.id if sp is not None else None

    def _resolve_my_staff_profile_id(self, user_id: int) -> int:
        staff_profile_id = self._find_my_staff_profile_id(user_id)
        if staff_profile_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Your account is not linked to a staff profile, so it cannot "
                    "own timesheets. Ask HR to onboard you as staff (Staff "
                    "Management → Onboard Staff) or link a profile to this login."
                ),
            )
        return staff_profile_id

    def create_my_timesheet(self, data: TimesheetSelfCreateSchema, user_id: int) -> Timesheet:
        staff_profile_id = self._resolve_my_staff_profile_id(user_id)
        full = TimesheetCreateSchema(staff_profile_id=staff_profile_id, **data.model_dump())
        return self.repository.create(full)

    def list_my_timesheets(self, user_id: int, skip: int = 0, limit: int = 100):
        staff_profile_id = self._find_my_staff_profile_id(user_id)
        if staff_profile_id is None:
            # Admin/superuser accounts without a staff profile have no
            # timesheets — an empty list, not an error.
            return [], 0
        return self.repository.list_timesheets(staff_profile_id, skip, limit)

    def _assert_owns(self, timesheet_id: int, user_id: int) -> Timesheet:
        staff_profile_id = self._resolve_my_staff_profile_id(user_id)
        ts = self.get_timesheet(timesheet_id)
        if ts.staff_profile_id != staff_profile_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only act on your own timesheets.",
            )
        return ts

    def submit_my_timesheet(self, timesheet_id: int, data: TimesheetSubmitSchema, user_id: int) -> Timesheet:
        self._assert_owns(timesheet_id, user_id)
        return self.submit_timesheet(timesheet_id, data, user_id)

    def delete_my_timesheet(self, timesheet_id: int, user_id: int) -> None:
        self._assert_owns(timesheet_id, user_id)
        self.delete_timesheet(timesheet_id)

    def update_timesheet(self, timesheet_id: int, data: TimesheetUpdateSchema) -> Timesheet:
        timesheet = self.get_timesheet(timesheet_id)
        if timesheet.status != TimesheetStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft timesheets can be modified"
            )
        return self.repository.update(timesheet, data)

    def delete_timesheet(self, timesheet_id: int) -> None:
        timesheet = self.get_timesheet(timesheet_id)
        if timesheet.status != TimesheetStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft timesheets can be deleted"
            )
        self.repository.delete(timesheet)

    def submit_timesheet(self, timesheet_id: int, data: TimesheetSubmitSchema, user_id: int) -> Timesheet:
        timesheet = self.get_timesheet(timesheet_id)
        if timesheet.status != TimesheetStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Only draft timesheets can be submitted"
            )

        # Route through the generic Approval Engine.
        approval_payload = ApprovalRequestCreateSchema(
            flow_id=data.flow_id,
            request_type=RequestTypeCode.TIMESHEET,
            assigned_approver_user_id=data.assigned_approver_user_id,
            subject_id=timesheet.id,
            title=data.title,
        )
        req = self.approval_service.submit(approval_payload, requester_user_id=user_id)
        if req is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No approval flow is configured for TIMESHEET. Configure one under Approvals → Flows & Types.",
            )

        # A zero-step flow auto-approves (row set to APPROVED by the engine);
        # otherwise reflect the submitted/pending state.
        self.db.refresh(timesheet)
        if timesheet.status == TimesheetStatus.DRAFT:
            timesheet.status = TimesheetStatus.SUBMITTED
            timesheet.submitted_at = datetime.now(timezone.utc)
        timesheet.approval_request_id = req.id
        self.db.add(timesheet)
        self.db.commit()
        self.db.refresh(timesheet)
        return timesheet
