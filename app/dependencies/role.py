# carepoint_hms/app/dependencies/role.py
from __future__ import annotations

"""
Role-based access dependencies for Carepoint HMS.

This module contains reusable role-checking dependencies that can be attached
to routes to enforce RBAC policies based on the current user's assigned roles
or fine-grained permissions.
"""

from typing import Annotated, Iterable

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ForbiddenError
from app.models.all_models import User
from app.dependencies.auth import get_current_active_user


def _extract_role_names(user: User) -> set[str]:
    """
    Extract normalized role names from the current user.

    The current model links users to roles through UserRoleAssociation and Role.
    """
    role_names: set[str] = set()

    # Defensive iteration in case the relationship is empty or partially loaded.
    for user_role in user.user_roles or []:
        if user_role.role and user_role.role.name:
            role_names.add(user_role.role.name.strip().upper())
        elif user_role.role and user_role.role.code:
            role_names.add(user_role.role.code.strip().upper())

    return role_names


def require_roles(*allowed_roles: str):
    """
    Build a dependency that requires the current user to have at least one
    of the supplied roles.

    Example:
        current_user: Annotated[
            User,
            Depends(require_roles("TENANT_ADMIN", "REGISTRAR"))
        ]
    """
    normalized_allowed = {role.strip().upper() for role in allowed_roles if role.strip()}

    def dependency(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        user_roles = _extract_role_names(current_user)

        if current_user.is_superuser:
            return current_user

        if not user_roles.intersection(normalized_allowed):
            raise ForbiddenError(
                message="You do not have the required role for this action.",
                detail={
                    "allowed_roles": sorted(normalized_allowed),
                    "user_roles": sorted(user_roles),
                },
            )

        return current_user

    return dependency


def require_all_roles(*required_roles: str):
    """
    Build a dependency that requires the current user to have all supplied roles.
    """
    normalized_required = {role.strip().upper() for role in required_roles if role.strip()}

    def dependency(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        user_roles = _extract_role_names(current_user)

        if current_user.is_superuser:
            return current_user

        missing = normalized_required - user_roles
        if missing:
            raise ForbiddenError(
                message="You do not have all required roles for this action.",
                detail={
                    "required_roles": sorted(normalized_required),
                    "user_roles": sorted(user_roles),
                    "missing_roles": sorted(missing),
                },
            )

        return current_user

    return dependency


def require_superuser(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Require superuser access.
    """
    if not current_user.is_superuser:
        raise ForbiddenError(message="Superuser access is required.")
    return current_user


def require_any_authenticated_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Simple passthrough dependency for authenticated active users.
    """
    return current_user


# Optional convenience aliases for common patterns.
require_admin = require_roles("TENANT_ADMIN", "ADMIN")
require_clinical_staff = require_roles("TENANT_ADMIN", "ADMIN", "CLINICIAN", "DOCTOR", "NURSE")
require_lab_staff = require_roles("TENANT_ADMIN", "ADMIN", "LAB_SCIENTIST", "LAB_TECHNICIAN")
require_pharmacy_staff = require_roles("TENANT_ADMIN", "ADMIN", "PHARMACIST")
require_billing_staff = require_roles("TENANT_ADMIN", "ADMIN", "BILLING_OFFICER", "CASHIER")
require_hr_staff = require_roles("TENANT_ADMIN", "ADMIN", "HR_MANAGER", "HR_OFFICER")


# ============================================================
# PERMISSION-BASED DEPENDENCIES
# ============================================================


def _normalize_permission_codes(codes: Iterable[str]) -> set[str]:
    """
    Normalize permission codes for comparison.
    """
    return {code.strip().upper() for code in codes if code and code.strip()}


def require_permission(*permission_codes: str, require_all: bool = False):
    """
    Build a dependency that requires the current user to hold the specified
    permission(s) via assigned roles.

    Behavior
    --------
    - Superusers always pass.
    - When `require_all` is True, the user must have every supplied permission.
    - Otherwise, having any one permission is sufficient.

    Example
    -------
        @router.post("/patients")
        def create_patient(
            current_user: Annotated[User, Depends(require_permission("PATIENT_CREATE"))],
        ): ...
    """
    normalized_required = _normalize_permission_codes(permission_codes)
    if not normalized_required:
        raise ValueError("require_permission needs at least one permission code.")

    def dependency(
        current_user: Annotated[User, Depends(get_current_active_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> User:
        # Lazy import to avoid circular dependency at module import time.
        from app.repositories.permission_repository import PermissionRepository

        if current_user.is_superuser:
            return current_user

        repo = PermissionRepository(db)
        held_codes = repo.get_permission_codes_for_user(current_user.id)

        if require_all:
            missing = normalized_required - held_codes
            if missing:
                raise ForbiddenError(
                    message="You do not have all required permissions for this action.",
                    detail={
                        "required_permissions": sorted(normalized_required),
                        "missing_permissions": sorted(missing),
                    },
                )
        else:
            if not held_codes.intersection(normalized_required):
                raise ForbiddenError(
                    message="You do not have permission to perform this action.",
                    detail={
                        "required_permissions": sorted(normalized_required),
                    },
                )

        return current_user

    return dependency


def require_all_permissions(*permission_codes: str):
    """
    Convenience wrapper that requires all supplied permissions.
    """
    return require_permission(*permission_codes, require_all=True)


def require_any_permission(*permission_codes: str):
    """
    Convenience wrapper that requires at least one of the supplied permissions.
    """
    return require_permission(*permission_codes, require_all=False)