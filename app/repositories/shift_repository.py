from typing import List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.all_models import ShiftDefinition, StaffShiftAssignment, ShiftSwapRequest
from app.schemas.shift_schemas import (
    ShiftDefinitionCreateSchema,
    ShiftDefinitionUpdateSchema,
    StaffShiftAssignmentCreateSchema,
    StaffShiftAssignmentUpdateSchema,
    ShiftSwapRequestCreateSchema,
)


class ShiftDefinitionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, definition_id: int) -> Optional[ShiftDefinition]:
        return self.db.scalars(
            select(ShiftDefinition).where(ShiftDefinition.id == definition_id)
        ).first()

    def list_definitions(
        self,
        department_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[ShiftDefinition], int]:
        stmt = select(ShiftDefinition)
        if department_id is not None:
            stmt = stmt.where(ShiftDefinition.department_id == department_id)
        stmt = stmt.order_by(ShiftDefinition.id.desc())

        total = len(self.db.scalars(stmt).all())
        items = list(self.db.scalars(stmt.offset(skip).limit(limit)).all())
        return items, total

    def create(self, data: ShiftDefinitionCreateSchema) -> ShiftDefinition:
        defn = ShiftDefinition(
            department_id=data.department_id,
            name=data.name,
            code=data.code.strip().upper(),
            shift_type=data.shift_type,
            start_time=data.start_time,
            end_time=data.end_time,
            break_duration_minutes=data.break_duration_minutes,
            color_hex=data.color_hex,
            description=data.description,
        )
        self.db.add(defn)
        self.db.commit()
        self.db.refresh(defn)
        return defn

    def update(self, defn: ShiftDefinition, data: ShiftDefinitionUpdateSchema) -> ShiftDefinition:
        for field in ("name", "shift_type", "start_time", "end_time", "break_duration_minutes", "color_hex", "description"):
            value = getattr(data, field, None)
            if value is not None:
                setattr(defn, field, value)

        self.db.commit()
        self.db.refresh(defn)
        return defn

    def delete(self, defn: ShiftDefinition) -> None:
        self.db.delete(defn)
        self.db.commit()


class StaffShiftAssignmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, assignment_id: int) -> Optional[StaffShiftAssignment]:
        return self.db.scalars(
            select(StaffShiftAssignment).where(StaffShiftAssignment.id == assignment_id)
        ).first()

    def list_assignments(
        self,
        department_id: Optional[int] = None,
        staff_profile_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[StaffShiftAssignment], int]:
        stmt = select(StaffShiftAssignment).join(ShiftDefinition)
        if department_id is not None:
            stmt = stmt.where(ShiftDefinition.department_id == department_id)
        if staff_profile_id is not None:
            stmt = stmt.where(StaffShiftAssignment.staff_profile_id == staff_profile_id)
        stmt = stmt.order_by(StaffShiftAssignment.shift_date.desc())

        total = len(self.db.scalars(stmt).all())
        items = list(self.db.scalars(stmt.offset(skip).limit(limit)).all())
        return items, total

    def create(self, data: StaffShiftAssignmentCreateSchema, assigned_by: Optional[int] = None) -> StaffShiftAssignment:
        assignment = StaffShiftAssignment(
            staff_profile_id=data.staff_profile_id,
            shift_definition_id=data.shift_definition_id,
            shift_date=data.shift_date,
            notes=data.notes,
            assigned_by_user_id=assigned_by,
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def update(self, assignment: StaffShiftAssignment, data: StaffShiftAssignmentUpdateSchema) -> StaffShiftAssignment:
        for field in ("shift_definition_id", "shift_date", "status", "notes"):
            value = getattr(data, field, None)
            if value is not None:
                setattr(assignment, field, value)

        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def delete(self, assignment: StaffShiftAssignment) -> None:
        self.db.delete(assignment)
        self.db.commit()


class ShiftSwapRequestRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, swap_id: int) -> Optional[ShiftSwapRequest]:
        return self.db.scalars(
            select(ShiftSwapRequest).where(ShiftSwapRequest.id == swap_id)
        ).first()

    def create(self, data: ShiftSwapRequestCreateSchema) -> ShiftSwapRequest:
        swap = ShiftSwapRequest(
            requester_assignment_id=data.requester_assignment_id,
            target_staff_id=data.target_staff_id,
            target_assignment_id=data.target_assignment_id,
            reason=data.reason,
        )
        self.db.add(swap)
        self.db.commit()
        self.db.refresh(swap)
        return swap
