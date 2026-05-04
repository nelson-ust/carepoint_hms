from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentActiveUser
from app.core.database import get_db
from app.dependencies.role import require_admin
from app.schemas.department_schema import (
    DepartmentCreateSchema,
    DepartmentListResponseSchema,
    DepartmentReadSchema,
    DepartmentUpdateSchema,
)
from app.services.department_service import DepartmentService

router = APIRouter(prefix="/departments", tags=["Department Management"])

def get_department_service(db: Annotated[Session, Depends(get_db)]) -> DepartmentService:
    return DepartmentService(db)

@router.post(
    "/",
    response_model=DepartmentReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new department",
    dependencies=[Depends(require_admin)],
)
def create_department(
    payload: DepartmentCreateSchema,
    service: Annotated[DepartmentService, Depends(get_department_service)],
):
    """
    Create a new hospital department. Requires Admin role.
    """
    return service.create(payload)

@router.get(
    "/",
    response_model=DepartmentListResponseSchema,
    summary="List all departments",
)
def list_departments(
    service: Annotated[DepartmentService, Depends(get_department_service)],
    _: CurrentActiveUser,
    skip: int = 0,
    limit: int = 50,
):
    """
    Paginated list of departments.
    """
    items, count = service.list(skip=skip, limit=limit)
    return {
        "success": True,
        "items": items,
        "count": count
    }

@router.get(
    "/{department_id}",
    response_model=DepartmentReadSchema,
    summary="Get department details",
)
def get_department(
    department_id: int,
    service: Annotated[DepartmentService, Depends(get_department_service)],
    _: CurrentActiveUser,
):
    """
    Retrieve specific department details.
    """
    return service.get(department_id)

@router.patch(
    "/{department_id}",
    response_model=DepartmentReadSchema,
    summary="Update department details",
    dependencies=[Depends(require_admin)],
)
def update_department(
    department_id: int,
    payload: DepartmentUpdateSchema,
    service: Annotated[DepartmentService, Depends(get_department_service)],
):
    """
    Update department fields. Requires Admin role.
    """
    return service.update(department_id, payload)

@router.delete(
    "/{department_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete a department",
    dependencies=[Depends(require_admin)],
)
def delete_department(
    department_id: int,
    service: Annotated[DepartmentService, Depends(get_department_service)],
):
    """
    Soft delete a department. Requires Admin role.
    """
    service.delete(department_id)
