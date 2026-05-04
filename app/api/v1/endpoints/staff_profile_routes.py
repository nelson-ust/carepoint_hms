from __future__ import annotations

"""
app.api.v1.endpoints.staff_profile_routes

FastAPI routes for staff onboarding, user administration, role assignment,
session review, and detailed staff profile retrieval.

Purpose
-------
This module exposes endpoints for:

- creating a user account with a required nested staff profile
- updating user and staff profile data
- listing users
- activating and deactivating accounts
- assigning, replacing, and removing roles
- resetting and changing passwords
- enabling and disabling MFA
- reviewing and revoking sessions
- reviewing a user's effective access summary
- retrieving detailed staff profile records
- listing and soft-deleting staff profiles

Security
--------
Administrative endpoints are restricted to administrators/super administrators.
Self-service password change and "revoke my other sessions" are available to
authenticated active users.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser, CurrentActiveUser
from app.models.all_models import StaffProfile, User
from app.schemas.staff_profile_schemas import (
    ActionResponseSchema,
    MFAToggleSchema,
    PasswordChangeSchema,
    PasswordResetSchema,
    RoleAssignmentSchema,
    StaffProfileDetailedReadSchema,
    StaffProfileReadSchema,
    UserAccessSummarySchema,
    UserCreateSchema,
    UserListResponseSchema,
    UserReadSchema,
    UserSessionReadSchema,
    UserUpdateSchema,
)
from app.services.staff_profile_service import StaffProfileService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/staff-profiles",
    tags=["Staff Profile Administration"],
)


def get_staff_profile_service(
    db: Annotated[Session, Depends(get_db)],
) -> StaffProfileService:
    """
    Dependency provider for the staff profile service.

    Args:
        db: Request-scoped SQLAlchemy session.

    Returns:
        StaffProfileService: Service instance.
    """
    return StaffProfileService(db)


# ============================================================
# SERIALIZATION HELPERS
# ============================================================

def _serialize_user(user: User) -> dict[str, Any]:
    """
    Serialize a User ORM object into the shape expected by UserReadSchema.

    This serializer also includes:
    - assigned roles
    - linked staff profile (when present)

    Args:
        user: ORM user instance.

    Returns:
        dict[str, Any]: Serialized user payload.
    """
    roles: list[dict[str, Any]] = []
    for link in user.user_roles or []:
        if link.role and not link.role.is_deleted:
            roles.append(
                {
                    "id": link.role.id,
                    "name": link.role.name,
                    "code": link.role.code,
                    "description": link.role.description,
                }
            )

    staff_profile_payload = None
    if user.staff_profile and not user.staff_profile.is_deleted:
        staff_profile_payload = {
            "id": user.staff_profile.id,
            "user_id": user.staff_profile.user_id,
            "department_id": user.staff_profile.department_id,
            "service_delivery_point_id": user.staff_profile.service_delivery_point_id,
            "staff_no": user.staff_profile.staff_no,
            "job_title": user.staff_profile.job_title,
            "professional_license_no": user.staff_profile.professional_license_no,
            "specialty": user.staff_profile.specialty,
            "created_at": user.staff_profile.created_at,
            "updated_at": user.staff_profile.updated_at,
        }

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
        "is_two_factor_enabled": user.is_two_factor_enabled,
        "is_email_verified": user.is_email_verified,
        "is_phone_verified": user.is_phone_verified,
        "last_login_at": user.last_login_at,
        "password_changed_at": user.password_changed_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "roles": roles,
        "staff_profile": staff_profile_payload,
    }


def _serialize_staff_profile(staff_profile: StaffProfile) -> dict[str, Any]:
    """
    Serialize a basic StaffProfile ORM object into StaffProfileReadSchema shape.

    Args:
        staff_profile: ORM staff profile instance.

    Returns:
        dict[str, Any]: Serialized basic staff profile payload.
    """
    return {
        "id": staff_profile.id,
        "user_id": staff_profile.user_id,
        "department_id": staff_profile.department_id,
        "service_delivery_point_id": staff_profile.service_delivery_point_id,
        "staff_no": staff_profile.staff_no,
        "job_title": staff_profile.job_title,
        "professional_license_no": staff_profile.professional_license_no,
        "specialty": staff_profile.specialty,
        "created_at": staff_profile.created_at,
        "updated_at": staff_profile.updated_at,
    }


def _serialize_detailed_staff_profile(staff_profile: StaffProfile) -> dict[str, Any]:
    """
    Serialize a detailed StaffProfile ORM object.

    Includes:
    - linked user account
    - assigned department
    - assigned service delivery point
    - assigned roles from the linked user

    Args:
        staff_profile: ORM staff profile instance with eager-loaded relations.

    Returns:
        dict[str, Any]: Serialized detailed staff profile payload.
    """
    roles: list[dict[str, Any]] = []
    if staff_profile.user:
        for link in staff_profile.user.user_roles or []:
            if link.role and not link.role.is_deleted:
                roles.append(
                    {
                        "id": link.role.id,
                        "name": link.role.name,
                        "code": link.role.code,
                        "description": link.role.description,
                    }
                )

    department_payload = None
    if staff_profile.department and not staff_profile.department.is_deleted:
        department_payload = {
            "id": staff_profile.department.id,
            "name": staff_profile.department.name,
            "code": staff_profile.department.code,
            "description": staff_profile.department.description,
        }

    service_point_payload = None
    if (
        staff_profile.service_delivery_point
        and not staff_profile.service_delivery_point.is_deleted
    ):
        service_point_payload = {
            "id": staff_profile.service_delivery_point.id,
            "name": staff_profile.service_delivery_point.name,
            "code": staff_profile.service_delivery_point.code,
            "service_point_type": str(staff_profile.service_delivery_point.service_point_type),
            "location_description": staff_profile.service_delivery_point.location_description,
            "queue_prefix": staff_profile.service_delivery_point.queue_prefix,
            "supports_appointments": staff_profile.service_delivery_point.supports_appointments,
            "supports_walk_in": staff_profile.service_delivery_point.supports_walk_in,
        }

    user_payload = None
    if staff_profile.user and not staff_profile.user.is_deleted:
        user_payload = {
            "id": staff_profile.user.id,
            "username": staff_profile.user.username,
            "email": staff_profile.user.email,
            "phone_number": staff_profile.user.phone_number,
            "first_name": staff_profile.user.first_name,
            "last_name": staff_profile.user.last_name,
            "middle_name": staff_profile.user.middle_name,
            "status": str(staff_profile.user.status),
            "is_superuser": staff_profile.user.is_superuser,
            "is_two_factor_enabled": staff_profile.user.is_two_factor_enabled,
            "is_email_verified": staff_profile.user.is_email_verified,
            "is_phone_verified": staff_profile.user.is_phone_verified,
            "last_login_at": staff_profile.user.last_login_at,
            "password_changed_at": staff_profile.user.password_changed_at,
            "created_at": staff_profile.user.created_at,
            "updated_at": staff_profile.user.updated_at,
        }

    return {
        "id": staff_profile.id,
        "user_id": staff_profile.user_id,
        "department_id": staff_profile.department_id,
        "service_delivery_point_id": staff_profile.service_delivery_point_id,
        "staff_no": staff_profile.staff_no,
        "job_title": staff_profile.job_title,
        "professional_license_no": staff_profile.professional_license_no,
        "specialty": staff_profile.specialty,
        "created_at": staff_profile.created_at,
        "updated_at": staff_profile.updated_at,
        "user": user_payload,
        "department": department_payload,
        "service_delivery_point": service_point_payload,
        "roles": roles,
    }


# ============================================================
# USER ADMINISTRATION ROUTES
# ============================================================

@router.get(
    "/users",
    response_model=UserListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List users",
)
def list_users(
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
    skip: int = Query(0, ge=0, description="Pagination offset."),
    limit: int = Query(20, ge=1, le=100, description="Pagination size."),
):
    """
    Return a paginated list of users with lightweight staff profile context.
    """
    items, total = service.list_users(skip=skip, limit=limit)
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Users fetched successfully.",
    )


@router.get(
    "/users/{user_id}",
    response_model=UserReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get user details",
)
def get_user(
    user_id: int,
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Return full details for a single user, including roles and linked staff profile.
    """
    user = service.get_user(user_id)
    return _serialize_user(user)


