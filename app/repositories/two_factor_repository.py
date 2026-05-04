# app/repositories/two_factor_repository.py
from __future__ import annotations

"""
app.repositories.two_factor_repository

Repository for administrative two-factor challenge operations.

The auth_repository handles challenges as part of login/verification flows.
This repository centralizes admin-facing queries: listing, filtering, and
expiring challenges.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import NotFoundError
from app.models.all_models import TwoFactorChallenge


class TwoFactorRepository:
    """
    Repository for two-factor challenge persistence operations.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ============================================================
    # LOOKUPS
    # ============================================================

    def get_by_id(self, challenge_id: int) -> Optional[TwoFactorChallenge]:
        return (
            self.db.query(TwoFactorChallenge)
            .options(joinedload(TwoFactorChallenge.user))
            .filter(
                TwoFactorChallenge.id == challenge_id,
                TwoFactorChallenge.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, challenge_id: int) -> TwoFactorChallenge:
        challenge = self.get_by_id(challenge_id)
        if not challenge:
            raise NotFoundError(
                message="Two-factor challenge not found.",
                detail={"challenge_id": challenge_id},
            )
        return challenge

    # ============================================================
    # LISTING
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
        """
        Paginated list of challenges with optional filters.

        Args:
            only_active: If True, returns only non-verified, non-expired challenges.
        """
        query = self.db.query(TwoFactorChallenge).filter(
            TwoFactorChallenge.is_deleted.is_(False)
        )

        if user_id is not None:
            query = query.filter(TwoFactorChallenge.user_id == user_id)

        if purpose:
            query = query.filter(TwoFactorChallenge.purpose == purpose)

        if is_verified is not None:
            query = query.filter(TwoFactorChallenge.is_verified.is_(is_verified))

        if only_active:
            now = datetime.now(timezone.utc)
            query = query.filter(
                TwoFactorChallenge.is_verified.is_(False),
                TwoFactorChallenge.expires_at > now,
            )

        total = query.with_entities(func.count(TwoFactorChallenge.id)).scalar() or 0
        items = (
            query.order_by(
                TwoFactorChallenge.date_created.desc(),
                TwoFactorChallenge.id.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    # ============================================================
    # MUTATIONS
    # ============================================================

    def expire_challenge(
        self,
        challenge: TwoFactorChallenge,
        when: Optional[datetime] = None,
    ) -> TwoFactorChallenge:
        """
        Force-expire a challenge by setting expires_at to now and marking it deleted.
        """
        challenge.expires_at = when or datetime.now(timezone.utc)
        challenge.is_deleted = True
        self.db.add(challenge)
        self.db.flush()
        self.db.refresh(challenge)
        return challenge

    def expire_all_open_for_user(
        self,
        user_id: int,
        when: Optional[datetime] = None,
    ) -> int:
        """
        Expire all open challenges for a user.
        """
        now = when or datetime.now(timezone.utc)
        challenges = (
            self.db.query(TwoFactorChallenge)
            .filter(
                TwoFactorChallenge.user_id == user_id,
                TwoFactorChallenge.is_verified.is_(False),
                TwoFactorChallenge.is_deleted.is_(False),
            )
            .all()
        )
        for challenge in challenges:
            challenge.expires_at = now
            challenge.is_deleted = True
            self.db.add(challenge)
        self.db.flush()
        return len(challenges)
