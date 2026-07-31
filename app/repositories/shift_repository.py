from typing import List, Optional, Tuple
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.enums import ShiftStatus
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
            select(ShiftDefinition)
            .options(
                joinedload(ShiftDefinition.department),
                joinedload(ShiftDefinition.service_delivery_point),
            )
            .where(ShiftDefinition.id == definition_id)
        ).first()

    def get_by_code(
        self, department_id: int, code: str
    ) -> Optional[ShiftDefinition]:
        return self.db.scalars(
            select(ShiftDefinition).where(
                ShiftDefinition.department_id == department_id,
                ShiftDefinition.code == code.strip().upper(),
            )
        ).first()

    def list_definitions(
        self,
        department_id: Optional[int] = None,
        service_delivery_point_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[ShiftDefinition], int]:
        stmt = select(ShiftDefinition).options(
            joinedload(ShiftDefinition.department),
            joinedload(ShiftDefinition.service_delivery_point),
        )
        if department_id is not None:
            stmt = stmt.where(ShiftDefinition.department_id == department_id)
        if service_delivery_point_id is not None:
            stmt = stmt.where(
                ShiftDefinition.service_delivery_point_id == service_delivery_point_id
            )
        stmt = stmt.order_by(ShiftDefinition.start_time.asc(), ShiftDefinition.id.asc())

        total = len(self.db.scalars(stmt).all())
        items = list(self.db.scalars(stmt.offset(skip).limit(limit)).all())
        return items, total

    def create(self, data: ShiftDefinitionCreateSchema) -> ShiftDefinition:
        defn = ShiftDefinition(
            department_id=data.department_id,
            service_delivery_point_id=data.service_delivery_point_id,
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
        # Only touch fields the caller actually sent. This lets
        # service_delivery_point_id=null explicitly clear the unit scope while
        # an omitted field is left untouched.
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
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

    def find_conflict(
        self,
        staff_profile_id: int,
        shift_date: date,
        exclude_id: Optional[int] = None,
    ) -> Optional[StaffShiftAssignment]:
        """
        A staff member should not hold two live duties on the same calendar day.
        Cancelled assignments are ignored. Returns the clashing row if any.
        """
        stmt = select(StaffShiftAssignment).where(
            StaffShiftAssignment.staff_profile_id == staff_profile_id,
            StaffShiftAssignment.shift_date == shift_date,
            StaffShiftAssignment.status != ShiftStatus.CANCELLED,
        )
        if exclude_id is not None:
            stmt = stmt.where(StaffShiftAssignment.id != exclude_id)
        return self.db.scalars(stmt).first()

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
        stmt = select(StaffShiftAssignment).join(ShiftDefinition)
        if department_id is not None:
            stmt = stmt.where(ShiftDefinition.department_id == department_id)
        if service_delivery_point_id is not None:
            stmt = stmt.where(
                ShiftDefinition.service_delivery_point_id == service_delivery_point_id
            )
        if staff_profile_id is not None:
            stmt = stmt.where(StaffShiftAssignment.staff_profile_id == staff_profile_id)
        if date_from is not None:
            stmt = stmt.where(StaffShiftAssignment.shift_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(StaffShiftAssignment.shift_date <= date_to)
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
