# carepoint_hms/app/dependencies/auth.py
from __future__ import annotations

"""
Authentication dependencies for Carepoint HMS.

This module contains reusable FastAPI dependencies for:
- extracting and decoding bearer tokens
- resolving the current authenticated user
- ensuring the user is active
- ensuring the current session is still valid

These dependencies are intended for use in route handlers and higher-level
security dependencies such as role and 2FA checks.
"""

from typing import Annotated, Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db, get_master_db
from app.core.multitenancy import get_current_tenant_id
from app.core.exceptions import NotFoundError, UnauthorizedError, ForbiddenError
from app.core.security import decode_token, validate_token_type
from app.models.all_models import User, UserRoleAssociation, Role, UserSession, SaaSAdmin, TenantSubscription, SubscriptionPlan
from app.core.enums import SubscriptionStatus


# FastAPI documents OAuth2PasswordBearer as the standard dependency for bearer
# token extraction in protected routes.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# For SaaS routes, we use HTTPBearer so Swagger UI provides a generic "Bearer" input
# instead of automatically injecting the Tenant login token.
saas_bearer = HTTPBearer()


def _get_subject_as_int(payload: dict) -> int:
    """
    Extract and validate the token subject as an integer user ID.

    Raises:
        UnauthorizedError: If the subject is missing or not a valid integer.
    """
    subject = payload.get("sub")
    if subject is None:
        raise UnauthorizedError(message="Token subject is missing.")

    try:
        return int(subject)
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError(
            message="Invalid token subject.",
            detail={"sub": subject},
        ) from exc


