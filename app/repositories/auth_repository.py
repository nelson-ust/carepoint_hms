from __future__ import annotations

"""
app.repositories.auth_repository

Repository layer for authentication and identity-related database operations.

Purpose
-------
This module centralizes direct database operations for:

- retrieving users for login/authentication
- retrieving users by username/email/phone
- loading roles for authenticated-user profile responses
- updating password hashes
- marking email/phone verification state
- enabling/disabling two-factor authentication flags
- updating user status / activation state
- loading session records
- creating and managing 2FA challenge records
- loading lightweight profile information

Design goals
------------
- keep raw SQLAlchemy query logic out of route handlers
- keep auth service focused on business rules and security orchestration
- provide reusable helpers for login, OTP, verification,
  password reset, and session flows
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.all_models import (
    PasswordHistory,
    Role,
    TwoFactorChallenge,
    User,
    UserRoleAssociation,
    UserSession,
)


class AuthRepository:
    """
    Repository for authentication-related persistence and lookup operations.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize repository with active SQLAlchemy session.

        Args:
            db: Active SQLAlchemy session.
        """
        self.db = db

    # ============================================================
    # USER LOOKUPS
    # ============================================================

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Return a user by primary key if not soft-deleted.
        """
        return (
            self.db.query(User)
            .filter(
                User.id == user_id,
                User.is_deleted.is_(False),
            )
            .first()
        )

    def get_user_with_roles_by_id(self, user_id: int) -> Optional[User]:
        """
        Return a user with staff profile, roles, sessions, and 2FA challenges loaded.
        """
        return (
            self.db.query(User)
            .options(
                joinedload(User.staff_profile),
                selectinload(User.user_roles).joinedload(UserRoleAssociation.role),
                selectinload(User.sessions),
                selectinload(User.two_factor_challenges),
            )
            .filter(
                User.id == user_id,
                User.is_deleted.is_(False),
            )
            .first()
        )

    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Return a user by username if not soft-deleted.
        """
        normalized = username.strip().lower()
        return (
            self.db.query(User)
            .filter(
                func.lower(User.username) == normalized,
                User.is_deleted.is_(False),
            )
            .first()
        )

    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Return a user by email if not soft-deleted.
        """
        normalized = email.strip().lower()
        return (
            self.db.query(User)
            .filter(
                func.lower(User.email) == normalized,
                User.is_deleted.is_(False),
            )
            .first()
        )

    def get_user_by_phone_number(self, phone_number: str) -> Optional[User]:
        """
        Return a user by phone number if not soft-deleted.
        """
        normalized = phone_number.strip()
        return (
            self.db.query(User)
            .filter(
                User.phone_number == normalized,
                User.is_deleted.is_(False),
            )
            .first()
        )

    def get_user_by_identifier(self, identifier: str) -> Optional[User]:
        """
        Resolve a login identifier against username, email, or phone number.
        """
        normalized = identifier.strip()
        normalized_lower = normalized.lower()

        return (
            self.db.query(User)
            .filter(
                or_(
                    func.lower(User.username) == normalized_lower,
                    func.lower(User.email) == normalized_lower,
                    User.phone_number == normalized,
                ),
                User.is_deleted.is_(False),
            )
            .first()
        )

    def get_user_with_roles_by_identifier(self, identifier: str) -> Optional[User]:
        """
        Resolve a login identifier and eagerly load roles, staff profile, sessions,
        and 2FA challenges.
        """
        normalized = identifier.strip()
        normalized_lower = normalized.lower()

        return (
            self.db.query(User)
            .options(
                joinedload(User.staff_profile),
                selectinload(User.user_roles).joinedload(UserRoleAssociation.role),
                selectinload(User.sessions),
                selectinload(User.two_factor_challenges),
            )
            .filter(
                or_(
                    func.lower(User.username) == normalized_lower,
                    func.lower(User.email) == normalized_lower,
                    User.phone_number == normalized,
                ),
                User.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_user_by_id(self, user_id: int) -> User:
        """
        Return a user by ID or raise ValueError.
        """
        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User with id={user_id} was not found.")
        return user

    # ============================================================
    # ROLE LOOKUPS
    # ============================================================

    def get_role_by_id(self, role_id: int) -> Optional[Role]:
        """
        Return a role by primary key if not soft-deleted.
        """
        return (
            self.db.query(Role)
            .filter(
                Role.id == role_id,
                Role.is_deleted.is_(False),
            )
            .first()
        )

    def get_role_by_name(self, name: str) -> Optional[Role]:
        """
        Return a role by name if not soft-deleted.
        """
        normalized = name.strip().lower()
        return (
            self.db.query(Role)
            .filter(
                func.lower(Role.name) == normalized,
                Role.is_deleted.is_(False),
            )
            .first()
        )

    def get_role_by_code(self, code: str) -> Optional[Role]:
        """
        Return a role by code if not soft-deleted.
        """
        normalized = code.strip().upper()
        return (
            self.db.query(Role)
            .filter(
                func.upper(Role.code) == normalized,
                Role.is_deleted.is_(False),
            )
            .first()
        )

    def list_user_roles(self, user_id: int) -> list[Role]:
        """
        Return all active roles linked to a user through UserRoleAssociation.
        """
        user = self.get_user_with_roles_by_id(user_id)
        if not user:
            return []

        roles: list[Role] = []
        for user_role in user.user_roles or []:
            role = getattr(user_role, "role", None)
            if role is not None and role not in roles:
                roles.append(role)

        return roles

    # ============================================================
    # PASSWORD MANAGEMENT
    # ============================================================

    def update_password_hash(self, user: User, new_password_hash: str) -> User:
        """
        Update a user's stored password hash.
        """
        user.password_hash = new_password_hash
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def update_last_login(self, user: User, when: Optional[datetime] = None) -> User:
        """
        Update the user's last login timestamp.
        """
        user.last_login_at = when or datetime.utcnow()
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def update_password_changed_at(self, user: User, when: Optional[datetime] = None) -> User:
        """
        Update the user's password changed timestamp.
        """
        user.password_changed_at = when or datetime.utcnow()
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    # ============================================================
    # PASSWORD RESET TOKEN
    # ============================================================

    def set_password_reset_token(
        self,
        user: User,
        *,
        encrypted_token: str,
        expires_at: datetime,
    ) -> User:
        """
        Store an encrypted password reset token and its expiry on the user.

        Only the encrypted form of the token is persisted; the raw token is
        delivered to the user via the emailed reset link and is recovered by
        decrypting this column at reset time.
        """
        user.password_reset_token = encrypted_token
        user.password_reset_token_expires_at = expires_at
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def clear_password_reset_token(self, user: User) -> User:
        """
        Clear a consumed or invalidated password reset token from the user.
        """
        user.password_reset_token = None
        user.password_reset_token_expires_at = None
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def list_users_with_pending_reset_token(self) -> list[User]:
        """
        Return all (non-deleted) users that currently have a password reset
        token stored.

        The token is encrypted at rest with a non-deterministic cipher, so it
        cannot be matched with a direct SQL equality filter. The caller
        decrypts each candidate's token and compares it against the supplied
        value. In practice only a handful of users have an active reset token
        at any moment, so this candidate set is very small.
        """
        return (
            self.db.query(User)
            .filter(
                User.password_reset_token.isnot(None),
                User.is_deleted.is_(False),
            )
            .all()
        )

    # ============================================================
    # LOCKOUT / FAILED LOGIN TRACKING
    # ============================================================

    def increment_failed_login_attempts(
        self, user: User, *, when: Optional[datetime] = None
    ) -> User:
        """
        Increment failed login attempt counter and timestamp.
        """
        user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
        user.last_failed_login_at = when or datetime.utcnow()
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def reset_failed_login_attempts(self, user: User) -> User:
        """
        Reset failed login attempts and clear lockout.
        """
        user.failed_login_attempts = 0
        user.locked_until = None
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def lock_user(
        self,
        user: User,
        *,
        until: Optional[datetime] = None,
        status_value=None,
    ) -> User:
        """
        Set lockout window on a user.
        """
        user.locked_until = until
        if status_value is not None:
            user.status = status_value
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    # ============================================================
    # PASSWORD HISTORY
    # ============================================================

    def insert_password_history(
        self,
        user_id: int,
        password_hash: str,
        when: Optional[datetime] = None,
    ) -> PasswordHistory:
        """
        Insert a row into the PasswordHistory table.
        """
        history = PasswordHistory(
            user_id=user_id,
            password_hash=password_hash,
            changed_at=when or datetime.utcnow(),
        )
        self.db.add(history)
        self.db.flush()
        self.db.refresh(history)
        return history

    def get_recent_password_hashes(self, user_id: int, limit: int = 5) -> list[str]:
        """
        Return the most recent password hashes for a user, newest first.
        """
        rows = (
            self.db.query(PasswordHistory.password_hash)
            .filter(
                PasswordHistory.user_id == user_id,
                PasswordHistory.is_deleted.is_(False),
            )
            .order_by(PasswordHistory.changed_at.desc(), PasswordHistory.id.desc())
            .limit(max(int(limit), 0))
            .all()
        )
        return [row[0] for row in rows if row[0]]

    # ============================================================
    # STATUS / ACTIVATION
    # ============================================================

    def update_user_status(self, user: User, status) -> User:
        """
        Update a user's status.
        """
        user.status = status
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    # ============================================================
    # EMAIL / PHONE VERIFICATION
    # ============================================================

    def mark_email_verified(self, user: User, *, verified: bool = True) -> User:
        """
        Mark a user's email as verified/unverified.
        """
        user.is_email_verified = verified
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def mark_phone_verified(self, user: User, *, verified: bool = True) -> User:
        """
        Mark a user's phone number as verified/unverified.
        """
        user.is_phone_verified = verified
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def update_email(self, user: User, email: Optional[str]) -> User:
        """
        Update a user's email address.
        """
        user.email = email
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def update_phone_number(self, user: User, phone_number: Optional[str]) -> User:
        """
        Update a user's phone number.
        """
        user.phone_number = phone_number
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    # ============================================================
    # TWO-FACTOR AUTHENTICATION FLAGS
    # ============================================================

    def configure_two_factor(
        self,
        user: User,
        *,
        is_two_factor_enabled: bool,
    ) -> User:
        """
        Update the master two-factor toggle on the user record.
        """
        user.is_two_factor_enabled = is_two_factor_enabled
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def disable_two_factor(self, user: User) -> User:
        """
        Disable two-factor authentication.
        """
        user.is_two_factor_enabled = False
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    # ============================================================
    # USER SESSION HELPERS
    # ============================================================

    def create_user_session(
        self,
        *,
        user_id: int,
        session_token_jti: str,
        refresh_token_jti: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        login_at: datetime,
        expires_at: Optional[datetime] = None,
        revoked_at: Optional[datetime] = None,
        is_current: bool = True,
        device_fingerprint: Optional[str] = None,
    ) -> UserSession:
        """
        Create and persist a user session.
        """
        session = UserSession(
            user_id=user_id,
            session_token_jti=session_token_jti,
            refresh_token_jti=refresh_token_jti,
            ip_address=ip_address,
            user_agent=user_agent,
            login_at=login_at,
            expires_at=expires_at,
            revoked_at=revoked_at,
            is_current=is_current,
            device_fingerprint=device_fingerprint,
        )
        self.db.add(session)
        self.db.flush()
        self.db.refresh(session)
        return session

    def get_session_by_session_jti(self, session_token_jti: str) -> Optional[UserSession]:
        """
        Return a session by access-token JTI.
        """
        return (
            self.db.query(UserSession)
            .filter(
                UserSession.session_token_jti == session_token_jti,
                UserSession.is_deleted.is_(False),
            )
            .first()
        )

    def get_session_by_refresh_jti(self, refresh_token_jti: str) -> Optional[UserSession]:
        """
        Return a session by refresh-token JTI.
        """
        return (
            self.db.query(UserSession)
            .filter(
                UserSession.refresh_token_jti == refresh_token_jti,
                UserSession.is_deleted.is_(False),
            )
            .first()
        )

    def list_user_sessions(self, user_id: int) -> list[UserSession]:
        """
        Return all non-deleted sessions for a user.
        """
        return (
            self.db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.is_deleted.is_(False),
            )
            .order_by(UserSession.login_at.desc(), UserSession.id.desc())
            .all()
        )

    def revoke_session(self, session: UserSession, when: Optional[datetime] = None) -> UserSession:
        """
        Revoke a single session.
        """
        session.revoked_at = when or datetime.utcnow()
        session.is_current = False
        self.db.add(session)
        self.db.flush()
        self.db.refresh(session)
        return session

    def revoke_all_user_sessions(self, user_id: int, when: Optional[datetime] = None) -> int:
        """
        Revoke all active sessions for a user.

        Returns:
            int: Number of sessions updated.
        """
        sessions = (
            self.db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.is_deleted.is_(False),
                UserSession.is_current.is_(True),
            )
            .all()
        )

        revoked_at = when or datetime.utcnow()
        for session in sessions:
            session.revoked_at = revoked_at
            session.is_current = False
            self.db.add(session)

        self.db.flush()
        return len(sessions)

    # ============================================================
    # TWO-FACTOR CHALLENGE HELPERS
    # ============================================================

    def create_two_factor_challenge(
        self,
        *,
        user_id: int,
        challenge_type,
        purpose,
        destination: Optional[str],
        code_hash: str,
        expires_at: datetime,
        max_attempts: int = 5,
    ) -> TwoFactorChallenge:
        """
        Create and persist a two-factor challenge.
        """
        challenge = TwoFactorChallenge(
            user_id=user_id,
            challenge_type=challenge_type,
            purpose=purpose,
            destination=destination,
            code_hash=code_hash,
            attempt_count=0,
            max_attempts=max_attempts,
            is_verified=False,
            verified_at=None,
            expires_at=expires_at,
        )
        self.db.add(challenge)
        self.db.flush()
        self.db.refresh(challenge)
        return challenge

    def get_two_factor_challenge_by_id(self, challenge_id: int) -> Optional[TwoFactorChallenge]:
        """
        Return a two-factor challenge by ID.
        """
        return (
            self.db.query(TwoFactorChallenge)
            .filter(
                TwoFactorChallenge.id == challenge_id,
                TwoFactorChallenge.is_deleted.is_(False),
            )
            .first()
        )

    def get_two_factor_challenge_by_code_hash(
        self,
        *,
        code_hash: str,
        purpose=None,
    ) -> Optional[TwoFactorChallenge]:
        """
        Return the most recent challenge matching a stored code hash.

        Used by the password-reset flow to resolve an opaque reset token
        (the token is hashed and looked up directly by its hash).
        """
        query = self.db.query(TwoFactorChallenge).filter(
            TwoFactorChallenge.code_hash == code_hash,
            TwoFactorChallenge.is_deleted.is_(False),
        )

        if purpose is not None:
            query = query.filter(TwoFactorChallenge.purpose == purpose)

        return query.order_by(
            TwoFactorChallenge.date_created.desc(),
            TwoFactorChallenge.id.desc(),
        ).first()

    def list_user_two_factor_challenges(self, user_id: int) -> list[TwoFactorChallenge]:
        """
        Return challenges for a user ordered by newest first.
        """
        return (
            self.db.query(TwoFactorChallenge)
            .filter(
                TwoFactorChallenge.user_id == user_id,
                TwoFactorChallenge.is_deleted.is_(False),
            )
            .order_by(TwoFactorChallenge.date_created.desc(), TwoFactorChallenge.id.desc())
            .all()
        )

    def get_latest_open_two_factor_challenge(
        self,
        *,
        user_id: int,
        purpose=None,
    ) -> Optional[TwoFactorChallenge]:
        """
        Return the latest non-verified two-factor challenge for a user,
        optionally filtered by purpose.
        """
        query = self.db.query(TwoFactorChallenge).filter(
            TwoFactorChallenge.user_id == user_id,
            TwoFactorChallenge.is_verified.is_(False),
            TwoFactorChallenge.is_deleted.is_(False),
        )

        if purpose is not None:
            query = query.filter(TwoFactorChallenge.purpose == purpose)

        return query.order_by(
            TwoFactorChallenge.date_created.desc(),
            TwoFactorChallenge.id.desc(),
        ).first()

    def increment_two_factor_attempt_count(
        self,
        challenge: TwoFactorChallenge,
    ) -> TwoFactorChallenge:
        """
        Increment failed-attempt count for a challenge.
        """
        challenge.attempt_count += 1
        self.db.add(challenge)
        self.db.flush()
        self.db.refresh(challenge)
        return challenge

    def mark_two_factor_challenge_verified(
        self,
        challenge: TwoFactorChallenge,
        when: Optional[datetime] = None,
    ) -> TwoFactorChallenge:
        """
        Mark a two-factor challenge as verified.
        """
        challenge.is_verified = True
        challenge.verified_at = when or datetime.utcnow()
        self.db.add(challenge)
        self.db.flush()
        self.db.refresh(challenge)
        return challenge

    # ============================================================
    # PROFILE HELPERS
    # ============================================================

    def get_authenticated_profile(self, user_id: int) -> Optional[User]:
        """
        Return a user with profile/role/session relationships for `/auth/me`.
        """
        return self.get_user_with_roles_by_id(user_id)

    # ============================================================
    # UNIQUENESS / EXISTENCE HELPERS
    # ============================================================

    def username_exists(self, username: str, *, exclude_user_id: Optional[int] = None) -> bool:
        """
        Return whether a username already exists.
        """
        query = self.db.query(func.count(User.id)).filter(
            func.lower(User.username) == username.strip().lower(),
            User.is_deleted.is_(False),
        )

        if exclude_user_id is not None:
            query = query.filter(User.id != exclude_user_id)

        return bool(query.scalar() or 0)

    def email_exists(self, email: str, *, exclude_user_id: Optional[int] = None) -> bool:
        """
        Return whether an email already exists.
        """
        query = self.db.query(func.count(User.id)).filter(
            func.lower(User.email) == email.strip().lower(),
            User.is_deleted.is_(False),
        )

        if exclude_user_id is not None:
            query = query.filter(User.id != exclude_user_id)

        return bool(query.scalar() or 0)

    def phone_number_exists(
        self,
        phone_number: str,
        *,
        exclude_user_id: Optional[int] = None,
    ) -> bool:
        """
        Return whether a phone number already exists.
        """
        query = self.db.query(func.count(User.id)).filter(
            User.phone_number == phone_number.strip(),
            User.is_deleted.is_(False),
        )

        if exclude_user_id is not None:
            query = query.filter(User.id != exclude_user_id)

        return bool(query.scalar() or 0)

    # ============================================================
    # GENERIC PERSISTENCE HELPERS
    # ============================================================

    def save_user(self, user: User) -> User:
        """
        Persist and refresh a user record.
        """
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def save_session(self, session: UserSession) -> UserSession:
        """
        Persist and refresh a user session record.
        """
        self.db.add(session)
        self.db.flush()
        self.db.refresh(session)
        return session

    def save_two_factor_challenge(self, challenge: TwoFactorChallenge) -> TwoFactorChallenge:
        """
        Persist and refresh a two-factor challenge record.
        """
        self.db.add(challenge)
        self.db.flush()
        self.db.refresh(challenge)
        return challenge