@router.post(
    "/users",
    response_model=UserReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create user with staff profile",
)
def create_user_with_staff_profile(
    payload: UserCreateSchema,
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Create a new user account together with a required nested staff profile.

    The business payload includes staff profile data as part of onboarding.
    """
    user = service.create_user_with_staff_profile(payload)
    return _serialize_user(user)


@router.put(
    "/users/{user_id}",
    response_model=UserReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update user and optional staff profile",
)
def update_user_and_staff_profile(
    user_id: int,
    payload: UserUpdateSchema,
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Update a user account and optionally update the linked staff profile.
    """
    user = service.update_user_and_staff_profile(user_id, payload)
    return _serialize_user(user)


@router.post(
    "/users/{user_id}/activate",
    response_model=UserReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Activate user",
)
def activate_user(
    user_id: int,
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Activate a user account.
    """
    user = service.activate_user(user_id)
    return _serialize_user(user)


@router.post(
    "/users/{user_id}/deactivate",
    response_model=UserReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Deactivate user",
)
def deactivate_user(
    user_id: int,
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Deactivate a user account and revoke active sessions.
    """
    user = service.deactivate_user(user_id)
    return _serialize_user(user)


# ============================================================
# ROLE ASSIGNMENT ROUTES
# ============================================================

@router.post(
    "/users/{user_id}/roles/assign",
    response_model=UserReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Assign roles to user",
)
def assign_roles(
    user_id: int,
    payload: RoleAssignmentSchema,
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Add one or more roles to a user.
    """
    user = service.assign_roles(user_id, payload)
    return _serialize_user(user)


@router.put(
    "/users/{user_id}/roles",
    response_model=UserReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Replace user roles",
)
def replace_roles(
    user_id: int,
    payload: RoleAssignmentSchema,
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Replace all current role assignments for a user.
    """
    user = service.replace_roles(user_id, payload)
    return _serialize_user(user)


@router.delete(
    "/users/{user_id}/roles",
    response_model=UserReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Remove roles from user",
)
def remove_roles(
    user_id: int,
    payload: RoleAssignmentSchema,
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Remove selected roles from a user.
    """
    user = service.remove_roles(user_id, payload)
    return _serialize_user(user)


# ============================================================
# PASSWORD / MFA ROUTES
# ============================================================

@router.post(
    "/users/{user_id}/password/reset",
    response_model=UserReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Admin reset password",
)
def admin_reset_password(
    user_id: int,
    payload: PasswordResetSchema,
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Reset a user's password as an administrator.

    This also revokes active sessions for the user.
    """
    user = service.admin_reset_password(user_id, payload)
    return _serialize_user(user)


@router.post(
    "/users/me/password/change",
    response_model=UserReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Change own password",
)
def change_own_password(
    payload: PasswordChangeSchema,
    current_user: CurrentActiveUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Change the current authenticated user's password.
    """
    user = service.change_own_password(current_user.id, payload)
    return _serialize_user(user)


@router.post(
    "/users/{user_id}/mfa",
    response_model=UserReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Enable or disable MFA",
)
def toggle_mfa(
    user_id: int,
    payload: MFAToggleSchema,
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Enable or disable MFA for a user account.
    """
    user = service.toggle_mfa(user_id, payload)
    return _serialize_user(user)


# ============================================================
# SESSION ROUTES
# ============================================================

@router.get(
    "/users/{user_id}/sessions",
    response_model=list[UserSessionReadSchema],
    status_code=status.HTTP_200_OK,
    summary="List user sessions / login history",
)
def list_user_sessions(
    user_id: int,
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
    skip: int = Query(0, ge=0, description="Pagination offset."),
    limit: int = Query(20, ge=1, le=100, description="Pagination size."),
):
    """
    Review a user's login history and session records.
    """
    items, _ = service.list_user_sessions(user_id, skip=skip, limit=limit)
    return items


@router.post(
    "/users/{user_id}/sessions/revoke",
    response_model=ActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Revoke selected user sessions",
)
def revoke_user_sessions(
    user_id: int,
    payload: dict,
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Revoke selected sessions for a user.

    Expected payload:
    -----------------
    {
      "session_ids": [1, 2, 3]
    }
    """
    session_ids = payload.get("session_ids", [])
    count = service.revoke_user_sessions(user_id, session_ids)
    return {
        "success": True,
        "message": f"{count} session(s) revoked successfully.",
    }


@router.post(
    "/users/me/sessions/revoke-others",
    response_model=ActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Revoke all other sessions for current user",
)
def revoke_my_other_sessions(
    current_user: CurrentActiveUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Revoke all active sessions for the current user except the current request session.

    Note
    ----
    This route currently revokes all active sessions because the current
    session JTI is not being passed into the service layer here.
    """
    count = service.revoke_all_other_sessions(
        current_user.id,
        keep_session_jti=None,
    )
    return {
        "success": True,
        "message": f"{count} session(s) revoked successfully.",
    }


# ============================================================
# ACCESS SUMMARY ROUTE
# ============================================================

@router.get(
    "/users/{user_id}/access-summary",
    response_model=UserAccessSummarySchema,
    status_code=status.HTTP_200_OK,
    summary="Get user access summary",
)
def get_user_access_summary(
    user_id: int,
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Return a user's assigned roles and effective permissions.
    """
    user, permissions = service.get_user_access_summary(user_id)
    return {
        "user": _serialize_user(user),
        "permissions": [
            {
                "id": permission.id,
                "name": permission.name,
                "code": permission.code,
                "module": permission.module,
                "description": permission.description,
            }
            for permission in permissions
        ],
    }


# ============================================================
# STAFF PROFILE ROUTES
# ============================================================

@router.get(
    "/",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="List detailed staff profiles",
)
def list_staff_profiles(
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
    skip: int = Query(0, ge=0, description="Pagination offset."),
    limit: int = Query(20, ge=1, le=100, description="Pagination size."),
):
    """
    Return a paginated list of detailed staff profile records.
    """
    items, total = service.list_staff_profiles(skip=skip, limit=limit)

    serialized_items = [_serialize_detailed_staff_profile(item) for item in items]

    return paginate_response(
        items=serialized_items,
        total=total,
        skip=skip,
        limit=limit,
        message="Staff profiles fetched successfully.",
    )


@router.get(
    "/{staff_profile_id}",
    response_model=StaffProfileDetailedReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get detailed staff profile by profile ID",
)
def get_detailed_staff_profile_by_id(
    staff_profile_id: int,
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Return a detailed staff profile record by staff profile ID.
    """
    staff_profile = service.get_detailed_staff_profile_by_id(staff_profile_id)
    return _serialize_detailed_staff_profile(staff_profile)


@router.get(
    "/by-user/{user_id}",
    response_model=StaffProfileDetailedReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get detailed staff profile by user ID",
)
def get_detailed_staff_profile_by_user_id(
    user_id: int,
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Return a detailed staff profile record using the linked user ID.
    """
    staff_profile = service.get_detailed_staff_profile_by_user_id(user_id)
    return _serialize_detailed_staff_profile(staff_profile)


@router.delete(
    "/{staff_profile_id}",
    response_model=StaffProfileReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Soft delete staff profile",
)
def soft_delete_staff_profile(
    staff_profile_id: int,
    _: AdminUser,
    service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Soft-delete a staff profile record.
    """
    staff_profile = service.soft_delete_staff_profile(staff_profile_id)
    return _serialize_staff_profile(staff_profile)