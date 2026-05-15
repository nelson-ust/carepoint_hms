# carepoint_hms/app/core/security.py
from __future__ import annotations

"""
carepoint_hms.app.core.security

Centralized security helpers for Carepoint HMS.

Purpose
-------
This module provides:
- JWT access and refresh token creation
- JWT decoding and validation
- password hashing and verification wrappers
- 2FA / OTP challenge helpers
- simple session token metadata helpers
- reusable utilities for authenticated user flows

Design goals
------------
- keep security logic consistent across the application
- align with the current User, UserSession, and TwoFactorChallenge models
- support login flows with optional 2FA
- support refresh token rotation
- keep helper functions small and testable

Dependencies
------------
This module expects:
- app.core.config.settings
- app.core.exceptions
- app.utils.password_utils
- app.utils.otp_utils
- app.utils.helpers
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import hashlib
import secrets
import uuid

from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import OTPError, TokenError, UnauthorizedError, ValidationError
from app.utils.helpers import generate_uuid_str
from app.utils.otp_utils import generate_otp, get_otp_expiry, hash_otp, verify_otp as verify_otp_hash
from app.utils.password_utils import hash_password, verify_password


# ============================================================
# JWT / TOKEN HELPERS
# ============================================================

def _utc_now() -> datetime:
    """
    Return the current UTC datetime.

    This helper keeps token timestamp generation consistent across the module.
    """
    return datetime.now(timezone.utc)


def _to_timestamp(value: datetime) -> int:
    """
    Convert a datetime to an integer UNIX timestamp.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp())


