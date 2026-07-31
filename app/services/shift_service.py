from typing import List, Optional, Tuple
from datetime import datetime, timezone, date, time

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ShiftStatus, StaffShiftType
from app.models.all_models import (
    ShiftDefinition,
    StaffShiftAssignment,
    ShiftSwapRequest,
    ServiceDeliveryPoint,
)
from app.repositories.shift_repository import (
    ShiftDefinitionRepository,
    StaffShiftAssignmentRepository,
    ShiftSwapRequestRepository,
)
from app.schemas.shift_schemas import (
    ShiftDefinitionCreateSchema,
    ShiftDefinitionUpdateSchema,
    ShiftQuickSetupSchema,
    StaffShiftAssignmentCreateSchema,
    StaffShiftAssignmentUpdateSchema,
    ShiftSwapRequestCreateSchema,
)


# Standard rotations used by the one-click "quick setup". Times are sensible
# hospital defaults the admin can edit afterwards. shift_type drives the roster
# colour/legend; the name/code are what staff actually see.
_QUICK_SETUP_PRESETS = {
    "TWO": [
        dict(name="Day Shift", code="DAY", shift_type=StaffShiftType.MORNING,
             start_time=time(7, 0), end_time=time(19, 0), color_hex="#f59e0b"),
        dict(name="Night Shift", code="NIGHT", shift_type=StaffShiftType.NIGHT,
             start_time=time(19, 0), end_time=time(7, 0), color_hex="#8b5cf6"),
    ],
    "THREE": [
        dict(name="Morning Shift", code="MORN", shift_type=StaffShiftType.MORNING,
             start_time=time(7, 0), end_time=time(14, 0), color_hex="#10b981"),
        dict(name="Afternoon Shift", code="AFT", shift_type=StaffShiftType.AFTERNOON,
             start_time=time(14, 0), end_time=time(21, 0), color_hex="#06b6d4"),
        dict(name="Night Shift", code="NIGHT", shift_type=StaffShiftType.NIGHT,
             start_time=time(21, 0), end_time=time(7, 0), color_hex="#8b5cf6"),
    ],
}


class ShiftDefinitionService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ShiftDefinitionRepository(db)

    def get(self, definition_id: int) -> ShiftDefinition:
        defn = self.repository.get_by_id(definition_id)
        if not defn:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift definition not found")
        return defn

    def _validate_unit(self, department_id: int, sdp_id: Optional[int]) -> None:
        """A unit (service delivery point) must exist and live in the department."""
        if sdp_id is None:
            return
        sdp = self.db.scalars(
            select(ServiceDeliveryPoint).where(ServiceDeliveryPoint.id == sdp_id)
        ).first()
        if not sdp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected unit (service delivery point) not found",
            )
        if sdp.department_id is not None and sdp.department_id != department_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected unit does not belong to the chosen department",
            )

    def list_definitions(
        self,
        department_id: Optional[int] = None,
        service_delivery_point_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[ShiftDefinition], int]:
        return self.repository.list_definitions(
            department_id, service_delivery_point_id, skip, limit
        )

    def create(self, data: ShiftDefinitionCreateSchema) -> ShiftDefinition:
        self._validate_unit(data.department_id, data.service_delivery_point_id)
        return self.repository.create(data)

    def update(self, definition_id: int, data: ShiftDefinitionUpdateSchema) -> ShiftDefinition:
        defn = self.get(definition_id)
        if "service_delivery_point_id" in data.model_dump(exclude_unset=True):
            self._validate_unit(defn.department_id, data.service_delivery_point_id)
        return self.repository.update(defn, data)

    def delete(self, definition_id: int) -> None:
        defn = self.get(definition_id)
        self.repository.delete(defn)

    def quick_setup(self, data: ShiftQuickSetupSchema) -> List[ShiftDefinition]:
        """Create a standard 2- or 3-shift rotation for a department/unit."""
        self._validate_unit(data.department_id, data.service_delivery_point_id)
        presets = _QUICK_SETUP_PRESETS.get(data.preset)
        if not presets:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unknown preset. Use 'TWO' or 'THREE'.",
            )

        if data.replace_existing:
            existing, _ = self.repository.list_definitions(
                data.department_id, data.service_delivery_point_id, 0, 1000
            )
            for d in existing:
                self.repository.delete(d)

        # Idempotent: skip any preset whose code already exists in this scope.
        existing, _ = self.repository.list_definitions(
            data.department_id, data.service_delivery_point_id, 0, 1000
        )
        existing_codes = {d.code.upper() for d in existing}

        created: List[ShiftDefinition] = []
        for p in presets:
            if p["code"].upper() in existing_codes:
                continue
            payload = ShiftDefinitionCreateSchema(
                department_id=data.department_id,
                service_delivery_point_id=data.service_delivery_point_id,
                break_duration_minutes=0,
                description=None,
                **p,
            )
            created.append(self.repository.create(payload))
        return created


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
        service_delivery_point_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[StaffShiftAssignment], int]:
        return self.repository.list_assignments(
            department_id,
            staff_profile_id,
            service_delivery_point_id,
            date_from,
            date_to,
            skip,
            limit,
        )

    def create(self, data: StaffShiftAssignmentCreateSchema, assigned_by: Optional[int] = None) -> StaffShiftAssignment:
        # Validate the shift definition exists
        defn = self.definition_repo.get_by_id(data.shift_definition_id)
        if not defn:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Shift definition not found"
            )
        # Prevent double-booking a staff member on the same day.
        clash = self.repository.find_conflict(data.staff_profile_id, data.shift_date)
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This staff member is already rostered for a shift on that date.",
            )
        return self.repository.create(data, assigned_by=assigned_by)

    def update(self, assignment_id: int, data: StaffShiftAssignmentUpdateSchema) -> StaffShiftAssignment:
        assignment = self.get(assignment_id)
        # If the date or staff effectively changes, re-check for a clash.
        new_date = data.shift_date or assignment.shift_date
        if new_date != assignment.shift_date:
            clash = self.repository.find_conflict(
                assignment.staff_profile_id, new_date, exclude_id=assignment.id
            )
            if clash is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This staff member is already rostered for a shift on that date.",
                )
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
