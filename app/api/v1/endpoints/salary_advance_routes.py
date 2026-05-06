from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.salary_advance_service import SalaryAdvanceService
from app.schemas.salary_advance_schemas import (
    SalaryAdvanceCreateSchema,
    SalaryAdvanceUpdateSchema,
    SalaryAdvanceReadSchema,
    SalaryAdvanceSubmitSchema
)
from app.dependencies.auth import get_current_user
from app.models.all_models import User

router = APIRouter(prefix="/salary-advances", tags=["Salary Advance"])

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
