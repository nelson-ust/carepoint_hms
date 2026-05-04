# app/services/two_factor_service.py
from __future__ import annotations

"""
app.services.two_factor_service

Admin-facing service for two-factor challenge management.

Responsibilities
----------------
- list challenges with filters
- expire a single challenge
- expire all open challenges for a user
- toggle a user's master 2FA enable flag (admin override)
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.all_models import TwoFactorChallenge, User
from app.repositories.auth_repository import AuthRepository
from app.repositories.two_factor_repository import TwoFactorRepository
from app.schemas.two_factor_schema import TwoFactorPolicyUpdateSchema
from app.utils.security_event_util import record_security_event


class TwoFactorService:
    """
    Service layer for admin-facing 2FA operations.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = TwoFactorRepository(db)
        self.auth_repository = AuthRepository(db)

    # ============================================================
    # READ
    # ============================================================

    def list_challenges(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        user_id: Optional[int] = None,
        purpose: Optional[str] = None,
        is_verified: Optional[bool] = None,
        only_active: bool = False,
    ) -> tuple[list[TwoFactorChallenge], int]:
        return self.repository.list_challenges(
            skip=skip,
            limit=limit,
            user_id=user_id,
            purpose=purpose,
            is_verified=is_verified,
            only_active=only_active,
        )

    def get_challenge(self, challenge_id: int) -> TwoFactorChallenge:
        return self.repository.get_required_by_id(challenge_id)

    # ============================================================
    # MUTATIONS
    # ============================================================

    def expire_challenge(
        self,
        challenge_id: int,
        *,
        actor_user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> TwoFactorChallenge:
        challenge = self.repository.get_required_by_id(challenge_id)
        expired = self.repository.expire_challenge(challenge)

        record_security_event(
            self.db,
            user_id=expired.user_id,
            event_type="TWO_FACTOR_CHALLENGE_EXPIRED",
            severity="WARNING",
            event_detail=(
                f"Challenge {expired.id} expired by user {actor_user_id}."
            ),
            event_metadata={
                "actor_user_id": actor_user_id,
                "reason": reason,
                "challenge_id": expired.id,
                "purpose": str(expired.purpose),
            },
        )

        self.db.commit()
        return self.repository.get_required_by_id(expired.id)

    def expire_all_open_challenges_for_user(
        self,
        user_id: int,
        *,
        actor_user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> int:
        user = self.auth_repository.get_user_by_id(user_id)
        if not user:
            raise NotFoundError(
                message="User not found.",
                detail={"user_id": user_id},
            )

        count = self.repository.expire_all_open_for_user(user.id)

        record_security_event(
            self.db,
            user_id=user.id,
            event_type="TWO_FACTOR_CHALLENGES_EXPIRED",
            severity="WARNING",
            event_detail=(
                f"All open 2FA challenges expired for user {user.username} by user {actor_user_id}."
            ),
            event_metadata={
                "actor_user_id": actor_user_id,
                "reason": reason,
                "expired_count": count,
            },
        )

        self.db.commit()
        return count

    def update_user_two_factor_policy(
        self,
        user_id: int,
        payload: TwoFactorPolicyUpdateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> User:
        """
        Toggle a user's master 2FA flag from an admin context.
        """
        user = self.auth_repository.get_user_by_id(user_id)
        if not user:
            raise NotFoundError(
                message="User not found.",
                detail={"user_id": user_id},
            )

        previous_value = bool(user.is_two_factor_enabled)
        if payload.enable_two_factor:
            self.auth_repository.configure_two_factor(user, is_two_factor_enabled=True)
        else:
            self.auth_repository.disable_two_factor(user)

        record_security_event(
            self.db,
            user_id=user.id,
            event_type=(
                "TWO_FACTOR_ENABLED_BY_ADMIN" if payload.enable_two_factor
                else "TWO_FACTOR_DISABLED_BY_ADMIN"
            ),
            severity="WARNING",
            event_detail=(
                f"Two-factor policy for user {user.username} changed from "
                f"{previous_value} to {payload.enable_two_factor} by user {actor_user_id}."
            ),
            event_metadata={
                "actor_user_id": actor_user_id,
                "reason": payload.reason,
                "previous_value": previous_value,
                "new_value": bool(payload.enable_two_factor),
            },
        )

        self.db.commit()
        return user
