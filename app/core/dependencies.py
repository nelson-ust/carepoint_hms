# carepoint_hms/app/core/dependencies.py
from __future__ import annotations

"""
carepoint_hms.app.core.dependencies

Centralized dependency exports and composite dependencies for Carepoint HMS.

Purpose
-------
This module provides a single place to import common FastAPI dependencies used
across the application.

It re-exports:
- authentication dependencies
- role-based access dependencies
- two-factor dependencies

It also defines composite dependencies for common route protection patterns.

Why this exists
---------------
- reduces repetitive imports in route modules
- keeps route definitions cleaner
- provides one stable import surface for security dependencies
- allows creation of common composite access patterns in one place

Typical usage
-------------
Example:

    from typing import Annotated
    from fastapi import APIRouter, Depends
    from app.models.all_models import User
    from app.core.dependencies import CurrentActiveUser, AdminUser

    router = APIRouter()

    @router.get("/me")
    def get_me(current_user: CurrentActiveUser):
        return current_user

    @router.get("/admin-only")
    def admin_only(current_user: AdminUser):
        return {"message": "ok"}

Notes
-----
- This module assumes your route-level security still uses dependency injection.
- Middleware can attach request context, but authorization should remain here.
"""

from typing import Annotated

from fastapi import Depends

from app.models.all_models import User, SaaSAdmin

# ---------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------
from app.dependencies.auth import (
    oauth2_scheme,
    get_token_payload,
    get_access_token_payload,
    get_refresh_token_payload,
    get_current_user,
    get_current_active_user,
    get_current_session,
    get_current_active_user_with_session,
    get_current_superuser,
    get_current_saas_admin,
    get_current_saas_superuser,
)

# ---------------------------------------------------------------------
# Role dependencies
# ---------------------------------------------------------------------
from app.dependencies.role import (
    require_roles,
    require_all_roles,
    require_superuser,
    require_any_authenticated_user,
    require_admin,
    require_clinical_staff,
    require_lab_staff,
    require_pharmacy_staff,
    require_billing_staff,
    require_hr_staff,
    require_permission,
    require_all_permissions,
    require_any_permission,
)

# ---------------------------------------------------------------------
# Two-factor dependencies
# ---------------------------------------------------------------------
from app.dependencies.two_factor import (
    require_two_factor_verified,
    require_user_two_factor_enabled,
    require_verified_email,
    require_verified_phone,
    require_verified_email_and_two_factor,
    require_verified_phone_and_two_factor,
    require_fully_verified_user,
)

# ---------------------------------------------------------------------
# Subscription / SaaS dependencies
# ---------------------------------------------------------------------
from app.dependencies.subscription import (
    require_plan_feature,
    get_subscription_service,
)


# ============================================================
# TYPE ALIASES FOR CLEANER ROUTE SIGNATURES
# ============================================================

TokenPayload = Annotated[dict, Depends(get_token_payload)]
AccessTokenPayload = Annotated[dict, Depends(get_access_token_payload)]
RefreshTokenPayload = Annotated[dict, Depends(get_refresh_token_payload)]

CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]
CurrentActiveUserWithSession = Annotated[User, Depends(get_current_active_user_with_session)]
CurrentSuperuser = Annotated[User, Depends(get_current_superuser)]
CurrentSaaSAdmin = Annotated[SaaSAdmin, Depends(get_current_saas_admin)]
CurrentSaaSSuperuser = Annotated[SaaSAdmin, Depends(get_current_saas_superuser)]

AnyAuthenticatedUser = Annotated[User, Depends(require_any_authenticated_user)]
TwoFactorVerifiedUser = Annotated[User, Depends(require_two_factor_verified)]
TwoFactorEnabledUser = Annotated[User, Depends(require_user_two_factor_enabled)]
VerifiedEmailUser = Annotated[User, Depends(require_verified_email)]
VerifiedPhoneUser = Annotated[User, Depends(require_verified_phone)]
VerifiedEmailAndTwoFactorUser = Annotated[User, Depends(require_verified_email_and_two_factor)]
VerifiedPhoneAndTwoFactorUser = Annotated[User, Depends(require_verified_phone_and_two_factor)]
FullyVerifiedUser = Annotated[User, Depends(require_fully_verified_user)]

AdminUser = Annotated[User, Depends(require_admin)]
ClinicalStaffUser = Annotated[User, Depends(require_clinical_staff)]
LabStaffUser = Annotated[User, Depends(require_lab_staff)]
PharmacyStaffUser = Annotated[User, Depends(require_pharmacy_staff)]
BillingStaffUser = Annotated[User, Depends(require_billing_staff)]
HRStaffUser = Annotated[User, Depends(require_hr_staff)]


# ============================================================
# COMMON COMPOSITE DEPENDENCIES
# ============================================================

