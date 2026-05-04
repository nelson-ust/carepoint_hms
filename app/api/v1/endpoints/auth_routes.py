from __future__ import annotations

"""
app.api.v1.endpoints.auth_routes

FastAPI routes for authentication, password management, OTP verification,
email/phone verification, and optional two-factor authentication.

Purpose
-------
This module exposes API endpoints for:

- login
- token refresh
- logout
- authenticated user profile retrieval
- password change
- forgot password / reset password
- OTP verification / resend
- two-factor setup / verification
- email verification request / confirm
- phone verification request / confirm

Security
--------
Public endpoints:
- login
- refresh
- forgot password
- reset password
- otp verify
- otp resend
- email verification request / confirm
- phone verification request / confirm
- two-factor verify

Protected endpoints:
- logout
- me
- change password
- two-factor setup
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db, get_master_db_context
from app.core.multitenancy import get_current_tenant
from app.core.dependencies import CurrentActiveUser
from app.dependencies.auth import oauth2_scheme
from app.schemas.auth_schemas import (
    AccessTokenSchema,
    AuthActionResponseSchema,
    AuthMeResponseSchema,
    ChangePasswordSchema,
    EmailVerificationConfirmSchema,
    EmailVerificationRequestSchema,
    ForgotPasswordSchema,
    LoginPendingTwoFactorSchema,
    LoginSchema,
    LoginSuccessSchema,
    LogoutRequestSchema,
    LogoutResponseSchema,
    OTPActionResponseSchema,
    OTPResendSchema,
    OTPVerificationSuccessSchema,
    OTPVerifySchema,
    PasswordActionResponseSchema,
    PhoneVerificationConfirmSchema,
    PhoneVerificationRequestSchema,
    RefreshTokenRequestSchema,
    ResetPasswordSchema,
    TwoFactorSetupResponseSchema,
    TwoFactorSetupSchema,
    TwoFactorVerifySchema,
)
from app.schemas.saas_auth_schemas import (
    SaaSAdminLoginResponseSchema,
    SaaSAdminLoginSchema,
    SaaSAdminReadSchema,
    SaaSImpersonateSchema,
    SaaSImpersonateResponseSchema,
)
from app.core.dependencies import CurrentSaaSAdmin
from app.services.auth_service import AuthService
from app.services.saas_auth_service import SaaSAuthService

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


def get_auth_service(
    db: Annotated[Session, Depends(get_db)],
) -> AuthService:
    """
    Dependency provider for the authentication service.
    """
    return AuthService(db)


# ============================================================
# REQUEST CONTEXT HELPERS
# ============================================================


def _resolve_client_ip(request: Request) -> str:
    """
    Best-effort client IP extraction (honors proxy headers).
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


# ============================================================
# SERIALIZATION HELPERS
# ============================================================

def _serialize_auth_user(user: dict[str, Any] | Any) -> dict[str, Any]:
    """
    Serialize lightweight authenticated user payload.

    Accepts either a dict returned by the service or an ORM-like object.
    """
    if isinstance(user, dict):
        return user

    return {
        "id": user.id,
        "username": user.username,
        "email": getattr(user, "email", None),
        "phone_number": getattr(user, "phone_number", None),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "middle_name": getattr(user, "middle_name", None),
        "status": str(getattr(user, "status", None)) if getattr(user, "status", None) is not None else None,
        "is_superuser": getattr(user, "is_superuser", False),
        "is_email_verified": getattr(user, "is_email_verified", False),
        "is_phone_verified": getattr(user, "is_phone_verified", False),
        "is_two_factor_enabled": getattr(user, "is_two_factor_enabled", False),
    }


