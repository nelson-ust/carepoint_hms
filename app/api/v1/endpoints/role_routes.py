from __future__ import annotations

"""
app.api.v1.endpoints.role_routes

FastAPI routes for role and role-permission management.

Purpose
-------
This module exposes API endpoints for:
- listing roles
- reading a role
- creating a role
- updating a role
- deleting a role
- assigning permissions to a role
- removing permissions from a role

Security
--------
These endpoints are restricted to administrators/super administrators.
You can tighten them further later if you decide to separate role-management
permissions from broader admin privileges.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser
from app.utils.pagination import paginate_response
from app.models.all_models import User
from app.schemas.role_schemas import (
    PermissionAssignmentSchema,
    RoleCreateSchema,
    RoleListResponseSchema,
    RolePermissionUpdateResponseSchema,
    RoleReadSchema,
    RoleUpdateSchema,
)
from app.services.role_service import RoleService

router = APIRouter(
    prefix="/roles",
    tags=["Roles"],
)


def get_role_service(
    db: Annotated[Session, Depends(get_db)],
) -> RoleService:
    """
    Dependency provider for the role service.
    """
    return RoleService(db)


# ============================================================
# ROUTES
# ============================================================


@router.get(
    "/",
    response_model=RoleListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List roles",
)
def list_roles(
    _: AdminUser,
    service: Annotated[RoleService, Depends(get_role_service)],
    skip: int = Query(0, ge=0, description="Pagination offset."),
    limit: int = Query(20, ge=1, le=100, description="Pagination size."),
):
    """
    Return a paginated list of roles.

    Access
    ------
    Restricted to administrators and super administrators.
    """
    items, total = service.list_roles(skip=skip, limit=limit)
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Roles fetched successfully.",
    )


@router.get(
    "/{role_id}",
    response_model=RoleReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get role details",
)
def get_role(
    role_id: int,
    _: AdminUser,
    service: Annotated[RoleService, Depends(get_role_service)],
):
    """
    Return the full details of a single role, including its permissions.
    """
    return service.get_role(role_id)


@router.post(
    "/",
    response_model=RoleReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create role",
)
def create_role(
    payload: RoleCreateSchema,
    _: AdminUser,
    service: Annotated[RoleService, Depends(get_role_service)],
):
    """
    Create a new role.

    Optionally accepts permission IDs to attach immediately.
    """
    return service.create_role(payload)


@router.put(
    "/{role_id}",
    response_model=RoleReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update role",
)
def update_role(
    role_id: int,
    payload: RoleUpdateSchema,
    _: AdminUser,
    service: Annotated[RoleService, Depends(get_role_service)],
):
    """
    Update an existing role.
    """
    return service.update_role(role_id, payload)


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete role",
)
def delete_role(
    role_id: int,
    _: AdminUser,
    service: Annotated[RoleService, Depends(get_role_service)],
):
    """
    Soft-delete a role.

    Notes
    -----
    This endpoint prevents deletion when the role is still assigned to users.
    """
    role = service.delete_role(role_id)
    return {
        "success": True,
        "message": "Role deleted successfully.",
        "role_id": role.id,
    }


@router.post(
    "/{role_id}/permissions",
    response_model=RolePermissionUpdateResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Assign permissions to role",
)
def assign_permissions_to_role(
    role_id: int,
    payload: PermissionAssignmentSchema,
    _: AdminUser,
    service: Annotated[RoleService, Depends(get_role_service)],
):
    """
    Attach one or more permissions to a role.
    """
    role = service.assign_permissions(role_id, payload.permission_ids)
    return {
        "success": True,
        "message": "Permissions assigned successfully.",
        "role": role,
    }


@router.delete(
    "/{role_id}/permissions",
    response_model=RolePermissionUpdateResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Remove permissions from role",
)
def remove_permissions_from_role(
    role_id: int,
    payload: PermissionAssignmentSchema,
    _: AdminUser,
    service: Annotated[RoleService, Depends(get_role_service)],
):
    """
    Remove one or more permissions from a role.
    """
    role = service.remove_permissions(role_id, payload.permission_ids)
    return {
        "success": True,
        "message": "Permissions removed successfully.",
        "role": role,
    }