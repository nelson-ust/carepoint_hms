# app/api/v1/endpoints/staff_routes.py
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.dependencies import CurrentActiveUser
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.schemas.staff_profile_schemas import (
    StaffProfileDetailedReadSchema,
    StaffProfileReadSchema,
    StaffProfileUpdateSchema,
    UserCreateSchema,
    UserReadSchema,
    UserUpdateSchema,
    UserListResponseSchema,
)
from app.services.staff_profile_service import StaffProfileService
from app.dependencies.role import require_admin, require_hr_staff

router = APIRouter(prefix="/staff", tags=["Staff Management"])

def get_staff_service(db: Annotated[Session, Depends(get_db)]) -> StaffProfileService:
    return StaffProfileService(db)


@router.post(
    "/",
    response_model=UserReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new staff user and profile",
    dependencies=[Depends(require_hr_staff)],
)
def create_staff(
    payload: UserCreateSchema,
    service: Annotated[StaffProfileService, Depends(get_staff_service)],
):
    """
    Onboard a new staff member. Creates the User account and StaffProfile together.
    Requires HR or Admin access.
    """
    return service.create_user_with_staff_profile(payload)


@router.get(
    "/",
    response_model=UserListResponseSchema,
    summary="List all staff users",
)
def list_staff(
    service: Annotated[StaffProfileService, Depends(get_staff_service)],
    _: CurrentActiveUser,
    skip: int = 0,
    limit: int = 50,
):
    """
    Paginated list of staff users.
    """
    items, count = service.list_users(skip=skip, limit=limit)
    return {
        "success": True,
        "message": "Staff fetched successfully.",
        "items": items,
        "count": count,
        "meta": {"skip": skip, "limit": limit, "total": count},
    }


@router.get(
    "/{user_id}",
    response_model=StaffProfileDetailedReadSchema,
    summary="Get detailed staff profile by user ID",
)
def get_staff(
    user_id: int,
    service: Annotated[StaffProfileService, Depends(get_staff_service)],
    _: CurrentActiveUser,
):
    """
    Retrieve full details for a specific staff member using their user ID.
    """
    return service.get_detailed_staff_profile_by_user_id(user_id)


@router.patch(
    "/{user_id}",
    response_model=UserReadSchema,
    summary="Update staff user and profile",
    dependencies=[Depends(require_hr_staff)],
)
def update_staff(
    user_id: int,
    payload: UserUpdateSchema,
    service: Annotated[StaffProfileService, Depends(get_staff_service)],
):
    """
    Update user fields and/or staff profile fields.
    Requires HR or Admin access.
    """
    return service.update_user_and_staff_profile(user_id, payload)


@router.delete(
    "/{staff_profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete a staff profile",
    dependencies=[Depends(require_admin)],
)
def delete_staff_profile(
    staff_profile_id: int,
    service: Annotated[StaffProfileService, Depends(get_staff_service)],
):
    """
    Soft delete a staff profile.
    Requires Admin access.
    """
    service.soft_delete_staff_profile(staff_profile_id)