def _serialize_auth_profile(payload: dict[str, Any] | Any) -> dict[str, Any]:
    """
    Serialize authenticated user profile payload.
    """
    if isinstance(payload, dict):
        return payload

    return {
        "id": payload.id,
        "username": payload.username,
        "email": getattr(payload, "email", None),
        "phone_number": getattr(payload, "phone_number", None),
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "middle_name": getattr(payload, "middle_name", None),
        "status": str(getattr(payload, "status", None)) if getattr(payload, "status", None) is not None else None,
        "is_superuser": getattr(payload, "is_superuser", False),
        "is_email_verified": getattr(payload, "is_email_verified", False),
        "is_phone_verified": getattr(payload, "is_phone_verified", False),
        "is_two_factor_enabled": getattr(payload, "is_two_factor_enabled", False),
        "two_factor_method": str(getattr(payload, "two_factor_method", None)) if getattr(payload, "two_factor_method", None) is not None else None,
        "two_factor_email_enabled": getattr(payload, "two_factor_email_enabled", False),
        "two_factor_sms_enabled": getattr(payload, "two_factor_sms_enabled", False),
        "two_factor_whatsapp_enabled": getattr(payload, "two_factor_whatsapp_enabled", False),
        "two_factor_authenticator_enabled": getattr(payload, "two_factor_authenticator_enabled", False),
        "roles": [],
        "created_at": getattr(payload, "created_at", None),
        "updated_at": getattr(payload, "updated_at", None),
    }


# ============================================================
# ROUTES
# ============================================================

