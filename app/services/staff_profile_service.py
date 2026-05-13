from __future__ import annotations

"""
app.services.staff_profile_service

Service layer for staff onboarding, user administration, staff profile
management, role assignment, session control, and access summary.

Purpose
-------
This module implements business logic for:

- creating users together with staff profiles
- updating users and linked staff profiles
- activating and deactivating accounts
- assigning/replacing/removing roles
- password reset and password change
- MFA enable/disable
- reviewing staff profile details
- reviewing user session / login history
- revoking sessions
- retrieving effective access summaries

Design goals
------------
- keep repositories focused on persistence
- centralize business validation in the service layer
- provide a reusable orchestration layer for route handlers
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import UserStatus
from app.core.exceptions import (
    AlreadyExistsError,
    BadRequestError,
    NotFoundError,
    UnauthorizedError,
)
from app.core.security import verify_user_password
from app.models.all_models import StaffProfile, User
from app.repositories.staff_profile_repository import StaffProfileRepository
from app.schemas.staff_profile_schemas import (
    MFAToggleSchema,
    PasswordChangeSchema,
    PasswordResetSchema,
    RoleAssignmentSchema,
    StaffProfileUpdateSchema,
    UserCreateSchema,
    UserUpdateSchema,
)
from app.utils.password_utils import hash_password, validate_password_strength


class StaffProfileService:
    """
    Service layer for staff onboarding and access administration workflows.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize the service with an active SQLAlchemy session.

        Args:
            db: Active SQLAlchemy session.
        """
        self.db = db
        self.repository = StaffProfileRepository(db)

    # ============================================================
    # USER / STAFF PROFILE CREATE
    # ============================================================

    def create_user_with_staff_profile(self, payload: UserCreateSchema) -> User:
        """
        Create a user account and linked staff profile in one onboarding flow.

        Validation performed
        --------------------
        - email uniqueness
        - username uniqueness
        - staff number uniqueness
        - optional professional license uniqueness
        - department existence
        - service delivery point existence
        - role existence
        - password policy validation

        Args:
            payload: User creation payload with nested staff profile data.

        Returns:
            User: Newly created user with related staff profile and roles loaded.
        """
        # --------------------------------------------------------
        # Validate user uniqueness
        # --------------------------------------------------------
        if self.repository.get_user_by_email(str(payload.email)):
            raise AlreadyExistsError(
                message="A user with this email already exists.",
                detail={"email": str(payload.email)},
            )

        if self.repository.get_user_by_username(payload.username):
            raise AlreadyExistsError(
                message="A user with this username already exists.",
                detail={"username": payload.username},
            )

        # --------------------------------------------------------
        # Validate staff profile uniqueness
        # --------------------------------------------------------
        existing_staff_no = self.repository.get_staff_profile_by_staff_no(
            payload.staff_profile.staff_no
        )
        if existing_staff_no:
            raise AlreadyExistsError(
                message="A staff profile with this staff number already exists.",
                detail={"staff_no": payload.staff_profile.staff_no},
            )

        if payload.staff_profile.professional_license_no:
            existing_license = self.repository.get_staff_profile_by_license_no(
                payload.staff_profile.professional_license_no
            )
            if existing_license:
                raise AlreadyExistsError(
                    message="A staff profile with this professional license number already exists.",
                    detail={
                        "professional_license_no": payload.staff_profile.professional_license_no
                    },
                )

        # --------------------------------------------------------
        # Validate supporting foreign keys
        # --------------------------------------------------------
        self._validate_department_exists(payload.staff_profile.department_id)
        self._validate_service_delivery_point_exists(
            payload.staff_profile.service_delivery_point_id
        )

        # --------------------------------------------------------
        # Validate roles and password policy
        # --------------------------------------------------------
        self._validate_roles_exist(payload.role_ids)
        validate_password_strength(payload.password)

        # --------------------------------------------------------
        # Build ORM objects
        # --------------------------------------------------------
        user = User(
            username=payload.username,
            email=str(payload.email),
            phone_number=payload.phone_number,
            password_hash=hash_password(payload.password),
            first_name=payload.first_name,
            last_name=payload.last_name,
            middle_name=payload.middle_name,
            status=UserStatus.ACTIVE,
            is_superuser=payload.is_superuser,
            is_email_verified=payload.is_email_verified,
            is_phone_verified=payload.is_phone_verified,
            is_two_factor_enabled=payload.is_two_factor_enabled,
        )

        staff_profile = StaffProfile(
            department_id=payload.staff_profile.department_id,
            service_delivery_point_id=payload.staff_profile.service_delivery_point_id,
            staff_no=payload.staff_profile.staff_no,
            job_title=payload.staff_profile.job_title,
            professional_license_no=payload.staff_profile.professional_license_no,
            specialty=payload.staff_profile.specialty,
        )

        # --------------------------------------------------------
        # Persist user + staff profile
        # --------------------------------------------------------
        created_user = self.repository.create_user_with_staff_profile(
            user=user,
            staff_profile=staff_profile,
        )

        # --------------------------------------------------------
        # Assign roles if provided
        # --------------------------------------------------------
        if payload.role_ids:
            created_user = self.repository.assign_roles(created_user, payload.role_ids)

        self.db.commit()
        return self.get_user(created_user.id)

    # ============================================================
    # USER / STAFF PROFILE UPDATE
    # ============================================================

    def update_user_and_staff_profile(self, user_id: int, payload: UserUpdateSchema) -> User:
        """
        Update a user account and optionally update its linked staff profile.

        Args:
            user_id: User primary key.
            payload: User update payload, optionally containing staff profile updates.

        Returns:
            User: Updated user with related data loaded.
        """
        user = self.get_user(user_id)
        staff_profile = self.repository.get_staff_profile_by_user_id(user_id)

        # --------------------------------------------------------
        # Validate uniqueness for email / username
        # --------------------------------------------------------
        if payload.email and str(payload.email) != user.email:
            existing = self.repository.get_user_by_email(str(payload.email))
            if existing and existing.id != user.id:
                raise AlreadyExistsError(
                    message="A user with this email already exists.",
                    detail={"email": str(payload.email)},
                )

        if payload.username and payload.username != user.username:
            existing = self.repository.get_user_by_username(payload.username)
            if existing and existing.id != user.id:
                raise AlreadyExistsError(
                    message="A user with this username already exists.",
                    detail={"username": payload.username},
                )

        # --------------------------------------------------------
        # Apply user changes
        # --------------------------------------------------------
        if payload.username is not None:
            user.username = payload.username
        if payload.email is not None:
            user.email = str(payload.email)
        if payload.phone_number is not None:
            user.phone_number = payload.phone_number
        if payload.first_name is not None:
            user.first_name = payload.first_name
        if payload.last_name is not None:
            user.last_name = payload.last_name
        if payload.middle_name is not None:
            user.middle_name = payload.middle_name
        if payload.is_superuser is not None:
            user.is_superuser = payload.is_superuser
        if payload.is_two_factor_enabled is not None:
            user.is_two_factor_enabled = payload.is_two_factor_enabled
        if payload.is_email_verified is not None:
            user.is_email_verified = payload.is_email_verified
        if payload.is_phone_verified is not None:
            user.is_phone_verified = payload.is_phone_verified

        if payload.status is not None:
            try:
                user.status = UserStatus[payload.status]
            except KeyError as exc:
                raise BadRequestError(
                    message="Invalid user status.",
                    detail={"status": payload.status},
                ) from exc

        # --------------------------------------------------------
        # Apply optional staff profile changes
        # --------------------------------------------------------
        if payload.staff_profile is not None:
            staff_profile = self._upsert_staff_profile_for_user(
                user=user,
                existing_staff_profile=staff_profile,
                payload=payload.staff_profile,
            )

        self.repository.update_user_and_staff_profile(
            user=user,
            staff_profile=staff_profile,
        )
        self.db.commit()
        return self.get_user(user.id)

    def _upsert_staff_profile_for_user(
        self,
        *,
        user: User,
        existing_staff_profile: Optional[StaffProfile],
        payload: StaffProfileUpdateSchema,
    ) -> StaffProfile:
        """
        Update an existing linked staff profile or create one if missing.

        Args:
            user: Target user.
            existing_staff_profile: Existing staff profile, if any.
            payload: Staff profile update payload.

        Returns:
            StaffProfile: Updated or newly created staff profile.
        """
        staff_profile = existing_staff_profile

        # --------------------------------------------------------
        # If the user does not already have a staff profile, create one.
        # A staff number is mandatory in that case.
        # --------------------------------------------------------
        if staff_profile is None:
            if not payload.staff_no:
                raise BadRequestError(
                    message="staff_no is required when creating a missing staff profile for a user."
                )

            self._validate_department_exists(payload.department_id)
            if payload.service_delivery_point_ids:
                for sdp_id in payload.service_delivery_point_ids:
                    self._validate_service_delivery_point_exists(sdp_id)

            existing_staff_no = self.repository.get_staff_profile_by_staff_no(payload.staff_no)
            if existing_staff_no:
                raise AlreadyExistsError(
                    message="A staff profile with this staff number already exists.",
                    detail={"staff_no": payload.staff_no},
                )

            if payload.professional_license_no:
                existing_license = self.repository.get_staff_profile_by_license_no(
                    payload.professional_license_no
                )
                if existing_license:
                    raise AlreadyExistsError(
                        message="A staff profile with this professional license number already exists.",
                        detail={"professional_license_no": payload.professional_license_no},
                    )

            staff_profile = StaffProfile(
                user_id=user.id,
                department_id=payload.department_id,
                staff_no=payload.staff_no,
                job_title=payload.job_title,
                professional_license_no=payload.professional_license_no,
                specialty=payload.specialty,
            )
            self.repository.create_staff_profile(staff_profile)

            if payload.service_delivery_point_ids:
                self.repository.replace_sdp_assignments(staff_profile.id, payload.service_delivery_point_ids)

            return staff_profile

        # --------------------------------------------------------
        # Validate uniqueness for mutable staff profile fields
        # --------------------------------------------------------
        if payload.staff_no and payload.staff_no != staff_profile.staff_no:
            existing_staff_no = self.repository.get_staff_profile_by_staff_no(payload.staff_no)
            if existing_staff_no and existing_staff_no.id != staff_profile.id:
                raise AlreadyExistsError(
                    message="A staff profile with this staff number already exists.",
                    detail={"staff_no": payload.staff_no},
                )

        if (
            payload.professional_license_no
            and payload.professional_license_no != staff_profile.professional_license_no
        ):
            existing_license = self.repository.get_staff_profile_by_license_no(
                payload.professional_license_no
            )
            if existing_license and existing_license.id != staff_profile.id:
                raise AlreadyExistsError(
                    message="A staff profile with this professional license number already exists.",
                    detail={"professional_license_no": payload.professional_license_no},
                )

        # --------------------------------------------------------
        # Validate supporting foreign keys
        # --------------------------------------------------------
        self._validate_department_exists(payload.department_id)
        self._validate_service_delivery_point_exists(payload.service_delivery_point_id)

        # --------------------------------------------------------
        # Apply changes
        # --------------------------------------------------------
        if payload.department_id is not None:
            staff_profile.department_id = payload.department_id
        if payload.service_delivery_point_ids is not None:
            self.repository.replace_sdp_assignments(staff_profile.id, payload.service_delivery_point_ids)
        if payload.staff_no is not None:
            staff_profile.staff_no = payload.staff_no
        if payload.job_title is not None:
            staff_profile.job_title = payload.job_title
        if payload.professional_license_no is not None:
            staff_profile.professional_license_no = payload.professional_license_no
        if payload.specialty is not None:
            staff_profile.specialty = payload.specialty

        self.repository.update_staff_profile(staff_profile)
        return staff_profile

    # ============================================================
    # USER QUERIES
    # ============================================================

    def get_user(self, user_id: int) -> User:
        """
        Return a user by ID or raise NotFoundError.

        Args:
            user_id: User primary key.

        Returns:
            User: Matching user.
        """
        user = self.repository.get_user_by_id(user_id)
        if not user:
            raise NotFoundError(
                message="User not found.",
                detail={"user_id": user_id},
            )
        return user

    def list_users(self, *, skip: int = 0, limit: int = 20):
        """
        Return paginated user summaries.

        Args:
            skip: Pagination offset.
            limit: Pagination limit.

        Returns:
            tuple[list[dict], int]: User summary rows and total count.
        """
        return self.repository.list_users(skip=skip, limit=limit)

    # ============================================================
    # STAFF PROFILE QUERIES
    # ============================================================

    def get_staff_profile(self, staff_profile_id: int) -> StaffProfile:
        """
        Return a staff profile by ID or raise NotFoundError.

        Args:
            staff_profile_id: Staff profile primary key.

        Returns:
            StaffProfile: Matching staff profile.
        """
        staff_profile = self.repository.get_staff_profile_by_id(staff_profile_id)
        if not staff_profile:
            raise NotFoundError(
                message="Staff profile not found.",
                detail={"staff_profile_id": staff_profile_id},
            )
        return staff_profile

    def get_detailed_staff_profile_by_id(self, staff_profile_id: int) -> StaffProfile:
        """
        Return a detailed staff profile including linked user, roles,
        department, and service delivery point.

        Args:
            staff_profile_id: Staff profile primary key.

        Returns:
            StaffProfile: Detailed staff profile.
        """
        staff_profile = self.repository.get_detailed_staff_profile_by_id(staff_profile_id)
        if not staff_profile:
            raise NotFoundError(
                message="Detailed staff profile not found.",
                detail={"staff_profile_id": staff_profile_id},
            )
        return staff_profile

    def get_detailed_staff_profile_by_user_id(self, user_id: int) -> StaffProfile:
        """
        Return a detailed staff profile using the linked user ID.

        Args:
            user_id: User primary key.

        Returns:
            StaffProfile: Detailed staff profile.
        """
        staff_profile = self.repository.get_detailed_staff_profile_by_user_id(user_id)
        if not staff_profile:
            raise NotFoundError(
                message="Detailed staff profile not found for the supplied user.",
                detail={"user_id": user_id},
            )
        return staff_profile

    def list_staff_profiles(self, *, skip: int = 0, limit: int = 20):
        """
        Return paginated detailed staff profiles.

        Args:
            skip: Pagination offset.
            limit: Pagination limit.

        Returns:
            tuple[list[StaffProfile], int]: Staff profile rows and total count.
        """
        return self.repository.list_staff_profiles(skip=skip, limit=limit)

    def list_staff_by_sdp(self, sdp_id: int, *, skip: int = 0, limit: int = 100):
        """
        Return paginated staff profiles assigned to a specific service delivery point.
        """
        # Validate that the SDP exists first
        self._validate_service_delivery_point_exists(sdp_id)
        return self.repository.list_staff_by_sdp_id(sdp_id, skip=skip, limit=limit)

    def assign_staff_to_sdp(self, staff_profile_ids: list[int], sdp_id: int) -> int:
        """
        Assign multiple staff profiles to a service delivery point.
        """
        if sdp_id is not None:
            self._validate_service_delivery_point_exists(sdp_id)

        # Validate that all staff profiles exist
        profiles = self.repository.db.query(StaffProfile).filter(
            StaffProfile.id.in_(staff_profile_ids),
            StaffProfile.is_deleted.is_(False)
        ).all()
        
        found_ids = {p.id for p in profiles}
        missing_ids = set(staff_profile_ids) - found_ids
        
        if missing_ids:
            raise NotFoundError(
                message="One or more staff profiles were not found.",
                detail={"missing_staff_profile_ids": list(missing_ids)}
            )

        count = self.repository.assign_multiple_to_sdp(staff_profile_ids, sdp_id)
        self.db.commit()
        return count

    def unassign_staff_from_sdp(self, sdp_id: int, staff_profile_ids: list[int]) -> int:
        """
        Remove staff profiles from a service delivery point.
        """
        self._validate_service_delivery_point_exists(sdp_id)
        count = self.repository.remove_multiple_from_sdp(staff_profile_ids, sdp_id)
        self.db.commit()
        return count

    def soft_delete_staff_profile(self, staff_profile_id: int) -> StaffProfile:
        """
        Soft-delete a staff profile.

        Args:
            staff_profile_id: Staff profile primary key.

        Returns:
            StaffProfile: Soft-deleted staff profile.
        """
        staff_profile = self.get_staff_profile(staff_profile_id)
        deleted = self.repository.soft_delete_staff_profile(staff_profile)
        self.db.commit()
        return deleted

    # ============================================================
    # ACCOUNT ACTIVATION / DEACTIVATION
    # ============================================================

    def activate_user(self, user_id: int) -> User:
        """
        Activate a user account.

        Args:
            user_id: User primary key.

        Returns:
            User: Activated user.
        """
        user = self.get_user(user_id)
        user.status = UserStatus.ACTIVE

        self.repository.update_user(user)
        self.db.commit()
        return self.get_user(user.id)

    def deactivate_user(self, user_id: int) -> User:
        """
        Deactivate a user account and revoke all active sessions.

        Args:
            user_id: User primary key.

        Returns:
            User: Deactivated user.
        """
        user = self.get_user(user_id)
        user.status = UserStatus.INACTIVE

        self.repository.update_user(user)
        self.repository.revoke_all_other_sessions(user.id)
        self.db.commit()
        return self.get_user(user.id)

    # ============================================================
    # ROLE ASSIGNMENT
    # ============================================================

    def assign_roles(self, user_id: int, payload: RoleAssignmentSchema) -> User:
        """
        Assign one or more roles to a user.

        Args:
            user_id: User primary key.
            payload: Role assignment payload.

        Returns:
            User: Updated user.
        """
        user = self.get_user(user_id)
        self._validate_roles_exist(payload.role_ids)

        updated = self.repository.assign_roles(user, payload.role_ids)
        self.db.commit()
        return self.get_user(updated.id)

    def replace_roles(self, user_id: int, payload: RoleAssignmentSchema) -> User:
        """
        Replace all user roles with the supplied role set.

        Args:
            user_id: User primary key.
            payload: Role assignment payload.

        Returns:
            User: Updated user.
        """
        user = self.get_user(user_id)
        self._validate_roles_exist(payload.role_ids)

        updated = self.repository.replace_roles(user, payload.role_ids)
        self.db.commit()
        return self.get_user(updated.id)

    def remove_roles(self, user_id: int, payload: RoleAssignmentSchema) -> User:
        """
        Remove selected roles from a user.

        Args:
            user_id: User primary key.
            payload: Role assignment payload.

        Returns:
            User: Updated user.
        """
        user = self.get_user(user_id)
        updated = self.repository.remove_roles(user, payload.role_ids)
        self.db.commit()
        return self.get_user(updated.id)

    # ============================================================
    # PASSWORD / MFA
    # ============================================================

    def admin_reset_password(self, user_id: int, payload: PasswordResetSchema) -> User:
        """
        Reset a user's password as an administrator.

        Notes
        -----
        All active sessions are revoked after reset.

        Args:
            user_id: User primary key.
            payload: Password reset payload.

        Returns:
            User: Updated user.
        """
        user = self.get_user(user_id)
        validate_password_strength(payload.new_password)

        user.password_hash = hash_password(payload.new_password)
        user.password_changed_at = datetime.now(timezone.utc)

        self.repository.update_user(user)
        self.repository.revoke_all_other_sessions(user.id)
        self.db.commit()
        return self.get_user(user.id)

    def change_own_password(self, current_user_id: int, payload: PasswordChangeSchema) -> User:
        """
        Change the current authenticated user's password.

        Args:
            current_user_id: Current authenticated user ID.
            payload: Password change payload.

        Returns:
            User: Updated user.
        """
        user = self.get_user(current_user_id)

        if not verify_user_password(payload.current_password, user.password_hash):
            raise UnauthorizedError(message="Current password is incorrect.")

        validate_password_strength(payload.new_password)

        user.password_hash = hash_password(payload.new_password)
        user.password_changed_at = datetime.now(timezone.utc)

        self.repository.update_user(user)
        self.repository.revoke_all_other_sessions(user.id)
        self.db.commit()
        return self.get_user(user.id)

    def toggle_mfa(self, user_id: int, payload: MFAToggleSchema) -> User:
        """
        Enable or disable multi-factor authentication for a user.

        Args:
            user_id: User primary key.
            payload: MFA toggle payload.

        Returns:
            User: Updated user.
        """
        user = self.get_user(user_id)
        user.is_two_factor_enabled = payload.enabled

        self.repository.update_user(user)
        self.db.commit()
        return self.get_user(user.id)

    # ============================================================
    # SESSIONS / LOGIN HISTORY
    # ============================================================

    def list_user_sessions(self, user_id: int, *, skip: int = 0, limit: int = 20):
        """
        Return paginated user session / login history.

        Args:
            user_id: User primary key.
            skip: Pagination offset.
            limit: Pagination limit.

        Returns:
            tuple[list[UserSession], int]: Session rows and total count.
        """
        self.get_user(user_id)
        return self.repository.list_user_sessions(user_id, skip=skip, limit=limit)

    def revoke_user_sessions(self, user_id: int, session_ids: list[int]) -> int:
        """
        Revoke selected sessions for a user.

        Args:
            user_id: User primary key.
            session_ids: Session primary keys.

        Returns:
            int: Number of revoked sessions.
        """
        self.get_user(user_id)
        sessions = self.repository.get_sessions_by_ids(user_id, session_ids)

        if not sessions:
            raise NotFoundError(
                message="No matching sessions were found for the user.",
                detail={"user_id": user_id, "session_ids": session_ids},
            )

        self.repository.revoke_sessions(sessions)
        self.db.commit()
        return len(sessions)

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
        self.get_user(user_id)
        count = self.repository.revoke_all_other_sessions(
            user_id,
            keep_session_jti=keep_session_jti,
        )
        self.db.commit()
        return count

    # ============================================================
    # ACCESS SUMMARY
    # ============================================================

    def get_user_access_summary(self, user_id: int):
        """
        Return a user's assigned roles and effective permissions.

        Args:
            user_id: User primary key.

        Returns:
            tuple[User, list[Permission]]: User and effective permissions.
        """
        user = self.get_user(user_id)
        permissions = self.repository.get_effective_permissions_for_user(user_id)
        return user, permissions

    # ============================================================
    # VALIDATION HELPERS
    # ============================================================

    def _validate_roles_exist(self, role_ids: list[int]) -> None:
        """
        Validate that all supplied role IDs exist.

        Args:
            role_ids: Role primary keys.

        Raises:
            NotFoundError: If any supplied role is missing.
        """
        if not role_ids:
            return

        roles = self.repository.get_roles_by_ids(role_ids)
        found_ids = {role.id for role in roles}
        missing_ids = sorted(set(role_ids) - found_ids)

        if missing_ids:
            raise NotFoundError(
                message="One or more roles were not found.",
                detail={"missing_role_ids": missing_ids},
            )

    def _validate_department_exists(self, department_id: Optional[int]) -> None:
        """
        Validate that a department exists when provided.

        Args:
            department_id: Department primary key.

        Raises:
            NotFoundError: If the department does not exist.
        """
        if department_id is None:
            return

        department = self.repository.get_department_by_id(department_id)
        if not department:
            raise NotFoundError(
                message="Department not found.",
                detail={"department_id": department_id},
            )

    def _validate_service_delivery_point_exists(
        self,
        service_delivery_point_id: Optional[int],
    ) -> None:
        """
        Validate that a service delivery point exists when provided.

        Args:
            service_delivery_point_id: Service delivery point primary key.

        Raises:
            NotFoundError: If the service delivery point does not exist.
        """
        if service_delivery_point_id is None:
            return

        service_point = self.repository.get_service_delivery_point_by_id(
            service_delivery_point_id
        )
        if not service_point:
            raise NotFoundError(
                message="Service delivery point not found.",
                detail={"service_delivery_point_id": service_delivery_point_id},
            )