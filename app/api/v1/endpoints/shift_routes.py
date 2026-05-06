from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.all_models import User
from app.services.shift_service import (
    ShiftDefinitionService,
    StaffShiftAssignmentService,
    ShiftSwapRequestService,
)
from app.schemas.shift_schemas import (
    ShiftDefinitionCreateSchema,
    ShiftDefinitionUpdateSchema,
    ShiftDefinitionReadSchema,
    StaffShiftAssignmentCreateSchema,
    StaffShiftAssignmentUpdateSchema,
    StaffShiftAssignmentReadSchema,
    ShiftSwapRequestCreateSchema,
    ShiftSwapRequestReadSchema,
)

router = APIRouter(prefix="/shifts", tags=["Staff Shifts"])


# ── Shift Definitions ────────────────────────────────────────────────

@router.post("/definitions", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_shift_definition(
    payload: ShiftDefinitionCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ShiftDefinitionService(db)
    defn = service.create(payload)
    return {
        "success": True,
        "message": "Shift definition created",
        "definition": ShiftDefinitionReadSchema.model_validate(defn).model_dump(),
    }


@router.get("/definitions", response_model=dict)
def list_shift_definitions(
    department_id: int = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ShiftDefinitionService(db)
    items, total = service.list_definitions(department_id, skip, limit)
    return {
        "success": True,
        "items": [ShiftDefinitionReadSchema.model_validate(i).model_dump() for i in items],
        "count": total,
    }


@router.get("/definitions/{definition_id}", response_model=dict)
def get_shift_definition(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ShiftDefinitionService(db)
    defn = service.get(definition_id)
    return {
        "success": True,
        "definition": ShiftDefinitionReadSchema.model_validate(defn).model_dump(),
    }


@router.patch("/definitions/{definition_id}", response_model=dict)
def update_shift_definition(
    definition_id: int,
    payload: ShiftDefinitionUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ShiftDefinitionService(db)
    defn = service.update(definition_id, payload)
    return {
        "success": True,
        "message": "Shift definition updated",
        "definition": ShiftDefinitionReadSchema.model_validate(defn).model_dump(),
    }


@router.delete("/definitions/{definition_id}", response_model=dict)
def delete_shift_definition(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ShiftDefinitionService(db)
    service.delete(definition_id)
    return {"success": True, "message": "Shift definition deleted"}


# ── Staff Shift Assignments ──────────────────────────────────────────

@router.post("/assignments", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_shift_assignment(
    payload: StaffShiftAssignmentCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = StaffShiftAssignmentService(db)
    assignment = service.create(payload, assigned_by=current_user.id)
    return {
        "success": True,
        "message": "Shift assignment created",
        "assignment": StaffShiftAssignmentReadSchema.model_validate(assignment).model_dump(),
    }


@router.get("/assignments", response_model=dict)
def list_shift_assignments(
    department_id: int = None,
    staff_profile_id: int = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = StaffShiftAssignmentService(db)
    items, total = service.list_assignments(department_id, staff_profile_id, skip, limit)
    return {
        "success": True,
        "items": [StaffShiftAssignmentReadSchema.model_validate(i).model_dump() for i in items],
        "count": total,
    }


@router.get("/assignments/{assignment_id}", response_model=dict)
def get_shift_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = StaffShiftAssignmentService(db)
    assignment = service.get(assignment_id)
    return {
        "success": True,
        "assignment": StaffShiftAssignmentReadSchema.model_validate(assignment).model_dump(),
    }


@router.patch("/assignments/{assignment_id}", response_model=dict)
def update_shift_assignment(
    assignment_id: int,
    payload: StaffShiftAssignmentUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = StaffShiftAssignmentService(db)
    assignment = service.update(assignment_id, payload)
    return {
        "success": True,
        "message": "Shift assignment updated",
        "assignment": StaffShiftAssignmentReadSchema.model_validate(assignment).model_dump(),
    }


@router.post("/assignments/{assignment_id}/check-in", response_model=dict)
def check_in_shift(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = StaffShiftAssignmentService(db)
    assignment = service.check_in(assignment_id)
    return {
        "success": True,
        "message": "Checked in successfully",
        "assignment": StaffShiftAssignmentReadSchema.model_validate(assignment).model_dump(),
    }


@router.post("/assignments/{assignment_id}/check-out", response_model=dict)
def check_out_shift(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = StaffShiftAssignmentService(db)
    assignment = service.check_out(assignment_id)
    return {
        "success": True,
        "message": "Checked out successfully",
        "assignment": StaffShiftAssignmentReadSchema.model_validate(assignment).model_dump(),
    }


@router.delete("/assignments/{assignment_id}", response_model=dict)
def delete_shift_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = StaffShiftAssignmentService(db)
    service.delete(assignment_id)
    return {"success": True, "message": "Shift assignment deleted"}


# ── Shift Swap Requests ──────────────────────────────────────────────

@router.post("/swaps", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_swap_request(
    payload: ShiftSwapRequestCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ShiftSwapRequestService(db)
    swap = service.create(payload)
    return {
        "success": True,
        "message": "Swap request created",
        "swap_request": ShiftSwapRequestReadSchema.model_validate(swap).model_dump(),
    }


@router.post("/swaps/{swap_id}/approve", response_model=dict)
def approve_swap_request(
    swap_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ShiftSwapRequestService(db)
    swap = service.approve(swap_id, decided_by=current_user.id)
    return {
        "success": True,
        "message": "Swap request approved",
        "swap_request": ShiftSwapRequestReadSchema.model_validate(swap).model_dump(),
    }


@router.post("/swaps/{swap_id}/reject", response_model=dict)
def reject_swap_request(
    swap_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ShiftSwapRequestService(db)
    swap = service.reject(swap_id, decided_by=current_user.id)
    return {
        "success": True,
        "message": "Swap request rejected",
        "swap_request": ShiftSwapRequestReadSchema.model_validate(swap).model_dump(),
    }
