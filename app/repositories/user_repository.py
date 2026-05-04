# app/repositories/user_repository.py
from __future__ import annotations

"""
app.repositories.user_repository

Repository layer for administrative user CRUD and lookup logic.

Notes
-----
- This repository handles user persistence used by the admin user management
  module. Authentication-specific persistence stays in `auth_repository.py`.
- The two repositories share the same `User` model and may both be used in
  service-layer transactions; they should not commit independently.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.enums import UserStatus
from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.all_models import (
    Role,
    User,
    UserRoleAssociation,
    UserSession,
)


class UserRepository:
    """
    Repository for administrative user persistence operations.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ============================================================
    # SINGLE-RECORD LOOKUPS
    # ============================================================

    def _base_user_query(self):
        """
        Standard query that excludes soft-deleted users and eagerly loads roles.
        """
        return (
            self.db.query(User)
            .options(
                selectinload(User.user_roles).joinedload(UserRoleAssociation.role),
            )
            .filter(User.is_deleted.is_(False))
        )

    def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Return a user by primary key.
        """
        return self._base_user_query().filter(User.id == user_id).first()

    def get_required_by_id(self, user_id: int) -> User:
        """
        Return a user by ID or raise NotFoundError.
        """
        user = self.get_by_id(user_id)
        if not user:
            raise NotFoundError(message="User not found.", detail={"user_id": user_id})
        return user

    def get_by_username(self, username: str) -> Optional[User]:
        normalized = username.strip().lower()
        return (
            self._base_user_query()
            .filter(func.lower(User.username) == normalized)
            .first()
        )

    def get_by_email(self, email: str) -> Optional[User]:
        normalized = email.strip().lower()
        return (
            self._base_user_query()
            .filter(func.lower(User.email) == normalized)
            .first()
        )

    def get_by_phone_number(self, phone_number: str) -> Optional[User]:
        normalized = phone_number.strip()
        return (
            self._base_user_query()
            .filter(User.phone_number == normalized)
            .first()
        )

    # ============================================================
    # LISTING
    # ============================================================

    def list_users(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        status: Optional[UserStatus] = None,
        role_code: Optional[str] = None,
        is_superuser: Optional[bool] = None,
    ) -> tuple[list[User], int]:
        """
        Paginated list of users with optional filters.
        """
        query = self.db.query(User).filter(User.is_deleted.is_(False)).options(
            selectinload(User.user_roles).joinedload(UserRoleAssociation.role)
        )

        if status is not None:
            query = query.filter(User.status == status)

        if is_superuser is not None:
            query = query.filter(User.is_superuser.is_(is_superuser))

        if role_code:
            normalized_role_code = role_code.strip().upper()
            # Use a subquery to avoid duplicates from joining roles
            role_subquery = (
                self.db.query(UserRoleAssociation.user_id)
                .join(Role, Role.id == UserRoleAssociation.role_id)
                .filter(
                    func.upper(Role.code) == normalized_role_code,
                    UserRoleAssociation.is_deleted.is_(False),
                    Role.is_deleted.is_(False),
                )
                .subquery()
            )
            query = query.filter(User.id.in_(role_subquery))

        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(User.username).like(term),
                    func.lower(User.email).like(term),
                    func.lower(User.first_name).like(term),
                    func.lower(User.last_name).like(term),
                    func.lower(func.coalesce(User.middle_name, "")).like(term),
                )
            )

        total = query.with_entities(func.count(User.id)).scalar() or 0
        items = (
            query.order_by(User.last_name.asc(), User.first_name.asc(), User.id.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    # ============================================================
    # CRUD
    # ============================================================

    def create_user(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        first_name: str,
        last_name: str,
        middle_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        is_superuser: bool = False,
        is_email_verified: bool = False,
        is_phone_verified: bool = False,
        is_two_factor_enabled: bool = False,
        status: UserStatus = UserStatus.ACTIVE,
    ) -> User:
        """
        Create a new user. Caller must supply a hashed password.
        """
        if self.get_by_username(username):
            raise AlreadyExistsError(
                message="A user with this username already exists.",
                detail={"username": username},
            )

        if self.get_by_email(email):
            raise AlreadyExistsError(
                message="A user with this email already exists.",
                detail={"email": email},
            )

        if phone_number and self.get_by_phone_number(phone_number):
            raise AlreadyExistsError(
                message="A user with this phone number already exists.",
                detail={"phone_number": phone_number},
            )

        user = User(
            username=username,
            email=email,
            phone_number=phone_number,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            is_superuser=is_superuser,
            is_email_verified=is_email_verified,
            is_phone_verified=is_phone_verified,
            is_two_factor_enabled=is_two_factor_enabled,
            status=status,
        )
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def update_user(
        self,
        user: User,
        *,
        email: Optional[str] = None,
        phone_number: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        middle_name: Optional[str] = None,
        is_email_verified: Optional[bool] = None,
        is_phone_verified: Optional[bool] = None,
        is_two_factor_enabled: Optional[bool] = None,
    ) -> User:
        """
        Update mutable user profile fields.
        """
        if email and email.strip().lower() != (user.email or "").lower():
            existing = self.get_by_email(email)
            if existing and existing.id != user.id:
                raise AlreadyExistsError(
                    message="A user with this email already exists.",
                    detail={"email": email},
                )
            user.email = email.strip()

        if phone_number is not None and phone_number != user.phone_number:
            existing = self.get_by_phone_number(phone_number) if phone_number else None
            if existing and existing.id != user.id:
                raise AlreadyExistsError(
                    message="A user with this phone number already exists.",
                    detail={"phone_number": phone_number},
                )
            user.phone_number = phone_number or None

        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if middle_name is not None:
            user.middle_name = middle_name or None

        if is_email_verified is not None:
            user.is_email_verified = is_email_verified
        if is_phone_verified is not None:
            user.is_phone_verified = is_phone_verified
        if is_two_factor_enabled is not None:
            user.is_two_factor_enabled = is_two_factor_enabled

        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def update_status(self, user: User, status: UserStatus) -> User:
        """
        Update a user's status.
        """
        user.status = status
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def update_password_hash(self, user: User, new_password_hash: str) -> User:
        """
        Update a user's stored password hash.
        """
        user.password_hash = new_password_hash
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def update_password_changed_at(
        self, user: User, when: Optional[datetime] = None
    ) -> User:
        """
        Update password_changed_at on a user.
        """
        user.password_changed_at = when or datetime.utcnow()
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

    def soft_delete(self, user: User) -> User:
        """
        Soft-delete a user. Caller is responsible for revoking sessions.
        """
        user.is_deleted = True
        user.status = UserStatus.INACTIVE
        self.db.add(user)
        self.db.flush()
        return user

    # ============================================================
    # ROLE ASSIGNMENT
    # ============================================================

    def get_role_by_id(self, role_id: int) -> Optional[Role]:
        return (
            self.db.query(Role)
            .filter(Role.id == role_id, Role.is_deleted.is_(False))
            .first()
        )

    def get_roles_by_ids(self, role_ids: list[int]) -> list[Role]:
        if not role_ids:
            return []
        return (
            self.db.query(Role)
            .filter(Role.id.in_(role_ids), Role.is_deleted.is_(False))
            .all()
        )

    def assign_roles(self, user: User, role_ids: list[int]) -> User:
        """
        Assign roles to a user, idempotently.
        """
        existing_role_ids = {
            link.role_id for link in user.user_roles or []
            if not link.is_deleted
        }

        for role_id in role_ids:
            if role_id in existing_role_ids:
                continue
            link = UserRoleAssociation(user_id=user.id, role_id=role_id)
            self.db.add(link)

        self.db.flush()
        self.db.refresh(user)
        return user

    def revoke_roles(self, user: User, role_ids: list[int]) -> User:
        """
        Soft-detach roles from a user.
        """
        if not role_ids:
            return user

        (
            self.db.query(UserRoleAssociation)
            .filter(
                UserRoleAssociation.user_id == user.id,
                UserRoleAssociation.role_id.in_(role_ids),
            )
            .delete(synchronize_session=False)
        )
        self.db.flush()
        self.db.refresh(user)
        return user

    # ============================================================
    # SESSIONS
    # ============================================================

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

    def revoke_all_user_sessions(self, user_id: int, when: Optional[datetime] = None) -> int:
        """
        Revoke all currently active sessions for a user.
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
