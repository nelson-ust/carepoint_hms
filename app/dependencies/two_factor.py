# carepoint_hms/app/dependencies/two_factor.py
from __future__ import annotations

"""
Two-factor authentication dependencies for Carepoint HMS.

This module contains dependencies that enforce:
- whether the current route requires a 2FA-verified access token
- whether the current user has a verified email/phone when needed
- whether the user's account has 2FA enabled when needed
"""

from typing import Annotated

from fastapi import Depends

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.dependencies.auth import (
    get_access_token_payload,
    get_current_active_user,
)
from app.models.all_models import User


def require_two_factor_verified(
    payload: Annotated[dict, Depends(get_access_token_payload)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Require that the current access token has completed second-factor verification.

    This is intended for sensitive operations where the route should only be
    accessible after OTP verification.
    """
    if current_user.is_superuser:
        # Superusers still need active accounts, but you may decide to bypass
        # token-level 2FA enforcement here if your policy allows it.
        pass

    if not payload.get("two_factor_verified", False):
        raise UnauthorizedError(
            message="Two-factor verification is required for this action.",
            detail={"two_factor_verified": False},
        )

    return current_user


def require_user_two_factor_enabled(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Require that the user's account has 2FA enabled.
    """
    if not current_user.is_two_factor_enabled:
        raise ForbiddenError(
            message="Two-factor authentication must be enabled for this action.",
            detail={"is_two_factor_enabled": False},
        )

    return current_user


def require_verified_email(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Require that the user's email address has been verified.
    """
    if not current_user.is_email_verified:
        raise ForbiddenError(
            message="Verified email is required for this action.",
            detail={"is_email_verified": False},
        )

    return current_user


def require_verified_phone(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Require that the user's phone number has been verified.
    """
    if not current_user.is_phone_verified:
        raise ForbiddenError(
            message="Verified phone number is required for this action.",
            detail={"is_phone_verified": False},
        )

    return current_user


def require_verified_email_and_two_factor(
    current_user: Annotated[User, Depends(require_verified_email)],
    _: Annotated[User, Depends(require_two_factor_verified)],
) -> User:
    """
    Require both verified email and a 2FA-verified access token.
    """
    return current_user


def require_verified_phone_and_two_factor(
    current_user: Annotated[User, Depends(require_verified_phone)],
    _: Annotated[User, Depends(require_two_factor_verified)],
) -> User:
    """
    Require both verified phone and a 2FA-verified access token.
    """
    return current_user


def require_fully_verified_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
    payload: Annotated[dict, Depends(get_access_token_payload)],
) -> User:
    """
    Require an active user with verified email, verified phone, enabled 2FA,
    and a token that has completed second-factor verification.

    This is useful for very sensitive administrative or financial operations.
    """
    if not current_user.is_email_verified:
        raise ForbiddenError(message="Verified email is required.")

    if not current_user.is_phone_verified:
        raise ForbiddenError(message="Verified phone number is required.")

    if not current_user.is_two_factor_enabled:
        raise ForbiddenError(message="Two-factor authentication must be enabled.")

    if not payload.get("two_factor_verified", False):
        raise UnauthorizedError(message="Two-factor verification is required.")

    return current_user