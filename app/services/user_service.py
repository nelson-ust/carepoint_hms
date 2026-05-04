# app/services/user_service.py
from __future__ import annotations

"""
app.services.user_service

Service layer for administrative user management.

Responsibilities
----------------
- create users
- list and filter users
- update user profile fields
- change status (activate / suspend / lock)
- assign and revoke roles
- force password reset (admin)
- unlock account
- list active sessions and revoke them
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_master_db_context
from app.core.multitenancy import get_current_tenant_id

from app.core.enums import UserStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.security import get_password_hash, validate_password_strength
from app.models.all_models import User
from app.repositories.user_repository import UserRepository
from app.schemas.user_schema import (
    UserCreateSchema,
    UserPasswordResetSchema,
    UserRoleAssignmentSchema,
    UserStatusUpdateSchema,
    UserUpdateSchema,
)
from app.utils.security_event_util import record_security_event
from app.core.logger import get_logger

logger = get_logger(__name__)


class UserService:
    """
    Service layer for user administration.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = UserRepository(db)

    # ============================================================
    # READ
    # ============================================================

    def list_users(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        status: Optional[str] = None,
        role_code: Optional[str] = None,
        is_superuser: Optional[bool] = None,
    ) -> tuple[list[User], int]:
        """
        Return paginated users matching the filters.
        """
        normalized_status: Optional[UserStatus] = None
        if status is not None:
            try:
                normalized_status = UserStatus(status.strip().upper())
            except ValueError as exc:
                raise BadRequestError(
                    message="Invalid status filter.",
                    detail={"status": status},
                ) from exc

        return self.repository.list_users(
            skip=skip,
            limit=limit,
            search=search,
            status=normalized_status,
            role_code=role_code,
            is_superuser=is_superuser,
        )

    def get_user(self, user_id: int) -> User:
        """
        Return a user by ID.
        """
        return self.repository.get_required_by_id(user_id)

    # ============================================================
    # CREATE
    # ============================================================

    def create_user(
        self,
        payload: UserCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> User:
        """
        Create a new user.

        Validations:
        - password meets strength rules
        - role IDs (if any) all exist
        - tenant subscription user limit is not exceeded
        """
        validate_password_strength(payload.password)
        
        # Enforce Subscription max_users limit
        tenant_id = get_current_tenant_id()
        if tenant_id:
            with get_master_db_context() as master_db:
                from app.models.all_models import TenantSubscription, SubscriptionPlan
                from app.core.enums import SubscriptionStatus
                
                sub = (
                    master_db.query(TenantSubscription)
                    .join(SubscriptionPlan)
                    .filter(
                        TenantSubscription.tenant_id == tenant_id,
                        TenantSubscription.status == SubscriptionStatus.ACTIVE
                    )
                    .first()
                )
                
                if not sub or not sub.plan:
                    raise BadRequestError(message="Active subscription required to create users.")
                    
                current_user_count = self.db.query(func.count(User.id)).filter(User.is_deleted == False).scalar() or 0
                if current_user_count >= sub.plan.max_users:
                    raise BadRequestError(
                        message=f"User limit reached. Your subscription plan allows a maximum of {sub.plan.max_users} users.",
                        detail={"max_users": sub.plan.max_users, "current_users": current_user_count}
                    )

        if payload.role_ids:
            roles = self.repository.get_roles_by_ids(payload.role_ids)
            found_ids = {r.id for r in roles}
            missing = sorted(set(payload.role_ids) - found_ids)
            if missing:
                raise NotFoundError(
                    message="One or more roles were not found.",
                    detail={"missing_role_ids": missing},
                )

        password_hash = get_password_hash(payload.password)
        user = self.repository.create_user(
            username=payload.username,
            email=str(payload.email).strip().lower(),
            phone_number=payload.phone_number,
            password_hash=password_hash,
            first_name=payload.first_name,
            last_name=payload.last_name,
            middle_name=payload.middle_name,
            is_superuser=payload.is_superuser,
            is_email_verified=payload.is_email_verified,
            is_phone_verified=payload.is_phone_verified,
            is_two_factor_enabled=payload.is_two_factor_enabled,
            status=UserStatus.ACTIVE,
        )

        if payload.role_ids:
            self.repository.assign_roles(user, payload.role_ids)

        record_security_event(
            self.db,
            user_id=user.id,
            event_type="USER_CREATED",
            severity="INFO",
            event_detail=f"User {user.username} created by user {actor_user_id}.",
            event_metadata={"actor_user_id": actor_user_id, "role_ids": payload.role_ids},
        )

        self.db.commit()
        return self.repository.get_required_by_id(user.id)

    def invite_user(
        self,
        payload: UserCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> User:
        """
        Invite a new user to the tenant.
        Similar to create_user but sets status to INVITED.
        """
        import secrets
        import string
        
        # Generate a temporary strong password
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        temp_password = ''.join(secrets.choice(alphabet) for i in range(16))
        
        # Enforce Subscription max_users limit
        tenant_id = get_current_tenant_id()
        if tenant_id:
            with get_master_db_context() as master_db:
                from app.models.all_models import TenantSubscription, SubscriptionPlan
                from app.core.enums import SubscriptionStatus
                
                sub = (
                    master_db.query(TenantSubscription)
                    .join(SubscriptionPlan)
                    .filter(
                        TenantSubscription.tenant_id == tenant_id,
                        TenantSubscription.status == SubscriptionStatus.ACTIVE
                    )
                    .first()
                )
                
                if not sub or not sub.plan:
                    raise BadRequestError(message="Active subscription required to invite users.")
                    
                current_user_count = self.db.query(func.count(User.id)).filter(User.is_deleted == False).scalar() or 0
                if current_user_count >= sub.plan.max_users:
                    raise BadRequestError(
                        message=f"User limit reached. Your subscription plan allows a maximum of {sub.plan.max_users} users.",
                        detail={"max_users": sub.plan.max_users, "current_users": current_user_count}
                    )

        if payload.role_ids:
            roles = self.repository.get_roles_by_ids(payload.role_ids)
            found_ids = {r.id for r in roles}
            missing = sorted(set(payload.role_ids) - found_ids)
            if missing:
                raise NotFoundError(
                    message="One or more roles were not found.",
                    detail={"missing_role_ids": missing},
                )

        password_hash = get_password_hash(temp_password)
        user = self.repository.create_user(
            username=payload.username,
            email=str(payload.email).strip().lower(),
            phone_number=payload.phone_number,
            password_hash=password_hash,
            first_name=payload.first_name,
            last_name=payload.last_name,
            middle_name=payload.middle_name,
            is_superuser=False,
            is_email_verified=False,
            is_phone_verified=False,
            is_two_factor_enabled=False,
            status=UserStatus.INVITED,
        )

        if payload.role_ids:
            self.repository.assign_roles(user, payload.role_ids)

        record_security_event(
            self.db,
            user_id=user.id,
            event_type="USER_INVITED",
            severity="INFO",
            event_detail=f"User {user.username} invited by user {actor_user_id}.",
            event_metadata={"actor_user_id": actor_user_id, "role_ids": payload.role_ids},
        )

        # TODO: Trigger invitation email with temp_password
        logger.info(f"User {user.username} invited. Temporary Password: {temp_password}")

        self.db.commit()
        return self.repository.get_required_by_id(user.id)

    # ============================================================
    # UPDATE
    # ============================================================

    def update_user(
        self,
        user_id: int,
        payload: UserUpdateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> User:
        """
        Update mutable user profile fields.
        """
        user = self.repository.get_required_by_id(user_id)

        before = {
            "email": user.email,
            "phone_number": user.phone_number,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "middle_name": user.middle_name,
        }

        updated = self.repository.update_user(
            user,
            email=str(payload.email).strip().lower() if payload.email else None,
            phone_number=payload.phone_number,
            first_name=payload.first_name,
            last_name=payload.last_name,
            middle_name=payload.middle_name,
            is_email_verified=payload.is_email_verified,
            is_phone_verified=payload.is_phone_verified,
            is_two_factor_enabled=payload.is_two_factor_enabled,
        )

        record_security_event(
            self.db,
            user_id=updated.id,
            event_type="USER_PROFILE_UPDATED",
            severity="INFO",
            event_detail=f"User {updated.username} profile updated by user {actor_user_id}.",
            event_metadata={"actor_user_id": actor_user_id, "before": before},
        )

        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def update_user_status(
        self,
        user_id: int,
        payload: UserStatusUpdateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> User:
        """Alias of :meth:`update_status` for legacy callers."""
        return self.update_status(user_id, payload, actor_user_id=actor_user_id)

    def update_status(
        self,
        user_id: int,
        payload: UserStatusUpdateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> User:
        """
        Change a user's status. Revokes sessions if status moves away from ACTIVE.
        """
        user = self.repository.get_required_by_id(user_id)
        new_status = UserStatus(payload.status)
        previous_status = user.status

        updated = self.repository.update_status(user, new_status)

        if new_status != UserStatus.ACTIVE:
            self.repository.revoke_all_user_sessions(updated.id, when=datetime.now(timezone.utc))

        if new_status == UserStatus.ACTIVE:
            self.repository.reset_failed_login_attempts(updated)

        record_security_event(
            self.db,
            user_id=updated.id,
            event_type="USER_STATUS_CHANGED",
            severity="WARNING" if new_status != UserStatus.ACTIVE else "INFO",
            event_detail=(
                f"User {updated.username} status changed from {previous_status} to {new_status} "
                f"by user {actor_user_id}."
            ),
            event_metadata={
                "actor_user_id": actor_user_id,
                "previous_status": str(previous_status),
                "new_status": str(new_status),
                "reason": payload.reason,
            },
        )

        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def unlock_user(
        self,
        user_id: int,
        *,
        actor_user_id: Optional[int] = None,
    ) -> User:
        """
        Clear lockout state and reset failed login attempts.
        """
        user = self.repository.get_required_by_id(user_id)
        self.repository.reset_failed_login_attempts(user)

        if user.status == UserStatus.LOCKED:
            self.repository.update_status(user, UserStatus.ACTIVE)

        record_security_event(
            self.db,
            user_id=user.id,
            event_type="ACCOUNT_UNLOCKED",
            severity="WARNING",
            event_detail=f"Account unlocked for user {user.username} by user {actor_user_id}.",
            event_metadata={"actor_user_id": actor_user_id},
        )

        self.db.commit()
        return self.repository.get_required_by_id(user.id)

    def lock_user(
        self,
        user_id: int,
        *,
        reason: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> User:
        """
        Administratively lock a user account.

        This sets ``status = LOCKED`` and revokes any active sessions. The
        account stays locked until an administrator calls :meth:`unlock_user`.
        """
        user = self.repository.get_required_by_id(user_id)
        if actor_user_id is not None and actor_user_id == user.id:
            raise BadRequestError(message="You cannot lock your own account.")

        self.repository.update_status(user, UserStatus.LOCKED)
        self.repository.revoke_all_user_sessions(user.id, datetime.now(timezone.utc))

        record_security_event(
            self.db,
            user_id=user.id,
            event_type="ACCOUNT_LOCKED_BY_ADMIN",
            severity="CRITICAL",
            event_detail=f"User {user.username} locked by user {actor_user_id}.",
            event_metadata={"actor_user_id": actor_user_id, "reason": reason},
        )

        self.db.commit()
        return self.repository.get_required_by_id(user.id)

    def deactivate_user(
        self,
        user_id: int,
        *,
        reason: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> User:
        """
        Deactivate (suspend) a user without soft-deleting it.

        The user will not be able to log in until an admin reactivates them.
        """
        user = self.repository.get_required_by_id(user_id)
        if actor_user_id is not None and actor_user_id == user.id:
            raise BadRequestError(message="You cannot deactivate your own account.")

        self.repository.update_status(user, UserStatus.SUSPENDED)
        self.repository.revoke_all_user_sessions(user.id, datetime.now(timezone.utc))

        record_security_event(
            self.db,
            user_id=user.id,
            event_type="USER_DEACTIVATED",
            severity="WARNING",
            event_detail=f"User {user.username} deactivated by user {actor_user_id}.",
            event_metadata={"actor_user_id": actor_user_id, "reason": reason},
        )

        self.db.commit()
        return self.repository.get_required_by_id(user.id)

    def reactivate_user(
        self,
        user_id: int,
        *,
        actor_user_id: Optional[int] = None,
    ) -> User:
        """
        Re-enable a previously suspended/locked user.
        """
        user = self.repository.get_required_by_id(user_id)
        self.repository.update_status(user, UserStatus.ACTIVE)
        self.repository.reset_failed_login_attempts(user)

        record_security_event(
            self.db,
            user_id=user.id,
            event_type="USER_REACTIVATED",
            severity="INFO",
            event_detail=f"User {user.username} reactivated by user {actor_user_id}.",
            event_metadata={"actor_user_id": actor_user_id},
        )

        self.db.commit()
        return self.repository.get_required_by_id(user.id)

    # ============================================================
    # ROLES
    # ============================================================

    def assign_roles(
        self,
        user_id: int,
        payload: UserRoleAssignmentSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> User:
        """
        Assign roles to a user.
        """
        if not payload.role_ids:
            raise BadRequestError(message="At least one role ID must be supplied.")

        user = self.repository.get_required_by_id(user_id)
        roles = self.repository.get_roles_by_ids(payload.role_ids)
        found_ids = {r.id for r in roles}
        missing = sorted(set(payload.role_ids) - found_ids)
        if missing:
            raise NotFoundError(
                message="One or more roles were not found.",
                detail={"missing_role_ids": missing},
            )

        updated = self.repository.assign_roles(user, payload.role_ids)

        record_security_event(
            self.db,
            user_id=updated.id,
            event_type="ROLE_ASSIGNED",
            severity="WARNING",
            event_detail=f"Roles assigned to {updated.username} by user {actor_user_id}.",
            event_metadata={"actor_user_id": actor_user_id, "role_ids": payload.role_ids},
        )

        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def revoke_roles(
        self,
        user_id: int,
        payload: UserRoleAssignmentSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> User:
        """
        Detach roles from a user.
        """
        if not payload.role_ids:
            raise BadRequestError(message="At least one role ID must be supplied.")

        user = self.repository.get_required_by_id(user_id)
        updated = self.repository.revoke_roles(user, payload.role_ids)

        record_security_event(
            self.db,
            user_id=updated.id,
            event_type="ROLE_REVOKED",
            severity="WARNING",
            event_detail=f"Roles revoked from {updated.username} by user {actor_user_id}.",
            event_metadata={"actor_user_id": actor_user_id, "role_ids": payload.role_ids},
        )

        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    # ============================================================
    # PASSWORD / SESSIONS
    # ============================================================

    def force_password_reset(
        self,
        user_id: int,
        payload: UserPasswordResetSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> User:
        """
        Admin-driven password reset.
        """
        validate_password_strength(payload.new_password)

        user = self.repository.get_required_by_id(user_id)
        new_hash = get_password_hash(payload.new_password)

        # Insert into PasswordHistory before updating.
        from app.models.all_models import PasswordHistory

        if user.password_hash:
            history = PasswordHistory(
                user_id=user.id,
                password_hash=user.password_hash,
                changed_at=datetime.now(timezone.utc),
            )
            self.db.add(history)

        self.repository.update_password_hash(user, new_hash)
        self.repository.update_password_changed_at(user, datetime.now(timezone.utc))

        if payload.revoke_active_sessions:
            self.repository.revoke_all_user_sessions(user.id, datetime.now(timezone.utc))

        if payload.require_change_on_next_login:
            # Force password change on next login by clearing the changed-at marker
            # so that any password-age policy can recognize it as forced.
            user.password_changed_at = None
            self.db.add(user)
            self.db.flush()

        record_security_event(
            self.db,
            user_id=user.id,
            event_type="PASSWORD_RESET_BY_ADMIN",
            severity="WARNING",
            event_detail=f"Password reset for {user.username} by user {actor_user_id}.",
            event_metadata={
                "actor_user_id": actor_user_id,
                "revoked_sessions": payload.revoke_active_sessions,
                "require_change_on_next_login": payload.require_change_on_next_login,
            },
        )

        self.db.commit()
        return self.repository.get_required_by_id(user.id)

    def list_user_sessions(self, user_id: int) -> list:
        """
        List all sessions for a user.
        """
        self.repository.get_required_by_id(user_id)
        return self.repository.list_user_sessions(user_id)

    def revoke_all_sessions(
        self,
        user_id: int,
        *,
        actor_user_id: Optional[int] = None,
    ) -> int:
        """
        Revoke all active sessions for a user.
        """
        user = self.repository.get_required_by_id(user_id)
        count = self.repository.revoke_all_user_sessions(user.id, datetime.now(timezone.utc))

        record_security_event(
            self.db,
            user_id=user.id,
            event_type="SESSIONS_REVOKED",
            severity="WARNING",
            event_detail=f"All sessions revoked for {user.username} by user {actor_user_id}.",
            event_metadata={"actor_user_id": actor_user_id, "revoked_count": count},
        )

        self.db.commit()
        return count

    # ============================================================
    # SOFT DELETE
    # ============================================================

    def soft_delete_user(
        self,
        user_id: int,
        *,
        actor_user_id: Optional[int] = None,
    ) -> User:
        """
        Soft-delete (deactivate) a user. System rule: super admins cannot
        delete themselves and protected superusers cannot be deleted.
        """
        user = self.repository.get_required_by_id(user_id)

        if actor_user_id is not None and actor_user_id == user.id:
            raise BadRequestError(message="You cannot delete your own account.")

        if user.is_superuser:
            raise BadRequestError(
                message="Superuser accounts cannot be soft-deleted via this endpoint.",
            )

        deleted = self.repository.soft_delete(user)
        self.repository.revoke_all_user_sessions(deleted.id, datetime.now(timezone.utc))

        record_security_event(
            self.db,
            user_id=deleted.id,
            event_type="USER_DEACTIVATED",
            severity="WARNING",
            event_detail=f"User {deleted.username} deactivated by user {actor_user_id}.",
            event_metadata={"actor_user_id": actor_user_id},
        )

        self.db.commit()
        return deleted
