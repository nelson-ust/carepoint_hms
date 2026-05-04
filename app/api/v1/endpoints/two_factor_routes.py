# app/api/v1/endpoints/two_factor_routes.py
from __future__ import annotations

"""
app.api.v1.endpoints.two_factor_routes

Admin-facing two-factor management endpoints.

Endpoints
---------
- list challenges (paginated, filterable)
- get challenge details
- expire a single challenge
- expire all open challenges for a user
- enable / disable a user's master 2FA flag (admin override)

Security
--------
All endpoints require an authenticated admin user.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser
from app.schemas.two_factor_schema import (
    TwoFactorChallengeActionResponseSchema,
    TwoFactorChallengeListResponseSchema,
    TwoFactorChallengeReadSchema,
    TwoFactorPolicyResponseSchema,
    TwoFactorPolicyUpdateSchema,
)
from app.services.two_factor_service import TwoFactorService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/two-factor",
    tags=["Two-Factor Administration"],
)


def get_two_factor_service(
    db: Annotated[Session, Depends(get_db)],
) -> TwoFactorService:
    return TwoFactorService(db)


def _serialize_challenge(challenge) -> dict:
    return {
        "id": challenge.id,
        "user_id": challenge.user_id,
        "challenge_type": str(challenge.challenge_type),
        "purpose": str(challenge.purpose),
        "destination": getattr(challenge, "destination", None),
        "attempt_count": int(getattr(challenge, "attempt_count", 0) or 0),
        "max_attempts": int(getattr(challenge, "max_attempts", 5) or 5),
        "is_verified": bool(getattr(challenge, "is_verified", False)),
        "verified_at": getattr(challenge, "verified_at", None),
        "expires_at": challenge.expires_at,
        "created_at": getattr(challenge, "created_at", None),
        "updated_at": getattr(challenge, "updated_at", None),
    }


@router.get(
    "/challenges",
    response_model=TwoFactorChallengeListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List two-factor challenges",
)
def list_challenges(
    _: AdminUser,
    service: Annotated[TwoFactorService, Depends(get_two_factor_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = Query(None, description="Filter by user ID."),
    purpose: Optional[str] = Query(
        None,
        description="Filter by purpose: LOGIN, PASSWORD_RESET, EMAIL_VERIFICATION, PHONE_VERIFICATION, HIGH_RISK_ACTION.",
    ),
    is_verified: Optional[bool] = Query(None, description="Filter by verification state."),
    only_active: bool = Query(False, description="Only return non-verified, non-expired challenges."),
):
    """
    List two-factor challenges across users (admin view).
    """
    items, total = service.list_challenges(
        skip=skip,
        limit=limit,
        user_id=user_id,
        purpose=purpose,
        is_verified=is_verified,
        only_active=only_active,
    )
    return paginate_response(
        items=[_serialize_challenge(c) for c in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Two-factor challenges fetched successfully.",
    )


@router.get(
    "/challenges/{challenge_id}",
    response_model=TwoFactorChallengeReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get challenge details",
)
def get_challenge(
    challenge_id: int,
    _: AdminUser,
    service: Annotated[TwoFactorService, Depends(get_two_factor_service)],
):
    challenge = service.get_challenge(challenge_id)
    return _serialize_challenge(challenge)


@router.post(
    "/challenges/{challenge_id}/expire",
    response_model=TwoFactorChallengeActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Force-expire a two-factor challenge",
)
def expire_challenge(
    challenge_id: int,
    actor: AdminUser,
    service: Annotated[TwoFactorService, Depends(get_two_factor_service)],
    reason: Optional[str] = Query(None, max_length=500),
):
    challenge = service.expire_challenge(challenge_id, actor_user_id=actor.id, reason=reason)
    return {
        "success": True,
        "message": "Challenge expired successfully.",
        "challenge": _serialize_challenge(challenge),
    }


@router.post(
    "/users/{user_id}/expire-open-challenges",
    status_code=status.HTTP_200_OK,
    summary="Expire all open challenges for a user",
)
def expire_open_challenges_for_user(
    user_id: int,
    actor: AdminUser,
    service: Annotated[TwoFactorService, Depends(get_two_factor_service)],
    reason: Optional[str] = Query(None, max_length=500),
):
    count = service.expire_all_open_challenges_for_user(
        user_id,
        actor_user_id=actor.id,
        reason=reason,
    )
    return {
        "success": True,
        "message": "All open challenges expired for user.",
        "user_id": user_id,
        "expired_count": count,
    }


@router.post(
    "/users/{user_id}/policy",
    response_model=TwoFactorPolicyResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Update a user's master 2FA policy",
)
def update_user_policy(
    user_id: int,
    payload: TwoFactorPolicyUpdateSchema,
    actor: AdminUser,
    service: Annotated[TwoFactorService, Depends(get_two_factor_service)],
):
    """
    Enable or disable a user's master 2FA flag from the admin context.
    """
    user = service.update_user_two_factor_policy(user_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": (
            "Two-factor authentication enabled for user."
            if payload.enable_two_factor
            else "Two-factor authentication disabled for user."
        ),
        "user_id": user.id,
        "is_two_factor_enabled": bool(user.is_two_factor_enabled),
    }