def get_token_payload(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> dict:
    """
    Decode the incoming bearer token and return its payload.
    """
    return decode_token(token)


def get_access_token_payload(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> dict:
    """
    Decode and validate that the incoming token is an access token.
    """
    return validate_token_type(token, "access")


def get_saas_access_token_payload(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(saas_bearer)],
) -> dict:
    """
    Decode and validate a SaaS access token.
    Uses HTTPBearer so Swagger UI doesn't inject the tenant token.
    """
    return validate_token_type(credentials.credentials, "access")


def get_refresh_token_payload(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> dict:
    """
    Decode and validate that the incoming token is a refresh token.
    """
    return validate_token_type(token, "refresh")


def get_current_user(
    payload: Annotated[dict, Depends(get_access_token_payload)],
    db: Annotated[Session, Depends(get_db)],
    master_db: Annotated[Session, Depends(get_master_db)],
) -> User | SaaSAdmin:
    """
    Resolve the current authenticated user from the JWT access token.

    Loads user roles eagerly so downstream role checks do not cause unnecessary
    lazy-loading round trips. Supports returning a SaaSAdmin if the token is a SaaS token.
    """
    user_id = _get_subject_as_int(payload)
    
    if payload.get("is_saas_admin"):
        admin = (
            master_db.query(SaaSAdmin)
            .filter(
                SaaSAdmin.id == user_id,
                SaaSAdmin.status == "ACTIVE",
            )
            .first()
        )
        if not admin:
            raise NotFoundError(message="Authenticated SaaS Admin was not found.")
        return admin
    
    # Cross-tenant token prevention
    token_tenant_id = payload.get("tenant_id")
    current_tenant_id = get_current_tenant_id()
    
    if token_tenant_id is not None and current_tenant_id is not None:
        if token_tenant_id != current_tenant_id:
            raise ForbiddenError(
                message="Token is not valid for this tenant.",
                detail={"token_tenant": token_tenant_id, "current_tenant": current_tenant_id}
            )

    user = (
        db.query(User)
        .options(
            joinedload(User.user_roles).joinedload(UserRoleAssociation.role)
        )
        .filter(
            User.id == user_id,
            User.is_deleted.is_(False),
        )
        .first()
    )

    if not user:
        raise NotFoundError(
            message="Authenticated user was not found.",
            detail={"user_id": user_id},
        )

    return user


def get_current_active_user(
    current_user: Annotated[User | SaaSAdmin, Depends(get_current_user)],
) -> User | SaaSAdmin:
    """
    Ensure the current user is active and allowed to access the system.
    """
    if str(current_user.status).upper() != "ACTIVE":
        raise UnauthorizedError(
            message="User account is not active.",
            detail={"status": str(current_user.status)},
        )

    if current_user.is_deleted:
        raise UnauthorizedError(message="User account is no longer available.")

    return current_user


def get_current_session(
    payload: Annotated[dict, Depends(get_access_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> UserSession:
    """
    Resolve the current session from the token JTI.

    This lets you invalidate tokens server-side by revoking the stored session.
    """
    jti = payload.get("jti")
    if not jti:
        raise UnauthorizedError(message="Token JTI is missing.")

    session = (
        db.query(UserSession)
        .filter(
            UserSession.session_token_jti == jti,
            UserSession.is_deleted.is_(False),
        )
        .first()
    )

    if not session:
        raise UnauthorizedError(message="Session not found.")

    if session.revoked_at is not None or session.is_current is False:
        raise UnauthorizedError(message="Session has been revoked.")

    return session


def get_current_active_user_with_session(
    current_user: Annotated[User, Depends(get_current_active_user)],
    _: Annotated[UserSession, Depends(get_current_session)],
) -> User:
    """
    Ensure both the current user and the current session are valid.

    Returns:
        User: The authenticated active user.
    """
    return current_user


def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Ensure the current user is a superuser.
    """
    if not current_user.is_superuser:
        raise UnauthorizedError(message="Superuser access is required.")
    return current_user


def get_current_saas_admin(
    payload: Annotated[dict, Depends(get_saas_access_token_payload)],
    db: Annotated[Session, Depends(get_master_db)],
) -> SaaSAdmin:
    """
    Resolve the current authenticated SaaS Admin from the JWT access token.
    """
    if not payload.get("is_saas_admin"):
        raise ForbiddenError(message="This endpoint requires a SaaS Admin token.")
        
    user_id = _get_subject_as_int(payload)

    admin = (
        db.query(SaaSAdmin)
        .filter(
            SaaSAdmin.id == user_id,
            SaaSAdmin.status == "ACTIVE",
        )
        .first()
    )

    if not admin:
        raise NotFoundError(
            message="Authenticated SaaS Admin was not found or is inactive.",
            detail={"admin_id": user_id},
        )

    return admin

def get_current_saas_superuser(
    current_admin: Annotated[SaaSAdmin, Depends(get_current_saas_admin)],
) -> SaaSAdmin:
    """
    Ensure the current SaaS Admin is a superuser.
    """
    # Both legacy is_superuser and the new SUPER_ADMIN platform role
    # qualify as superuser-level access.
    role = getattr(current_admin, "platform_role", None)
    role_value = getattr(role, "value", role)
    if not current_admin.is_superuser and str(role_value or "").upper() != "SUPER_ADMIN":
        raise ForbiddenError(message="SaaS Superuser access is required.")
    return current_admin


def require_saas_role(*allowed_roles: str):
    """
    Build a dependency that requires the current SaaS admin to hold at
    least one of the supplied platform roles.

    SUPER_ADMIN always satisfies any role check.

    Example::

        admin: Annotated[
            SaaSAdmin,
            Depends(require_saas_role("BILLING_ADMIN", "SUPER_ADMIN")),
        ]
    """
    normalized = {str(r).strip().upper() for r in allowed_roles if r}
    if not normalized:
        raise ValueError("require_saas_role needs at least one role.")

    def dependency(
        current_admin: Annotated[SaaSAdmin, Depends(get_current_saas_admin)],
    ) -> SaaSAdmin:
        role = getattr(current_admin, "platform_role", None)
        role_value = str(getattr(role, "value", role) or "").upper()

        if current_admin.is_superuser or role_value == "SUPER_ADMIN":
            return current_admin
        if role_value in normalized:
            return current_admin

        raise ForbiddenError(
            message="You do not have the required platform role for this action.",
            detail={
                "required": sorted(normalized),
                "current_role": role_value or None,
            },
        )

    return dependency


# Convenience aliases for common platform-role checks.
require_saas_super_admin = require_saas_role("SUPER_ADMIN")
require_saas_support_admin = require_saas_role("SUPER_ADMIN", "SUPPORT_ADMIN")
require_saas_billing_admin = require_saas_role("SUPER_ADMIN", "BILLING_ADMIN")
require_saas_auditor = require_saas_role("SUPER_ADMIN", "SYSTEM_AUDITOR")

class RequireModule:
    """
    Dependency class to enforce that the current tenant has access to a
    specific module.

    Effective access combines:
      * the active subscription plan (must be ACTIVE or TRIALING),
      * the plan-level ``has_<module>`` flag, and
      * any per-tenant override stored in :class:`TenantModuleAccess`.
    """

    def __init__(self, module_name: str):
        self.module_name = module_name

    def __call__(
        self,
        current_user: Annotated[User | SaaSAdmin, Depends(get_current_active_user)],
        master_db: Annotated[Session, Depends(get_master_db)],
    ):
        # SaaS Admins bypass module checks.
        if isinstance(current_user, SaaSAdmin):
            return current_user

        tenant_id = get_current_tenant_id()
        if not tenant_id:
            raise ForbiddenError(message="Tenant context is required to access this module.")

        sub = (
            master_db.query(TenantSubscription)
            .join(SubscriptionPlan)
            .filter(
                TenantSubscription.tenant_id == tenant_id,
                TenantSubscription.status.in_(
                    [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
                ),
            )
            .first()
        )

        if not sub or not sub.plan:
            raise ForbiddenError(message="Active subscription required.")

        flag_name = f"has_{self.module_name}"
        if not getattr(sub.plan, flag_name, False):
            raise ForbiddenError(
                message=(
                    f"Your current subscription plan does not include access "
                    f"to the {self.module_name} module."
                ),
                detail={"module": self.module_name, "plan": sub.plan.name},
            )

        # Per-tenant override (admins can disable a module without changing the plan).
        from app.models.all_models import TenantModuleAccess

        override = (
            master_db.query(TenantModuleAccess)
            .filter(
                TenantModuleAccess.tenant_id == tenant_id,
                TenantModuleAccess.module_code == self.module_name,
                TenantModuleAccess.is_deleted.is_(False),
            )
            .first()
        )
        if override is not None and not override.is_enabled:
            # Log the denial
            try:
                from app.dependencies.subscription import get_subscription_service
                service = get_subscription_service(master_db)
                from fastapi import Request
                # We can't easily get the request object here without changing signature 
                # but RequireModule is a class, we can add it to __call__ if we want.
                # However, many existing callers might not expect it.
                # For now, I'll just log with available info.
                service.log_access_attempt(
                    tenant_id=tenant_id,
                    feature_code=self.module_name,
                    user_id=getattr(current_user, "id", None),
                    is_denied=True,
                    reason="Module disabled by override"
                )
            except Exception:
                pass

            raise ForbiddenError(
                message=(
                    f"The {self.module_name} module has been disabled for "
                    f"your tenant by an administrator."
                ),
                detail={"module": self.module_name},
            )

        return current_user