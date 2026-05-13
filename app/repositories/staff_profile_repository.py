from __future__ import annotations

"""
app.repositories.staff_profile_repository

Repository layer for staff profile onboarding, user administration,
role assignment, session management, and access-summary persistence logic.

Purpose
-------
This module centralizes direct database operations for workflows involving:

- staff profile creation and update
- user creation and update during staff onboarding
- detailed staff profile retrieval
- user role assignment and removal
- user session review and revocation
- effective permission loading for access administration

Design goals
------------
- keep raw database access out of route handlers
- keep business rules out of the repository layer
- provide reusable persistence helpers for the service layer
- support onboarding where user data and staff profile data are supplied
  together in one business payload

Important implementation note
-----------------------------
Even when the business flow treats staff profile capture as "first",
the actual database insert order must remain:

1. create User
2. flush to obtain user.id
3. create StaffProfile with user_id linked to the new user

This is required because `StaffProfile.user_id` is a non-nullable foreign key
to `User.id` in the current data model.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.all_models import (
    Department,
    Permission,
    Role,
    RolePermissionAssociation,
    ServiceDeliveryPoint,
    StaffProfile,
    StaffServiceDeliveryPointAssociation,
    User,
    UserRoleAssociation,
    UserSession,
)


class StaffProfileRepository:
    """
    Repository for staff profile onboarding, user administration,
    role assignment, session management, and effective permission loading.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize the repository with an active SQLAlchemy session.

        Args:
            db: Active SQLAlchemy session.
        """
        self.db = db

    # ============================================================
    # USER QUERIES
    # ============================================================

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Return a user by ID with related roles and staff profile eagerly loaded.

        Loaded relations
        ----------------
        - user_roles.role
        - staff_profile.department
        - staff_profile.service_delivery_point

        Args:
            user_id: User primary key.

        Returns:
            Optional[User]: Matching user or None.
        """
        return (
            self.db.query(User)
            .options(
                joinedload(User.user_roles).joinedload(UserRoleAssociation.role),
                joinedload(User.staff_profile).joinedload(StaffProfile.department),
                joinedload(User.staff_profile)
                .joinedload(StaffProfile.service_delivery_points)
                .joinedload(StaffServiceDeliveryPointAssociation.service_delivery_point),
            )
            .filter(User.id == user_id, User.is_deleted.is_(False))
            .first()
        )

    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Return a user by email address.

        Args:
            email: Email address.

        Returns:
            Optional[User]: Matching user or None.
        """
        return (
            self.db.query(User)
            .options(
                joinedload(User.staff_profile),
                joinedload(User.user_roles).joinedload(UserRoleAssociation.role),
            )
            .filter(User.email == email, User.is_deleted.is_(False))
            .first()
        )

    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Return a user by username.

        Args:
            username: Username.

        Returns:
            Optional[User]: Matching user or None.
        """
        return (
            self.db.query(User)
            .options(
                joinedload(User.staff_profile),
                joinedload(User.user_roles).joinedload(UserRoleAssociation.role),
            )
            .filter(User.username == username, User.is_deleted.is_(False))
            .first()
        )

    def list_users(self, *, skip: int = 0, limit: int = 20) -> tuple[list[dict], int]:
        """
        Return paginated user summaries including role count and staff profile data.

        Args:
            skip: Pagination offset.
            limit: Pagination limit.

        Returns:
            tuple[list[dict], int]:
                - list of user summary dictionaries
                - total count
        """
        total = (
            self.db.query(func.count(User.id))
            .filter(User.is_deleted.is_(False))
            .scalar()
            or 0
        )

        rows = (
            self.db.query(
                User,
                StaffProfile,
                func.count(func.distinct(UserRoleAssociation.role_id)).label("role_count"),
            )
            .outerjoin(StaffProfile, StaffProfile.user_id == User.id)
            .outerjoin(UserRoleAssociation, UserRoleAssociation.user_id == User.id)
            .filter(User.is_deleted.is_(False))
            .group_by(User.id, StaffProfile.id)
            .order_by(User.first_name.asc(), User.last_name.asc(), User.username.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        items: list[dict] = []
        for user, staff_profile, role_count in rows:
            items.append(
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "status": str(user.status),
                    "is_superuser": user.is_superuser,
                    "is_two_factor_enabled": user.is_two_factor_enabled,
                    "last_login_at": user.last_login_at,
                    "personal_phone": getattr(user, "personal_phone", None),
                    "role_count": int(role_count or 0),
                    "staff_no": staff_profile.staff_no if staff_profile else None,
                    "department_id": staff_profile.department_id if staff_profile else None,
                    "service_delivery_point_ids": [
                        link.service_delivery_point_id 
                        for link in (staff_profile.service_delivery_points or [])
                    ] if staff_profile else [],
                }
            )

        return items, int(total)

    def create_user(self, user: User) -> User:
        """
        Persist a new user.

        Args:
            user: User ORM instance.

        Returns:
            User: Persisted user.
        """
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def update_user(self, user: User) -> User:
        """
        Persist updates to an existing user.

        Args:
            user: User ORM instance.

        Returns:
            User: Updated user.
        """
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def soft_delete_user(self, user: User) -> User:
        """
        Soft-delete a user record.

        Args:
            user: User ORM instance.

        Returns:
            User: Soft-deleted user.
        """
        user.is_deleted = True
        self.db.add(user)
        self.db.flush()
        return user

    # ============================================================
    # DEPARTMENT / SERVICE POINT HELPERS
    # ============================================================

    def get_department_by_id(self, department_id: int) -> Optional[Department]:
        """
        Return a department by ID.

        Args:
            department_id: Department primary key.

        Returns:
            Optional[Department]: Matching department or None.
        """
        return (
            self.db.query(Department)
            .filter(Department.id == department_id, Department.is_deleted.is_(False))
            .first()
        )

    def get_service_delivery_point_by_id(
        self,
        service_delivery_point_id: int,
    ) -> Optional[ServiceDeliveryPoint]:
        """
        Return a service delivery point by ID.

        Args:
            service_delivery_point_id: Service delivery point primary key.

        Returns:
            Optional[ServiceDeliveryPoint]: Matching record or None.
        """
        return (
            self.db.query(ServiceDeliveryPoint)
            .filter(
                ServiceDeliveryPoint.id == service_delivery_point_id,
                ServiceDeliveryPoint.is_deleted.is_(False),
            )
            .first()
        )

    # ============================================================
    # STAFF PROFILE QUERIES
    # ============================================================

    def get_staff_profile_by_id(self, staff_profile_id: int) -> Optional[StaffProfile]:
        """
        Return a staff profile by ID.

        Args:
            staff_profile_id: Staff profile primary key.

        Returns:
            Optional[StaffProfile]: Matching staff profile or None.
        """
        return (
            self.db.query(StaffProfile)
            .filter(StaffProfile.id == staff_profile_id, StaffProfile.is_deleted.is_(False))
            .first()
        )

    def get_staff_profile_by_user_id(self, user_id: int) -> Optional[StaffProfile]:
        """
        Return a staff profile for a given user.

        Args:
            user_id: User primary key.

        Returns:
            Optional[StaffProfile]: Matching staff profile or None.
        """
        return (
            self.db.query(StaffProfile)
            .filter(StaffProfile.user_id == user_id, StaffProfile.is_deleted.is_(False))
            .first()
        )

    def get_staff_profile_by_staff_no(self, staff_no: str) -> Optional[StaffProfile]:
        """
        Return a staff profile by unique staff number.

        Args:
            staff_no: Unique staff number.

        Returns:
            Optional[StaffProfile]: Matching staff profile or None.
        """
        return (
            self.db.query(StaffProfile)
            .filter(StaffProfile.staff_no == staff_no, StaffProfile.is_deleted.is_(False))
            .first()
        )

    def get_staff_profile_by_license_no(
        self,
        professional_license_no: str,
    ) -> Optional[StaffProfile]:
        """
        Return a staff profile by professional license number.

        Args:
            professional_license_no: Professional license number.

        Returns:
            Optional[StaffProfile]: Matching staff profile or None.
        """
        return (
            self.db.query(StaffProfile)
            .filter(
                StaffProfile.professional_license_no == professional_license_no,
                StaffProfile.is_deleted.is_(False),
            )
            .first()
        )

    def get_detailed_staff_profile_by_id(self, staff_profile_id: int) -> Optional[StaffProfile]:
        """
        Return a fully detailed staff profile record.

        Loaded relations
        ----------------
        - user
        - user's assigned roles
        - department
        - service delivery point

        Args:
            staff_profile_id: Staff profile primary key.

        Returns:
            Optional[StaffProfile]: Detailed staff profile or None.
        """
        return (
            self.db.query(StaffProfile)
            .options(
                joinedload(StaffProfile.user)
                .joinedload(User.user_roles)
                .joinedload(UserRoleAssociation.role),
                joinedload(StaffProfile.department),
                joinedload(StaffProfile.service_delivery_points)
                .joinedload(StaffServiceDeliveryPointAssociation.service_delivery_point),
            )
            .filter(
                StaffProfile.id == staff_profile_id,
                StaffProfile.is_deleted.is_(False),
            )
            .first()
        )

    def get_detailed_staff_profile_by_user_id(self, user_id: int) -> Optional[StaffProfile]:
        """
        Return a fully detailed staff profile using the linked user ID.

        Loaded relations
        ----------------
        - user
        - user's assigned roles
        - department
        - service delivery point

        Args:
            user_id: User primary key.

        Returns:
            Optional[StaffProfile]: Detailed staff profile or None.
        """
        return (
            self.db.query(StaffProfile)
            .options(
                joinedload(StaffProfile.user)
                .joinedload(User.user_roles)
                .joinedload(UserRoleAssociation.role),
                joinedload(StaffProfile.department),
                joinedload(StaffProfile.service_delivery_points)
                .joinedload(StaffServiceDeliveryPointAssociation.service_delivery_point),
            )
            .filter(
                StaffProfile.user_id == user_id,
                StaffProfile.is_deleted.is_(False),
            )
            .first()
        )

    def list_staff_profiles(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[StaffProfile], int]:
        """
        Return paginated staff profiles with related user, department,
        service delivery point, and roles.

        Args:
            skip: Pagination offset.
            limit: Pagination limit.

        Returns:
            tuple[list[StaffProfile], int]:
                - staff profile rows
                - total count
        """
        total = (
            self.db.query(func.count(StaffProfile.id))
            .filter(StaffProfile.is_deleted.is_(False))
            .scalar()
            or 0
        )

        items = (
            self.db.query(StaffProfile)
            .options(
                joinedload(StaffProfile.user)
                .joinedload(User.user_roles)
                .joinedload(UserRoleAssociation.role),
                joinedload(StaffProfile.department),
                joinedload(StaffProfile.service_delivery_points)
                .joinedload(StaffServiceDeliveryPointAssociation.service_delivery_point),
            )
            .filter(StaffProfile.is_deleted.is_(False))
            .order_by(StaffProfile.staff_no.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return items, int(total)

    def list_staff_by_sdp_id(
        self,
        sdp_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[StaffProfile], int]:
        """
        Return paginated staff profiles assigned to a specific service delivery point.
        """
        query = (
            self.db.query(StaffProfile)
            .join(StaffServiceDeliveryPointAssociation)
            .options(
                joinedload(StaffProfile.user),
                joinedload(StaffProfile.department),
            )
            .filter(
                StaffServiceDeliveryPointAssociation.service_delivery_point_id == sdp_id,
                StaffProfile.is_deleted.is_(False),
            )
        )

        total = query.with_entities(func.count(StaffProfile.id)).scalar() or 0
        items = (
            query.order_by(StaffProfile.staff_no.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def assign_multiple_to_sdp(self, staff_profile_ids: list[int], sdp_id: int) -> int:
        """
        Bulk assign staff profiles to a service delivery point (adding them).
        """
        if not staff_profile_ids or sdp_id is None:
            return 0

        # Find existing assignments to avoid duplicates
        existing = (
            self.db.query(StaffServiceDeliveryPointAssociation)
            .filter(
                StaffServiceDeliveryPointAssociation.service_delivery_point_id == sdp_id,
                StaffServiceDeliveryPointAssociation.staff_profile_id.in_(staff_profile_ids)
            )
            .all()
        )
        existing_staff_ids = {link.staff_profile_id for link in existing}

        added_count = 0
        for staff_id in staff_profile_ids:
            if staff_id not in existing_staff_ids:
                self.db.add(
                    StaffServiceDeliveryPointAssociation(
                        staff_profile_id=staff_id,
                        service_delivery_point_id=sdp_id
                    )
                )
                added_count += 1
        
        self.db.flush()
        return added_count

    def replace_sdp_assignments(self, staff_profile_id: int, sdp_ids: list[int]) -> None:
        """
        Replace all SDP assignments for a staff member.
        """
        # Remove existing
        (
            self.db.query(StaffServiceDeliveryPointAssociation)
            .filter(StaffServiceDeliveryPointAssociation.staff_profile_id == staff_profile_id)
            .delete(synchronize_session=False)
        )

        # Add new
        for sdp_id in sdp_ids:
            self.db.add(
                StaffServiceDeliveryPointAssociation(
                    staff_profile_id=staff_profile_id,
                    service_delivery_point_id=sdp_id
                )
            )
        self.db.flush()

    def remove_multiple_from_sdp(self, staff_profile_ids: list[int], sdp_id: int) -> int:
        """
        Remove multiple staff profiles from a specific service delivery point.
        """
        if not staff_profile_ids:
            return 0
        
        count = (
            self.db.query(StaffServiceDeliveryPointAssociation)
            .filter(
                StaffServiceDeliveryPointAssociation.service_delivery_point_id == sdp_id,
                StaffServiceDeliveryPointAssociation.staff_profile_id.in_(staff_profile_ids)
            )
            .delete(synchronize_session=False)
        )
        self.db.flush()
        return count

    def create_staff_profile(self, staff_profile: StaffProfile) -> StaffProfile:
        """
        Persist a new staff profile.

        Args:
            staff_profile: StaffProfile ORM instance.

        Returns:
            StaffProfile: Persisted staff profile.
        """
        self.db.add(staff_profile)
        self.db.flush()
        self.db.refresh(staff_profile)
        return staff_profile

    def update_staff_profile(self, staff_profile: StaffProfile) -> StaffProfile:
        """
        Persist updates to an existing staff profile.

        Args:
            staff_profile: StaffProfile ORM instance.

        Returns:
            StaffProfile: Updated staff profile.
        """
        self.db.add(staff_profile)
        self.db.flush()
        self.db.refresh(staff_profile)
        return staff_profile

    def soft_delete_staff_profile(self, staff_profile: StaffProfile) -> StaffProfile:
        """
        Soft-delete a staff profile record.

        Args:
            staff_profile: StaffProfile ORM instance.

        Returns:
            StaffProfile: Soft-deleted staff profile.
        """
        staff_profile.is_deleted = True
        self.db.add(staff_profile)
        self.db.flush()
        return staff_profile

    def create_user_with_staff_profile(
        self,
        *,
        user: User,
        staff_profile: StaffProfile,
    ) -> User:
        """
        Create a user and then create the linked staff profile in a single unit of work.

        Notes
        -----
        Because `StaffProfile.user_id` depends on `User.id`, the repository must:
        1. create the user
        2. flush to obtain the user ID
        3. attach the user ID to the staff profile
        4. create the staff profile

        Args:
            user: User ORM instance.
            staff_profile: StaffProfile ORM instance without user_id assigned yet.

        Returns:
            User: Newly created user with staff profile relationship available.
        """
        # Persist the user first so the database assigns the primary key.
        self.db.add(user)
        self.db.flush()

        # Link the staff profile to the new user.
        staff_profile.user_id = user.id

        # Persist the staff profile after the user ID exists.
        self.db.add(staff_profile)
        self.db.flush()

        # Refresh the user object so relationship state is available immediately.
        self.db.refresh(user)
        return self.get_user_by_id(user.id)

    def update_user_and_staff_profile(
        self,
        *,
        user: User,
        staff_profile: Optional[StaffProfile] = None,
    ) -> User:
        """
        Persist updates to a user and optionally an associated staff profile.

        Args:
            user: User ORM instance.
            staff_profile: Optional StaffProfile ORM instance.

        Returns:
            User: Refreshed user with staff profile and roles loaded.
        """
        self.db.add(user)

        if staff_profile is not None:
            self.db.add(staff_profile)

        self.db.flush()
        self.db.refresh(user)
        return self.get_user_by_id(user.id)

    # ============================================================
    # ROLE QUERIES / ASSIGNMENT
    # ============================================================

    def get_roles_by_ids(self, role_ids: list[int]) -> list[Role]:
        """
        Return roles matching the supplied role IDs.

        Args:
            role_ids: Role primary keys.

        Returns:
            list[Role]: Matching roles.
        """
        if not role_ids:
            return []

        return (
            self.db.query(Role)
            .filter(Role.id.in_(role_ids), Role.is_deleted.is_(False))
            .all()
        )

    def assign_roles(self, user: User, role_ids: list[int]) -> User:
        """
        Assign roles to a user while preserving existing assignments.

        Args:
            user: Target user.
            role_ids: Role IDs to assign.

        Returns:
            User: Refreshed user.
        """
        existing_role_ids = {link.role_id for link in user.user_roles or []}

        for role_id in role_ids:
            if role_id in existing_role_ids:
                continue

            self.db.add(
                UserRoleAssociation(
                    user_id=user.id,
                    role_id=role_id,
                )
            )

        self.db.flush()
        return self.get_user_by_id(user.id)

    def replace_roles(self, user: User, role_ids: list[int]) -> User:
        """
        Replace all current role assignments for a user.

        Args:
            user: Target user.
            role_ids: Final role IDs for the user.

        Returns:
            User: Refreshed user.
        """
        (
            self.db.query(UserRoleAssociation)
            .filter(UserRoleAssociation.user_id == user.id)
            .delete(synchronize_session=False)
        )

        for role_id in role_ids:
            self.db.add(
                UserRoleAssociation(
                    user_id=user.id,
                    role_id=role_id,
                )
            )

        self.db.flush()
        return self.get_user_by_id(user.id)

    def remove_roles(self, user: User, role_ids: list[int]) -> User:
        """
        Remove selected roles from a user.

        Args:
            user: Target user.
            role_ids: Role IDs to remove.

        Returns:
            User: Refreshed user.
        """
        if role_ids:
            (
                self.db.query(UserRoleAssociation)
                .filter(
                    UserRoleAssociation.user_id == user.id,
                    UserRoleAssociation.role_id.in_(role_ids),
                )
                .delete(synchronize_session=False)
            )

        self.db.flush()
        return self.get_user_by_id(user.id)

    # ============================================================
    # SESSIONS / LOGIN HISTORY
    # ============================================================

    def list_user_sessions(
        self,
        user_id: int,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[UserSession], int]:
        """
        Return paginated session/login history for a user.

        Args:
            user_id: User primary key.
            skip: Pagination offset.
            limit: Pagination limit.

        Returns:
            tuple[list[UserSession], int]:
                - session rows
                - total count
        """
        total = (
            self.db.query(func.count(UserSession.id))
            .filter(
                UserSession.user_id == user_id,
                UserSession.is_deleted.is_(False),
            )
            .scalar()
            or 0
        )

        items = (
            self.db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.is_deleted.is_(False),
            )
            .order_by(UserSession.login_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return items, int(total)

    def get_sessions_by_ids(self, user_id: int, session_ids: list[int]) -> list[UserSession]:
        """
        Return specific session rows for a user.

        Args:
            user_id: User primary key.
            session_ids: Session primary keys.

        Returns:
            list[UserSession]: Matching sessions.
        """
        if not session_ids:
            return []

        return (
            self.db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.id.in_(session_ids),
                UserSession.is_deleted.is_(False),
            )
            .all()
        )

    def revoke_sessions(self, sessions: list[UserSession]) -> None:
        """
        Revoke the supplied sessions.

        Args:
            sessions: Session rows to revoke.
        """
        now = datetime.now(timezone.utc)

        for session in sessions:
            session.revoked_at = now
            session.is_current = False
            self.db.add(session)

        self.db.flush()

    def revoke_all_other_sessions(
        self,
        user_id: int,
        keep_session_jti: Optional[str] = None,
    ) -> int:
        """
        Revoke all active sessions for a user except an optional current session.

        Args:
            user_id: User primary key.
            keep_session_jti: Optional session JTI to preserve.

        Returns:
            int: Number of revoked sessions.
        """
        query = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_deleted.is_(False),
            UserSession.revoked_at.is_(None),
            UserSession.is_current.is_(True),
        )

        if keep_session_jti:
            query = query.filter(UserSession.session_token_jti != keep_session_jti)

        sessions = query.all()
        self.revoke_sessions(sessions)
        return len(sessions)

    # ============================================================
    # EFFECTIVE PERMISSIONS
    # ============================================================

    def get_effective_permissions_for_user(self, user_id: int) -> list[Permission]:
        """
        Return deduplicated effective permissions for a user based on assigned roles.

        Args:
            user_id: User primary key.

        Returns:
            list[Permission]: Effective permissions.
        """
        return (
            self.db.query(Permission)
            .join(
                RolePermissionAssociation,
                RolePermissionAssociation.permission_id == Permission.id,
            )
            .join(
                UserRoleAssociation,
                UserRoleAssociation.role_id == RolePermissionAssociation.role_id,
            )
            .filter(
                UserRoleAssociation.user_id == user_id,
                Permission.is_deleted.is_(False),
            )
            .distinct(Permission.id)
            .order_by(Permission.module.asc(), Permission.code.asc())
            .all()
        )