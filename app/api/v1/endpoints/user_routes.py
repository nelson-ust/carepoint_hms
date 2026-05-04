# app/api/v1/endpoints/user_routes.py
from __future__ import annotations

"""
app.api.v1.endpoints.user_routes

FastAPI routes for administrative user management.

Endpoints
---------
- list users (paginated, filterable)
- get user details
- create user
- update user profile
- update user status (activate / suspend / lock)
- unlock user (clear failed login attempts)
- assign roles
- revoke roles
- force password reset
- list user sessions
- revoke all user sessions
- soft-delete user

Security
--------
All endpoints require an authenticated admin user.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser
from app.models.all_models import User as UserModel
from app.schemas.user_schema import (
    UserActionResponseSchema,
    UserCreateSchema,
    UserDeleteResponseSchema,
    UserListResponseSchema,
    UserPasswordResetSchema,
    UserReadSchema,
    UserRoleAssignmentSchema,
    UserSessionListResponseSchema,
    UserStatusUpdateSchema,
    UserUpdateSchema,
    UserInviteSchema,
)
from app.services.user_service import UserService
from app.utils.pagination import paginate_response

router = APIRouter(prefix="/users", tags=["Admin - User Management"])


def get_user_service(db: Annotated[Session, Depends(get_db)]) -> UserService:
    return UserService(db)


def _serialize_user(user: UserModel) -> dict:
    """
    Lite serialization for user responses.
    """
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "phone_number": user.phone_number,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "middle_name": user.middle_name,
        "status": str(user.status),
        "is_superuser": user.is_superuser,
        "is_email_verified": user.is_email_verified,
        "is_phone_verified": user.is_phone_verified,
        "is_two_factor_enabled": user.is_two_factor_enabled,
        "roles": [
            {
                "id": assoc.role.id,
                "name": assoc.role.name,
                "code": assoc.role.code,
            }
            for assoc in user.user_roles or []
            if not assoc.is_deleted
        ],
    }


@router.get(
    "",
    response_model=UserListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List users",
)
def list_users(
    actor: AdminUser,
    service: Annotated[UserService, Depends(get_user_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, min_length=1, max_length=100),
    status: Optional[str] = Query(None, description="ACTIVE, INACTIVE, LOCKED, SUSPENDED, INVITED."),
    role_code: Optional[str] = Query(None),
    is_superuser: Optional[bool] = Query(None),
):
    """
    List all non-deleted users with optional filtering.
    """
    users, total = service.list_users(
        skip=skip,
        limit=limit,
        search=search,
        status=status,
        role_code=role_code,
        is_superuser=is_superuser,
    )
    return paginate_response(
        items=[_serialize_user(u) for u in users],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "",
    response_model=UserActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
)
def create_user(
    payload: UserCreateSchema,
    actor: AdminUser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """
    Create a new user. Optionally accepts role IDs to assign on creation.
    """
    user = service.create_user(payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "User created successfully.",
        "user": _serialize_user(user),
    }


@router.post(
    "/invite",
    response_model=UserActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Invite user",
)
def invite_user(
    payload: UserInviteSchema,
    actor: AdminUser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """
    Invite a new user. Sets status to INVITED and generates a temporary password.
    """
    user = service.invite_user(payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "User invited successfully. A temporary password has been generated.",
        "user": _serialize_user(user),
    }


@router.get(
    "/{user_id}",
    response_model=UserReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get user details",
)
def get_user(
    user_id: int,
    actor: AdminUser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """
    Retrieve full details for a specific user.
    """
    return service.get_user(user_id)


@router.put(
    "/{user_id}",
    response_model=UserActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Update user profile",
)
def update_user(
    user_id: int,
    payload: UserUpdateSchema,
    actor: AdminUser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """
    Update profile fields (email, phone, name) for a user.
    """
    user = service.update_user(user_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "User profile updated successfully.",
        "user": _serialize_user(user),
    }


@router.put(
    "/{user_id}/status",
    response_model=UserActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Update user status",
)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdateSchema,
    actor: AdminUser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """
    Change a user's status (e.g. deactivate or reactivate).
    """
    user = service.update_user_status(user_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": f"User status updated to {payload.status}.",
        "user": _serialize_user(user),
    }


@router.post(
    "/{user_id}/unlock",
    response_model=UserActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Unlock user account",
)
def unlock_user(
    user_id: int,
    actor: AdminUser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """
    Clear failed login attempts and lockout for a user.
    """
    user = service.unlock_user(user_id, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "User account unlocked successfully.",
        "user": _serialize_user(user),
    }


@router.post(
    "/{user_id}/lock",
    response_model=UserActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Lock user account",
)
def lock_user(
    user_id: int,
    actor: AdminUser,
    service: Annotated[UserService, Depends(get_user_service)],
    reason: Optional[str] = Query(None, description="Optional reason for locking the account."),
):
    """
    Administratively lock a user account and revoke all of its sessions.
    """
    user = service.lock_user(user_id, reason=reason, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "User account locked.",
        "user": _serialize_user(user),
    }


@router.post(
    "/{user_id}/deactivate",
    response_model=UserActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Deactivate (suspend) user",
)
def deactivate_user(
    user_id: int,
    actor: AdminUser,
    service: Annotated[UserService, Depends(get_user_service)],
    reason: Optional[str] = Query(None, description="Optional reason for deactivation."),
):
    """
    Suspend a user account so they cannot log in until reactivated.
    """
    user = service.deactivate_user(user_id, reason=reason, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "User account deactivated.",
        "user": _serialize_user(user),
    }


@router.post(
    "/{user_id}/reactivate",
    response_model=UserActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Reactivate user",
)
def reactivate_user(
    user_id: int,
    actor: AdminUser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """Re-enable a previously suspended/locked user."""
    user = service.reactivate_user(user_id, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "User account reactivated.",
        "user": _serialize_user(user),
    }


@router.post(
    "/{user_id}/roles",
    response_model=UserActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Assign roles",
)
def assign_roles(
    user_id: int,
    payload: UserRoleAssignmentSchema,
    actor: AdminUser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """
    Assign multiple roles to a user.
    """
    user = service.assign_roles(user_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Roles assigned successfully.",
        "user": _serialize_user(user),
    }


@router.delete(
    "/{user_id}/roles",
    response_model=UserActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Revoke roles",
)
def revoke_roles(
    user_id: int,
    payload: UserRoleAssignmentSchema,
    actor: AdminUser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """
    Revoke multiple roles from a user.
    """
    user = service.revoke_roles(user_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Roles revoked successfully.",
        "user": _serialize_user(user),
    }


@router.post(
    "/{user_id}/password-reset",
    response_model=UserActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Force password reset",
)
def force_password_reset(
    user_id: int,
    payload: UserPasswordResetSchema,
    actor: AdminUser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """
    Force a password change for a user. Optionally revokes active sessions.
    """
    user = service.force_password_reset(user_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Password reset successfully.",
        "user": _serialize_user(user),
    }


@router.get(
    "/{user_id}/sessions",
    response_model=UserSessionListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List user sessions",
)
def list_user_sessions(
    user_id: int,
    actor: AdminUser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """
    List all active / non-deleted sessions for a user.
    """
    sessions = service.list_user_sessions(user_id)
    return {
        "success": True,
        "message": "User sessions fetched successfully.",
        "sessions": sessions,
    }


@router.post(
    "/{user_id}/revoke-sessions",
    response_model=UserActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Revoke all user sessions",
)
def revoke_all_sessions(
    user_id: int,
    actor: AdminUser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """
    Invalidate all active sessions for a user.
    """
    user, count = service.revoke_all_sessions(user_id, actor_user_id=actor.id)
    return {
        "success": True,
        "message": f"Successfully revoked {count} sessions.",
        "user": _serialize_user(user),
    }


@router.delete(
    "/{user_id}",
    response_model=UserDeleteResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Soft-delete user",
)
def delete_user(
    user_id: int,
    actor: AdminUser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """
    Soft-delete a user and revoke their sessions.
    """
    service.delete_user(user_id, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "User deactivated successfully.",
        "user_id": user_id,
    }