@router.post(
    "/login",
    response_model=LoginSuccessSchema | LoginPendingTwoFactorSchema | SaaSAdminLoginResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Login",
)
def login(
    payload: LoginSchema,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Authenticate a user by username, email, or phone number.

    Returns either:
    - success with tokens
    - pending two-factor verification response
    """
    ip_address = _resolve_client_ip(request)
    user_agent = request.headers.get("user-agent")

    if get_current_tenant() is None:
        # SaaS Admin Login
        with get_master_db_context() as master_db:
            saas_service = SaaSAuthService(master_db)
            saas_payload = SaaSAdminLoginSchema(email=payload.identifier, password=payload.password)
            return saas_service.login(saas_payload, ip_address=ip_address, user_agent=user_agent)

    result = service.login(payload, ip_address=ip_address, user_agent=user_agent)

    if result.get("two_factor_required"):
        return {
            "success": True,
            "message": result["message"],
            "user_id": result["user_id"],
            "identifier": result.get("identifier"),
            "two_factor_required": True,
            "two_factor_method": result.get("two_factor_method"),
            "challenge_reference": result.get("challenge_reference"),
        }

    return {
        "success": True,
        "message": result["message"],
        "user": _serialize_auth_user(result["user"]),
        "tokens": result["tokens"],
    }


@router.post(
    "/refresh",
    response_model=AccessTokenSchema,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
)
def refresh_access_token(
    payload: RefreshTokenRequestSchema,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Refresh access token using a refresh token.
    """
    if get_current_tenant() is None:
        with get_master_db_context() as master_db:
            saas_service = SaaSAuthService(master_db)
            return saas_service.refresh_access_token(payload.refresh_token)
            
    result = service.refresh_access_token(payload)
    return result


@router.post(
    "/impersonate",
    response_model=SaaSImpersonateResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Impersonate a tenant (SaaS Admins Only)",
)
def impersonate_tenant(
    payload: SaaSImpersonateSchema,
    current_admin: CurrentSaaSAdmin,
):
    """
    Generate an impersonation access token for a target tenant.
    Requires an active SaaS Admin session.
    """
    with get_master_db_context() as master_db:
        saas_service = SaaSAuthService(master_db)
        return saas_service.impersonate_tenant(current_admin.id, payload.tenant_code)


@router.post(
    "/logout",
    response_model=LogoutResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Logout",
)
def logout(
    payload: LogoutRequestSchema,
    current_user: CurrentActiveUser,
    service: Annotated[AuthService, Depends(get_auth_service)],
    access_token: Annotated[str, Depends(oauth2_scheme)],
):
    """
    Logout current authenticated user.

    Supports:
    - blacklisting a refresh token
    - revoking the current session by access token
    - optional all-sessions logout
    """
    if get_current_tenant() is None:
        with get_master_db_context() as master_db:
            saas_service = SaaSAuthService(master_db)
            return saas_service.logout(
                refresh_token=payload.refresh_token,
                all_sessions=payload.all_sessions,
                admin_id=current_user.id,
                access_token=access_token,
            )

    result = service.logout(
        refresh_token=payload.refresh_token,
        all_sessions=payload.all_sessions,
        current_user_id=current_user.id,
        access_token=access_token,
    )
    return result


@router.get(
    "/me",
    response_model=AuthMeResponseSchema | SaaSAdminReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated profile",
)
def get_authenticated_profile(
    current_user: CurrentActiveUser,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Return the currently authenticated user's profile.
    """
    if get_current_tenant() is None:
        # SaaS Admin Profile
        return {
            "id": current_user.id,
            "email": current_user.email,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "is_superuser": current_user.is_superuser,
            "is_active": current_user.is_active,
        }

    result = service.get_authenticated_profile(current_user.id)
    return {
        "success": True,
        "message": result["message"],
        "user": _serialize_auth_profile(result["user"]),
        "session": result.get("session"),
    }


@router.post(
    "/change-password",
    response_model=PasswordActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Change password",
)
def change_password(
    payload: ChangePasswordSchema,
    current_user: CurrentActiveUser,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Change password for the currently authenticated user.
    """
    result = service.change_password(current_user.id, payload)
    return result


@router.post(
    "/forgot-password",
    response_model=PasswordActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Forgot password",
)
def forgot_password(
    payload: ForgotPasswordSchema,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Begin password reset flow.
    """
    result = service.forgot_password(payload)
    return result


@router.post(
    "/reset-password",
    response_model=PasswordActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Reset password",
)
def reset_password(
    payload: ResetPasswordSchema,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Complete password reset using a reset token.
    """
    result = service.reset_password(payload)
    return result


@router.post(
    "/otp/verify",
    response_model=OTPVerificationSuccessSchema,
    status_code=status.HTTP_200_OK,
    summary="Verify OTP",
)
def verify_otp(
    payload: OTPVerifySchema,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Verify OTP for generic verification flows such as:
    - login 2FA
    - email verification
    - phone verification
    """
    result = service.verify_otp(payload)

    return {
        "success": True,
        "message": result["message"],
        "verified": result.get("verified", True),
        "user": _serialize_auth_user(result["user"]) if result.get("user") else None,
        "tokens": result.get("tokens"),
    }


@router.post(
    "/otp/resend",
    response_model=OTPActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Resend OTP",
)
def resend_otp(
    payload: OTPResendSchema,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Resend OTP for supported verification flows.

    Example payload:
    {
      "user_id": 1,
      "identifier": "user@example.com",
      "purpose": "LOGIN",
      "delivery_method": "EMAIL"
    }
    """
    return service.resend_otp(payload)


@router.post(
    "/two-factor/setup",
    response_model=TwoFactorSetupResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Setup or disable two-factor authentication",
)
def setup_two_factor(
    payload: TwoFactorSetupSchema,
    current_user: CurrentActiveUser,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Configure or disable two-factor authentication for the authenticated user.
    """
    result = service.setup_two_factor(current_user.id, payload)
    return result


@router.post(
    "/two-factor/verify",
    response_model=OTPVerificationSuccessSchema,
    status_code=status.HTTP_200_OK,
    summary="Verify two-factor authentication",
)
def verify_two_factor(
    payload: TwoFactorVerifySchema,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Verify login two-factor challenge and issue final tokens.
    """
    ip_address = _resolve_client_ip(request)
    user_agent = request.headers.get("user-agent")
    result = service.verify_two_factor(payload, ip_address=ip_address, user_agent=user_agent)
    return {
        "success": True,
        "message": result["message"],
        "verified": result.get("verified", True),
        "user": _serialize_auth_user(result["user"]) if result.get("user") else None,
        "tokens": result.get("tokens"),
    }


@router.post(
    "/email-verification/request",
    response_model=OTPActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Request email verification",
)
def request_email_verification(
    payload: EmailVerificationRequestSchema,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Request or resend email verification instructions.
    """
    result = service.request_email_verification(payload)
    return result


@router.post(
    "/email-verification/confirm",
    response_model=AuthActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Confirm email verification",
)
def confirm_email_verification(
    payload: EmailVerificationConfirmSchema,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Confirm email verification using a token.
    """
    result = service.confirm_email_verification(payload)
    return result


@router.post(
    "/phone-verification/request",
    response_model=OTPActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Request phone verification",
)
def request_phone_verification(
    payload: PhoneVerificationRequestSchema,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Request or resend phone verification challenge.
    """
    result = service.request_phone_verification(payload)
    return result


@router.post(
    "/phone-verification/confirm",
    response_model=AuthActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Confirm phone verification",
)
def confirm_phone_verification(
    payload: PhoneVerificationConfirmSchema,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """
    Confirm phone verification using token or OTP challenge.
    """
    result = service.confirm_phone_verification(payload)
    return result