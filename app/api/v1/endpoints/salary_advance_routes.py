from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.salary_advance_service import SalaryAdvanceService
from app.schemas.salary_advance_schemas import (
    SalaryAdvanceCreateSchema,
    SalaryAdvanceUpdateSchema,
    SalaryAdvanceSelfCreateSchema,
    SalaryAdvanceReadSchema,
    SalaryAdvanceSubmitSchema
)
from app.core.dependencies import get_current_user, require_permission, require_plan_feature
from app.models.all_models import User

router = APIRouter(
    prefix="/salary-advances", 
    tags=["Salary Advance"],
    dependencies=[Depends(require_plan_feature("hr"))]
)

@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_salary_advance(
    payload: SalaryAdvanceCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = SalaryAdvanceService(db)
    advance = service.create_salary_advance(payload)
    return {
        "success": True,
        "message": "Salary advance request created successfully",
        "salary_advance": SalaryAdvanceReadSchema.model_validate(advance).model_dump()
    }

@router.get("", response_model=dict)
def list_salary_advances(
    staff_profile_id: int = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = SalaryAdvanceService(db)
    items, total = service.list_salary_advances(staff_profile_id, skip, limit)
    return {
        "success": True,
        "items": [SalaryAdvanceReadSchema.model_validate(i).model_dump() for i in items],
        "count": total
    }

@router.get("/me", response_model=dict, summary="List my own salary advances")
def list_my_salary_advances(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = SalaryAdvanceService(db)
    items, total = service.list_my_salary_advances(current_user.id, skip, limit)
    return {
        "success": True,
        "items": [SalaryAdvanceReadSchema.model_validate(i).model_dump() for i in items],
        "count": total
    }

@router.post("/me", response_model=dict, status_code=status.HTTP_201_CREATED, summary="Create my own salary advance")
def create_my_salary_advance(
    payload: SalaryAdvanceSelfCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = SalaryAdvanceService(db)
    advance = service.create_my_salary_advance(payload, user_id=current_user.id)
    return {
        "success": True,
        "message": "Salary advance request created successfully",
        "salary_advance": SalaryAdvanceReadSchema.model_validate(advance).model_dump()
    }

@router.post("/me/{request_id}/submit", response_model=dict, summary="Submit my own salary advance for approval")
def submit_my_salary_advance(
    request_id: int,
    payload: SalaryAdvanceSubmitSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = SalaryAdvanceService(db)
    advance = service.submit_my_salary_advance(request_id, payload, user_id=current_user.id)
    return {
        "success": True,
        "message": "Salary advance request submitted for approval",
        "salary_advance": SalaryAdvanceReadSchema.model_validate(advance).model_dump()
    }

@router.delete("/me/{request_id}", response_model=dict, summary="Delete my own draft salary advance")
def delete_my_salary_advance(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = SalaryAdvanceService(db)
    service.delete_my_salary_advance(request_id, user_id=current_user.id)
    return {
        "success": True,
        "message": "Salary advance request deleted successfully"
    }

@router.get("/{request_id}", response_model=dict)
def get_salary_advance(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = SalaryAdvanceService(db)
    advance = service.get_salary_advance(request_id)
    return {
        "success": True,
        "salary_advance": SalaryAdvanceReadSchema.model_validate(advance).model_dump()
    }

@router.patch("/{request_id}", response_model=dict)
def update_salary_advance(
    request_id: int,
    payload: SalaryAdvanceUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = SalaryAdvanceService(db)
    advance = service.update_salary_advance(request_id, payload)
    return {
        "success": True,
        "message": "Salary advance request updated successfully",
        "salary_advance": SalaryAdvanceReadSchema.model_validate(advance).model_dump()
    }

@router.delete("/{request_id}", response_model=dict)
def delete_salary_advance(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = SalaryAdvanceService(db)
    service.delete_salary_advance(request_id)
    return {
        "success": True,
        "message": "Salary advance request deleted successfully"
    }

@router.post("/{request_id}/disburse", response_model=dict,
             summary="Mark an approved advance as disbursed (paid out)")
def disburse_salary_advance(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("USER_MANAGE_STATUS", "PAYMENT_RECEIVE", "ACCOUNTING_POST")),
):
    """Cash office / HR confirms the money left the till. Payroll only ever
    recovers DISBURSED advances, and the ledger books the cash movement here."""
    service = SalaryAdvanceService(db)
    advance = service.disburse_salary_advance(request_id, getattr(current_user, "id", None))
    return {
        "success": True,
        "message": "Advance marked as disbursed. It will be recovered in the next payroll run on or after its repayment month.",
        "salary_advance": SalaryAdvanceReadSchema.model_validate(advance).model_dump(),
    }


@router.post("/{request_id}/submit", response_model=dict)
def submit_salary_advance(
    request_id: int,
    payload: SalaryAdvanceSubmitSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = SalaryAdvanceService(db)
    advance = service.submit_salary_advance(request_id, payload, current_user.id)
    return {
        "success": True,
        "message": "Salary advance request submitted for approval",
        "salary_advance": SalaryAdvanceReadSchema.model_validate(advance).model_dump()
    }