def require_authenticated_verified_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
    _: Annotated[User, Depends(require_two_factor_verified)],
) -> User:
    """
    Require an active authenticated user whose access token has completed 2FA.

    This is useful for routes that do not require role checks but still need
    a verified authenticated session.
    """
    return current_user


def require_admin_with_two_factor(
    current_user: Annotated[User, Depends(require_admin)],
    _: Annotated[User, Depends(require_two_factor_verified)],
) -> User:
    """
    Require admin-level access and a 2FA-verified token.
    """
    return current_user


def require_clinical_staff_with_two_factor(
    current_user: Annotated[User, Depends(require_clinical_staff)],
    _: Annotated[User, Depends(require_two_factor_verified)],
) -> User:
    """
    Require clinical staff access and a 2FA-verified token.
    """
    return current_user


def require_billing_staff_with_two_factor(
    current_user: Annotated[User, Depends(require_billing_staff)],
    _: Annotated[User, Depends(require_two_factor_verified)],
) -> User:
    """
    Require billing staff access and a 2FA-verified token.
    """
    return current_user


def require_hr_staff_with_two_factor(
    current_user: Annotated[User, Depends(require_hr_staff)],
    _: Annotated[User, Depends(require_two_factor_verified)],
) -> User:
    """
    Require HR staff access and a 2FA-verified token.
    """
    return current_user


def require_superuser_with_two_factor(
    current_user: Annotated[User, Depends(require_superuser)],
    _: Annotated[User, Depends(require_two_factor_verified)],
) -> User:
    """
    Require superuser access and a 2FA-verified token.
    """
    return current_user


# ============================================================
# COMPOSITE TYPE ALIASES
# ============================================================

AuthenticatedVerifiedUser = Annotated[User, Depends(require_authenticated_verified_user)]
AdminUserWithTwoFactor = Annotated[User, Depends(require_admin_with_two_factor)]
ClinicalStaffUserWithTwoFactor = Annotated[User, Depends(require_clinical_staff_with_two_factor)]
BillingStaffUserWithTwoFactor = Annotated[User, Depends(require_billing_staff_with_two_factor)]
HRStaffUserWithTwoFactor = Annotated[User, Depends(require_hr_staff_with_two_factor)]
SuperuserWithTwoFactor = Annotated[User, Depends(require_superuser_with_two_factor)]


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Auth primitives
    "oauth2_scheme",
    "get_token_payload",
    "get_access_token_payload",
    "get_refresh_token_payload",
    "get_current_user",
    "get_current_active_user",
    "get_current_session",
    "get_current_active_user_with_session",
    "get_current_superuser",

    # Role primitives
    "require_roles",
    "require_all_roles",
    "require_superuser",
    "require_any_authenticated_user",
    "require_admin",
    "require_clinical_staff",
    "require_lab_staff",
    "require_pharmacy_staff",
    "require_billing_staff",
    "require_hr_staff",
    "require_permission",
    "require_all_permissions",
    "require_any_permission",

    # Two-factor primitives
    "require_two_factor_verified",
    "require_user_two_factor_enabled",
    "require_verified_email",
    "require_verified_phone",
    "require_verified_email_and_two_factor",
    "require_verified_phone_and_two_factor",
    "require_fully_verified_user",

    # Type aliases
    "TokenPayload",
    "AccessTokenPayload",
    "RefreshTokenPayload",
    "CurrentUser",
    "CurrentActiveUser",
    "CurrentActiveUserWithSession",
    "CurrentSuperuser",
    "AnyAuthenticatedUser",
    "TwoFactorVerifiedUser",
    "TwoFactorEnabledUser",
    "VerifiedEmailUser",
    "VerifiedPhoneUser",
    "VerifiedEmailAndTwoFactorUser",
    "VerifiedPhoneAndTwoFactorUser",
    "FullyVerifiedUser",
    "AdminUser",
    "ClinicalStaffUser",
    "LabStaffUser",
    "PharmacyStaffUser",
    "BillingStaffUser",
    "HRStaffUser",

    # Subscription / SaaS primitives
    "require_plan_feature",
    "get_subscription_service",

    # Composite dependencies

    "require_authenticated_verified_user",
    "require_admin_with_two_factor",
    "require_clinical_staff_with_two_factor",
    "require_billing_staff_with_two_factor",
    "require_hr_staff_with_two_factor",
    "require_superuser_with_two_factor",

    # Composite type aliases
    "AuthenticatedVerifiedUser",
    "AdminUserWithTwoFactor",
    "ClinicalStaffUserWithTwoFactor",
    "BillingStaffUserWithTwoFactor",
    "HRStaffUserWithTwoFactor",
    "SuperuserWithTwoFactor",
]