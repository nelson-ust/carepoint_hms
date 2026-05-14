# app/api/v1/endpoints/permission_routes.py
from __future__ import annotations

"""
app.api.v1.endpoints.permission_routes

FastAPI routes for fine-grained permission management.

Endpoints
---------
- list permissions (paginated, filterable by module/search)
- list distinct permission modules
- get a single permission
- create a permission
- update a permission
- soft-delete a permission
- bulk upsert permissions (admin/seed)
- read effective permissions for the authenticated user

Security
--------
All endpoints require an authenticated admin user, except `/me/permissions`
which is available to any authenticated active user.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser, CurrentActiveUser
from app.schemas.permission_schema import (
    PermissionBulkCreateResponseSchema,
    PermissionBulkCreateSchema,
    PermissionCreateSchema,
    PermissionListResponseSchema,
    PermissionReadSchema,
    PermissionUpdateSchema,
)
from app.services.permission_service import PermissionService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/permissions",
    tags=["Permissions"],
)


def get_permission_service(
    db: Annotated[Session, Depends(get_db)],
) -> PermissionService:
    """
    Dependency provider for the permission service.
    """
    return PermissionService(db)


# ============================================================
# ROUTES
# ============================================================

@router.get(
    "/",
    response_model=PermissionListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List permissions",
)
def list_permissions(
    _: AdminUser,
    service: Annotated[PermissionService, Depends(get_permission_service)],
    skip: int = Query(0, ge=0, description="Pagination offset."),
    limit: int = Query(20, ge=1, le=100, description="Pagination size."),
    module: Optional[str] = Query(None, description="Filter by module label."),
    search: Optional[str] = Query(None, description="Substring search across name/code/description."),
):
    """
    Return a paginated list of permissions.
    """
    items, total = service.list_permissions(
        skip=skip,
        limit=limit,
        module=module,
        search=search,
    )
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Permissions fetched successfully.",
    )


@router.get(
    "/modules",
    status_code=status.HTTP_200_OK,
    summary="List permission modules",
)
def list_permission_modules(
    _: AdminUser,
    service: Annotated[PermissionService, Depends(get_permission_service)],
):
    """
    Return distinct module labels currently in use.
    """
    return {
        "success": True,
        "message": "Permission modules fetched successfully.",
        "modules": service.list_modules(),
    }


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="Get effective permissions for the authenticated user",
)
def get_my_permissions(
    current_user: CurrentActiveUser,
    service: Annotated[PermissionService, Depends(get_permission_service)],
):
    """
    Return the set of permission codes the authenticated user has.
    Superusers receive a special wildcard marker.
    """
    if current_user.is_superuser:
        return {
            "success": True,
            "message": "Effective permissions resolved.",
            "is_superuser": True,
            "permissions": ["*"],
        }

    codes = service.get_permission_codes_for_user(current_user.id)
    return {
        "success": True,
        "message": "Effective permissions resolved.",
        "is_superuser": False,
        "permissions": sorted(codes),
    }


@router.get(
    "/{permission_id}",
    response_model=PermissionReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get permission details",
)
def get_permission(
    permission_id: int,
    _: AdminUser,
    service: Annotated[PermissionService, Depends(get_permission_service)],
):
    """
    Return permission details.
    """
    return service.get_permission(permission_id)


@router.post(
    "/",
    response_model=PermissionReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create permission",
)
def create_permission(
    payload: PermissionCreateSchema,
    _: AdminUser,
    service: Annotated[PermissionService, Depends(get_permission_service)],
):
    """
    Create a new permission.
    """
    return service.create_permission(payload)


@router.put(
    "/{permission_id}",
    response_model=PermissionReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update permission",
)
def update_permission(
    permission_id: int,
    payload: PermissionUpdateSchema,
    _: AdminUser,
    service: Annotated[PermissionService, Depends(get_permission_service)],
):
    """
    Update an existing permission. System permissions are immutable except for description.
    """
    return service.update_permission(permission_id, payload)


@router.delete(
    "/{permission_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete permission",
)
def delete_permission(
    permission_id: int,
    _: AdminUser,
    service: Annotated[PermissionService, Depends(get_permission_service)],
):
    """
    Soft-delete a permission. System permissions cannot be deleted.
    """
    permission = service.delete_permission(permission_id)
    return {
        "success": True,
        "message": "Permission deleted successfully.",
        "permission_id": permission.id,
    }


@router.post(
    "/bulk-upsert",
    response_model=PermissionBulkCreateResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Bulk upsert permissions (admin/seed)",
)
def bulk_upsert_permissions(
    payload: PermissionBulkCreateSchema,
    _: AdminUser,
    service: Annotated[PermissionService, Depends(get_permission_service)],
):
    """
    Insert or update permissions in bulk, keyed by code.

    Useful for seed scripts and configuration management.
    """
    result = service.bulk_upsert(payload)
    return {
        "success": True,
        "message": "Permissions processed successfully.",
        "created_count": result["created_count"],
        "updated_count": result["updated_count"],
        "skipped_count": result["skipped_count"],
        "items": result["items"],
    }
