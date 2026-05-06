from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import TimesheetStatus, ApprovalSubjectType
from app.models.all_models import Timesheet
from app.repositories.timesheet_repository import TimesheetRepository
from app.schemas.timesheet_schemas import TimesheetCreateSchema, TimesheetUpdateSchema, TimesheetSubmitSchema
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

        # Create approval request
        approval_payload = ApprovalRequestCreateSchema(
            flow_id=data.flow_id,
            subject_type=ApprovalSubjectType.TIMESHEET,
            subject_id=timesheet.id,
            title=data.title,
            submit_now=data.submit_now
        )
        
        self.approval_service.submit(approval_payload, requester_user_id=user_id)
        
        # Timesheet status is technically managed by the Approval engine now.
        # But we can set it to PENDING here or rely on the engine's finalize subject.
        # Wait, the engine will call _finalize_subject on the next action.
        # So we update the timesheet status to reflect it's in progress/pending.
        # Actually, in some flows submitting the request might automatically approve it if no steps,
        # but the request_service handles that. We should just refresh the timesheet.
        self.db.refresh(timesheet)
        return timesheet
