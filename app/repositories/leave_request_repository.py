from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import LeaveRequest
from app.schemas.leave_request_schemas import LeaveRequestCreateSchema, LeaveRequestUpdateSchema

class LeaveRequestRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, request_id: int) -> Optional[LeaveRequest]:
        return self.db.scalars(select(LeaveRequest).where(LeaveRequest.id == request_id)).first()

    def list_requests(
        self, staff_profile_id: Optional[int] = None, skip: int = 0, limit: int = 100
    ) -> Tuple[List[LeaveRequest], int]:
        stmt = select(LeaveRequest)
        if staff_profile_id:
            stmt = stmt.where(LeaveRequest.staff_profile_id == staff_profile_id)
        
        stmt = stmt.order_by(LeaveRequest.id.desc())
        
        total = len(self.db.scalars(stmt).all())
        items = list(self.db.scalars(stmt.offset(skip).limit(limit)).all())
        return items, total

    def create(self, data: LeaveRequestCreateSchema) -> LeaveRequest:
        leave_req = LeaveRequest(
            staff_profile_id=data.staff_profile_id,
            leave_type_id=data.leave_type_id,
            start_date=data.start_date,
            end_date=data.end_date,
            days_requested=data.days_requested,
            reason=data.reason,
            handover_notes=data.handover_notes,
            cover_staff_id=data.cover_staff_id
        )
        self.db.add(leave_req)
        self.db.commit()
        self.db.refresh(leave_req)
        return leave_req

    def update(self, leave_req: LeaveRequest, data: LeaveRequestUpdateSchema) -> LeaveRequest:
        if data.start_date is not None:
            leave_req.start_date = data.start_date
        if data.end_date is not None:
            leave_req.end_date = data.end_date
        if data.days_requested is not None:
            leave_req.days_requested = data.days_requested
        if data.reason is not None:
            leave_req.reason = data.reason
        if data.handover_notes is not None:
            leave_req.handover_notes = data.handover_notes
        if data.cover_staff_id is not None:
            leave_req.cover_staff_id = data.cover_staff_id
            
        self.db.commit()
        self.db.refresh(leave_req)
        return leave_req

    def delete(self, leave_req: LeaveRequest) -> None:
        self.db.delete(leave_req)
        self.db.commit()
