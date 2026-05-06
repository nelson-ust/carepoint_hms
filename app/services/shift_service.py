from typing import List, Optional, Tuple
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import ShiftStatus
from app.models.all_models import ShiftDefinition, StaffShiftAssignment, ShiftSwapRequest
from app.repositories.shift_repository import (
    ShiftDefinitionRepository,
    StaffShiftAssignmentRepository,
    ShiftSwapRequestRepository,
)
from app.schemas.shift_schemas import (
    ShiftDefinitionCreateSchema,
    ShiftDefinitionUpdateSchema,
    StaffShiftAssignmentCreateSchema,
    StaffShiftAssignmentUpdateSchema,
    ShiftSwapRequestCreateSchema,
)


class ShiftDefinitionService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ShiftDefinitionRepository(db)

    def get(self, definition_id: int) -> ShiftDefinition:
        defn = self.repository.get_by_id(definition_id)
        if not defn:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift definition not found")
        return defn

    def list_definitions(
        self, department_id: Optional[int] = None, skip: int = 0, limit: int = 100
    ) -> Tuple[List[ShiftDefinition], int]:
        return self.repository.list_definitions(department_id, skip, limit)

    def create(self, data: ShiftDefinitionCreateSchema) -> ShiftDefinition:
        return self.repository.create(data)

    def update(self, definition_id: int, data: ShiftDefinitionUpdateSchema) -> ShiftDefinition:
        defn = self.get(definition_id)
        return self.repository.update(defn, data)

    def delete(self, definition_id: int) -> None:
        defn = self.get(definition_id)
        self.repository.delete(defn)


class StaffShiftAssignmentService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = StaffShiftAssignmentRepository(db)
        self.definition_repo = ShiftDefinitionRepository(db)

    def get(self, assignment_id: int) -> StaffShiftAssignment:
        assignment = self.repository.get_by_id(assignment_id)
        if not assignment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift assignment not found")
        return assignment

    def list_assignments(
        self,
        department_id: Optional[int] = None,
        staff_profile_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[StaffShiftAssignment], int]:
        return self.repository.list_assignments(department_id, staff_profile_id, skip, limit)

    def create(self, data: StaffShiftAssignmentCreateSchema, assigned_by: Optional[int] = None) -> StaffShiftAssignment:
        # Validate the shift definition exists
        defn = self.definition_repo.get_by_id(data.shift_definition_id)
        if not defn:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Shift definition not found"
            )
        return self.repository.create(data, assigned_by=assigned_by)

    def update(self, assignment_id: int, data: StaffShiftAssignmentUpdateSchema) -> StaffShiftAssignment:
        assignment = self.get(assignment_id)
        return self.repository.update(assignment, data)

    def check_in(self, assignment_id: int) -> StaffShiftAssignment:
        assignment = self.get(assignment_id)
        if assignment.status != ShiftStatus.SCHEDULED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only check in to a scheduled shift"
            )
        assignment.status = ShiftStatus.ON_DUTY
        assignment.check_in_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def check_out(self, assignment_id: int) -> StaffShiftAssignment:
        assignment = self.get(assignment_id)
        if assignment.status != ShiftStatus.ON_DUTY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only check out from an on-duty shift"
            )
        assignment.status = ShiftStatus.COMPLETED
        assignment.check_out_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def delete(self, assignment_id: int) -> None:
        assignment = self.get(assignment_id)
        if assignment.status not in (ShiftStatus.SCHEDULED, ShiftStatus.CANCELLED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete an active or completed shift assignment"
            )
        self.repository.delete(assignment)


class ShiftSwapRequestService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ShiftSwapRequestRepository(db)
        self.assignment_repo = StaffShiftAssignmentRepository(db)

    def get(self, swap_id: int) -> ShiftSwapRequest:
        swap = self.repository.get_by_id(swap_id)
        if not swap:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Swap request not found")
        return swap

    def create(self, data: ShiftSwapRequestCreateSchema) -> ShiftSwapRequest:
        # Validate the requester assignment exists
        assignment = self.assignment_repo.get_by_id(data.requester_assignment_id)
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Requester shift assignment not found"
            )
        return self.repository.create(data)

    def approve(self, swap_id: int, decided_by: int) -> ShiftSwapRequest:
        swap = self.get(swap_id)
        if swap.status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Swap request is not in pending status"
            )
        swap.status = "APPROVED"
        swap.decided_by_user_id = decided_by
        swap.decided_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(swap)
        return swap

    def reject(self, swap_id: int, decided_by: int) -> ShiftSwapRequest:
        swap = self.get(swap_id)
        if swap.status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Swap request is not in pending status"
            )
        swap.status = "REJECTED"
        swap.decided_by_user_id = decided_by
        swap.decided_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(swap)
        return swap