def create_token_payload(
    *,
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    role: Optional[str] = None,
    roles: Optional[list[str]] = None,
    tenant_id: Optional[int] = None,
    tenant_code: Optional[str] = None,
    two_factor_verified: bool = False,
    extra_claims: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Build a JWT payload.

    Args:
        subject: Usually the user ID or unique login identifier.
        token_type: Token type such as 'access' or 'refresh'.
        expires_delta: How long the token should remain valid.
        role: Optional primary role.
        roles: Optional list of role names.
        tenant_id: Numeric tenant identifier this token is scoped to.
        tenant_code: Short tenant code (slug) carried for client convenience
            and used as a tenant resolution fallback by middleware.
        two_factor_verified: Whether second-factor verification has been completed.
        extra_claims: Optional extra claims to include.

    Returns:
        dict[str, Any]: JWT payload dictionary.
    """
    now = _utc_now()
    expire_at = now + expires_delta
    jti = str(uuid.uuid4())

    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "jti": jti,
        "iat": _to_timestamp(now),
        "nbf": _to_timestamp(now),
        "exp": _to_timestamp(expire_at),
        "tenant_id": tenant_id,
        "tenant_code": tenant_code,
        "two_factor_verified": two_factor_verified,
    }

    # Add role-related claims if available.
    if role is not None:
        payload["role"] = role
    if roles is not None:
        payload["roles"] = roles

    if extra_claims:
        payload.update(extra_claims)

    return payload


def create_access_token(
    *,
    subject: str,
    role: Optional[str] = None,
    roles: Optional[list[str]] = None,
    tenant_id: Optional[int] = None,
    tenant_code: Optional[str] = None,
    two_factor_verified: bool = False,
    expires_minutes: Optional[int] = None,
    extra_claims: Optional[dict[str, Any]] = None,
) -> tuple[str, dict[str, Any]]:
    """
    Create a signed JWT access token.

    Returns:
        tuple[str, dict[str, Any]]:
            The encoded token and the decoded payload used to create it.
    """
    minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    payload = create_token_payload(
        subject=subject,
        token_type="access",
        expires_delta=timedelta(minutes=minutes),
        role=role,
        roles=roles,
        tenant_id=tenant_id,
        tenant_code=tenant_code,
        two_factor_verified=two_factor_verified,
        extra_claims=extra_claims,
    )
    token = jwt.encode(
        payload,
        settings.secret_key_value,
        algorithm=settings.ALGORITHM,
    )
    return token, payload


def create_refresh_token(
    *,
    subject: str,
    role: Optional[str] = None,
    roles: Optional[list[str]] = None,
    tenant_id: Optional[int] = None,
    tenant_code: Optional[str] = None,
    expires_days: Optional[int] = None,
    extra_claims: Optional[dict[str, Any]] = None,
) -> tuple[str, dict[str, Any]]:
    """
    Create a signed JWT refresh token.
    """
    days = expires_days or settings.REFRESH_TOKEN_EXPIRE_DAYS
    payload = create_token_payload(
        subject=subject,
        token_type="refresh",
        expires_delta=timedelta(days=days),
        role=role,
        roles=roles,
        tenant_id=tenant_id,
        tenant_code=tenant_code,
        two_factor_verified=False,
        extra_claims=extra_claims,
    )
    token = jwt.encode(
        payload,
        settings.secret_key_value,
        algorithm=settings.ALGORITHM,
    )
    return token, payload


def create_reset_token(
    *,
    subject: str,
    tenant_id: Optional[int] = None,
    tenant_code: Optional[str] = None,
    expires_minutes: Optional[int] = None,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    """
    Create a signed JWT password reset token.

    The token is short-lived. When ``expires_minutes`` is not supplied it
    falls back to ``settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`` so the
    expiry window is centrally configurable.
    """
    minutes = expires_minutes or getattr(settings, "PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", 30)
    payload = create_token_payload(
        subject=subject,
        token_type="reset",
        expires_delta=timedelta(minutes=minutes),
        tenant_id=tenant_id,
        tenant_code=tenant_code,
        extra_claims=extra_claims,
    )
    token = jwt.encode(
        payload,
        settings.secret_key_value,
        algorithm=settings.ALGORITHM,
    )
    return token


def build_password_reset_link(reset_token: str, *, tenant_code: Optional[str] = None) -> str:
    """
    Build the frontend password-reset URL that carries the reset token.

    For tenant users the ``tenant_code`` is appended as a query parameter so
    the frontend can send it back as the ``X-Tenant-Code`` header when it
    calls the reset-password endpoint. SaaS admins have no tenant code.
    """
    from urllib.parse import urlencode

    base = str(getattr(settings, "FRONTEND_URL", "") or "").rstrip("/")
    path = str(getattr(settings, "PASSWORD_RESET_URL_PATH", "/reset-password") or "/reset-password")
    if not path.startswith("/"):
        path = "/" + path

    params: dict[str, str] = {"token": reset_token}
    if tenant_code:
        params["tenant_code"] = tenant_code

    return f"{base}{path}?{urlencode(params)}"


def generate_password_reset_token() -> str:
    """
    Generate a short, opaque, URL-safe password reset token.

    Unlike a JWT, this token carries no payload — it is just a random
    secret. The server stores only its hash and looks the token up at
    reset time, which keeps the emailed link short and makes the token
    trivially single-use and revocable.
    """
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """
    Deterministically hash a password reset token for storage and lookup.

    A plain (unsalted) SHA-256 digest is used so the token can be looked
    up directly by its hash. The raw token is never persisted.
    """
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Raises:
        TokenError: If the token is invalid or malformed.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key_value,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise TokenError(
            message="Invalid or expired token.",
            detail={"reason": str(exc)},
        ) from exc


def get_token_subject(token: str) -> str:
    """
    Extract the subject claim from a token.

    Raises:
        TokenError: If the token is missing a subject.
    """
    payload = decode_token(token)
    subject = payload.get("sub")
    if not subject:
        raise TokenError(message="Token subject is missing.")
    return str(subject)


def get_token_jti(token: str) -> str:
    """
    Extract the JWT ID from a token.
    """
    payload = decode_token(token)
    jti = payload.get("jti")
    if not jti:
        raise TokenError(message="Token JTI is missing.")
    return str(jti)


def get_token_type(token: str) -> str:
    """
    Extract the token type claim.
    """
    payload = decode_token(token)
    token_type = payload.get("type")
    if not token_type:
        raise TokenError(message="Token type is missing.")
    return str(token_type)


def validate_token_type(token: str, expected_type: str) -> dict[str, Any]:
    """
    Decode a token and validate its type.

    Raises:
        TokenError: If the token type does not match the expected type.
    """
    payload = decode_token(token)
    token_type = payload.get("type")
    if token_type != expected_type:
        raise TokenError(
            message=f"Expected a {expected_type} token.",
            detail={"received_type": token_type},
        )
    return payload


def ensure_two_factor_verified(token: str) -> dict[str, Any]:
    """
    Ensure an access token has completed 2FA verification.

    Raises:
        UnauthorizedError: If the token is not marked as 2FA verified.
    """
    payload = validate_token_type(token, "access")
    if not payload.get("two_factor_verified", False):
        raise UnauthorizedError(
            message="Two-factor verification is required.",
            detail={"two_factor_verified": False},
        )
    return payload


# ============================================================
# PASSWORD HELPERS
# ============================================================

def get_password_hash(password: str) -> str:
    """
    Hash a password using the shared password utility.
    """
    return hash_password(password)


def verify_user_password(plain_password: str, password_hash_value: str) -> bool:
    """
    Verify a user-supplied password against the stored hash.
    """
    return verify_password(plain_password, password_hash_value)


def validate_password_strength(password: str) -> None:
    """
    Validate password strength against the application policy.

    Rules:
    - Minimum 8 characters
    - Must include at least one uppercase letter
    - Must include at least one lowercase letter
    - Must include at least one digit
    - Must include at least one special character

    Raises:
    - ValidationError: If the password is too weak.
    """
    if not password or len(password) < 8:
        raise ValidationError(
            message="Password must be at least 8 characters long.",
            detail={"min_length": 8},
        )

    has_upper = any(ch.isupper() for ch in password)
    has_lower = any(ch.islower() for ch in password)
    has_digit = any(ch.isdigit() for ch in password)
    has_special = any(not ch.isalnum() for ch in password)

    if not all([has_upper, has_lower, has_digit, has_special]):
        raise ValidationError(
            message="Password must contain uppercase, lowercase, numbers, and special characters.",
            detail={
                "has_upper": has_upper,
                "has_lower": has_lower,
                "has_digit": has_digit,
                "has_special": has_special,
            },
        )


# ============================================================
# 2FA / OTP HELPERS
# ============================================================

def create_otp_challenge_payload(
    *,
    user_id: int,
    challenge_type: str,
    purpose: str,
    destination: Optional[str] = None,
    otp_length: Optional[int] = None,
    max_attempts: Optional[int] = None,
) -> dict[str, Any]:
    """
    Create a payload for persisting a TwoFactorChallenge record.

    This function does not write to the database. It prepares the data your
    repository/service should save in the TwoFactorChallenge model.

    Returns:
        dict[str, Any]:
            Includes the plain OTP for delivery and the hashed OTP for storage.
    """
    code = generate_otp(otp_length or settings.OTP_LENGTH)
    expiry = get_otp_expiry(settings.OTP_EXPIRE_MINUTES)

    return {
        "user_id": user_id,
        "challenge_type": challenge_type,
        "purpose": purpose,
        "destination": destination,
        "plain_code": code,           # send this by email/SMS, do not persist
        "code_hash": hash_otp(code),  # persist this in the DB
        "attempt_count": 0,
        "max_attempts": max_attempts or settings.OTP_MAX_ATTEMPTS,
        "is_verified": False,
        "verified_at": None,
        "expires_at": expiry,
    }


def verify_two_factor_code(
    *,
    plain_code: str,
    stored_code_hash: str,
    expires_at: datetime,
    attempt_count: int,
    max_attempts: int,
) -> bool:
    """
    Validate a submitted OTP against a stored challenge.

    Raises:
        OTPError: If the code is expired, invalid, or the attempt limit is reached.
    """
    now = _utc_now()

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if attempt_count >= max_attempts:
        raise OTPError(
            message="Maximum OTP attempts exceeded.",
            detail={"attempt_count": attempt_count, "max_attempts": max_attempts},
        )

    if now >= expires_at:
        raise OTPError(
            message="OTP has expired.",
            detail={"expires_at": expires_at.isoformat()},
        )

    if not verify_otp_hash(plain_code, stored_code_hash):
        raise OTPError(message="Invalid OTP supplied.")

    return True


def build_two_factor_success_update() -> dict[str, Any]:
    """
    Return a normalized update payload for a successfully verified challenge.
    """
    return {
        "is_verified": True,
        "verified_at": _utc_now(),
    }


# ============================================================
# ACCOUNT LOCKOUT HELPERS
# ============================================================

def is_account_locked(
    *,
    failed_attempts: int,
    locked_until: Optional[datetime],
    max_attempts: int,
) -> bool:
    """
    Determine if an account is currently locked based on failed attempts and cooldown.
    """
    if locked_until is None:
        return failed_attempts >= max_attempts

    now = _utc_now()
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)

    return now < locked_until


def build_lockout_update(
    *,
    current_failed_attempts: int,
    max_attempts: int,
    lockout_minutes: int,
) -> dict[str, Any]:
    """
    Calculate the next failed-login state and return a database update payload.
    """
    new_count = current_failed_attempts + 1
    locked_until = None

    if new_count >= max_attempts:
        locked_until = _utc_now() + timedelta(minutes=lockout_minutes)

    return {
        "failed_login_attempts": new_count,
        "locked_until": locked_until,
        "last_failed_login_at": _utc_now(),
    }


def build_lockout_reset_payload() -> dict[str, Any]:
    """
    Return a payload to reset failed login counters upon successful authentication.
    """
    return {
        "failed_login_attempts": 0,
        "locked_until": None,
    }


# ============================================================
# SESSION HELPERS
# ============================================================

def build_session_payload(
    *,
    user_id: int,
    access_payload: dict[str, Any],
    refresh_payload: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build a payload for persisting a UserSession record.

    This aligns with the current UserSession model fields. :contentReference[oaicite:2]{index=2}
    """
    exp = access_payload.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None

    return {
        "user_id": user_id,
        "session_token_jti": access_payload["jti"],
        "refresh_token_jti": refresh_payload["jti"] if refresh_payload else None,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "login_at": _utc_now(),
        "expires_at": expires_at,
        "revoked_at": None,
        "is_current": True,
    }


def build_session_revoke_payload() -> dict[str, Any]:
    """
    Return a normalized session revoke payload.
    """
    return {
        "revoked_at": _utc_now(),
        "is_current": False,
    }


def is_session_revoked(*, revoked_at: Optional[datetime], is_current: bool) -> bool:
    """
    Determine whether a session should be treated as revoked.
    """
    return bool(revoked_at is not None or not is_current)


# ============================================================
# HIGH-LEVEL AUTH FLOW HELPERS
# ============================================================

def build_login_result(
    *,
    user_id: int | str,
    role: Optional[str] = None,
    roles: Optional[list[str]] = None,
    two_factor_verified: bool = False,
    tenant_id: Optional[int] = None,
    tenant_code: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict[str, Any]:
    """
    Create access/refresh tokens and a session payload for login.

    Returns:
        dict[str, Any]:
            access token, refresh token, token payloads, and session payload.
    """
    access_token, access_payload = create_access_token(
        subject=str(user_id),
        role=role,
        roles=roles,
        tenant_id=tenant_id,
        tenant_code=tenant_code,
        two_factor_verified=two_factor_verified,
    )
    refresh_token, refresh_payload = create_refresh_token(
        subject=str(user_id),
        role=role,
        roles=roles,
        tenant_id=tenant_id,
        tenant_code=tenant_code,
    )
    session_payload = build_session_payload(
        user_id=int(user_id),
        access_payload=access_payload,
        refresh_payload=refresh_payload,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_payload": access_payload,
        "refresh_payload": refresh_payload,
        "session_payload": session_payload,
        "token_type": "bearer",
    }


def build_post_2fa_access_token(
    *,
    user_id: int | str,
    role: Optional[str] = None,
    roles: Optional[list[str]] = None,
    tenant_id: Optional[int] = None,
    tenant_code: Optional[str] = None,
) -> tuple[str, dict[str, Any]]:
    """
    Create a 2FA-verified access token after OTP verification succeeds.
    """
    return create_access_token(
        subject=str(user_id),
        role=role,
        roles=roles,
        tenant_id=tenant_id,
        tenant_code=tenant_code,
        two_factor_verified=True,
    )


def assert_user_is_active(*, status: str) -> None:
    """
    Validate that the user status allows login/access.

    Raises:
        UnauthorizedError: If the account is not active.
    """
    if str(status).upper() != "ACTIVE":
        raise UnauthorizedError(
            message="User account is not active.",
            detail={"status": status},
        )


def assert_login_password(
    *,
    plain_password: str,
    stored_password_hash: str,
) -> None:
    """
    Validate login password and raise a consistent auth error on failure.
    """
    if not verify_user_password(plain_password, stored_password_hash):
        raise UnauthorizedError(message="Invalid credentials.")