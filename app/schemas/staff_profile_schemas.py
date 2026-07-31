from __future__ import annotations

"""
app.schemas.staff_profile_schemas

Pydantic schemas for staff profile onboarding, user administration,
role assignment, session review, and access administration.

Purpose
-------
This module defines request and response schemas for:

- staff profile creation and update
- user account creation and update
- user-role assignment and removal
- password reset and password change flows
- account activation/deactivation support payloads
- multi-factor authentication toggle
- session review and revocation
- detailed staff profile retrieval including linked user, department,
  service delivery point, and assigned roles

Design notes
------------
- These schemas are intended for FastAPI + Pydantic v2.
- User creation requires a nested staff profile payload.
- The business payload can capture staff profile data first, even though
  the database insert order must still create the User row before the
  StaffProfile row because StaffProfile.user_id depends on User.id.
- Read schemas are designed to serialize ORM objects or explicit dict payloads.
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, EmailStr

from app.schemas.service_delivery_point_schemas import ServiceDeliveryPointLiteSchema


# ============================================================
# COMMON / EMBEDDED LITE SCHEMAS
# ============================================================

class RoleLiteSchema(BaseModel):
    """
    Lightweight role representation embedded inside user/staff responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: Optional[str] = None


class PermissionLiteSchema(BaseModel):
    """
    Lightweight permission representation embedded inside access responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    module: Optional[str] = None
    description: Optional[str] = None


class DepartmentLiteSchema(BaseModel):
    """
    Lightweight department representation.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: Optional[str] = None


class ServiceDeliveryPointLiteSchema(BaseModel):
    """
    Lightweight service delivery point representation.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    service_point_type: str
    location_description: Optional[str] = None
    queue_prefix: Optional[str] = None
    supports_appointments: bool = False
    supports_walk_in: bool = True


class UserSessionReadSchema(BaseModel):
    """
    Read schema for user session / login history entries.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_token_jti: str
    refresh_token_jti: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    login_at: datetime
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    is_current: bool


# ============================================================
# STAFF PROFILE SCHEMAS
# ============================================================

class StaffProfileBaseSchema(BaseModel):
    """
    Base shared fields for staff profile input.

    Notes
    -----
    These fields represent the organizational and professional details for
    a staff member and are collected together with user account data during
    onboarding.
    """

    department_id: Optional[int] = Field(
        None,
        description="Department ID the staff member belongs to.",
    )
    service_delivery_point_ids: list[int] = Field(
        default_factory=list,
        description="Optional list of service delivery point assignments.",
    )
    facility_id: Optional[int] = Field(
        None,
        description="Optional facility ID assignment.",
    )
    staff_no: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Unique staff number.",
    )
    job_title: Optional[str] = Field(
        None,
        max_length=150,
        description="Job title or role title.",
    )
    professional_license_no: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional professional license number.",
    )
    specialty: Optional[str] = Field(
        None,
        max_length=150,
        description="Optional specialty or professional area.",
    )

    @field_validator("staff_no")
    @classmethod
    def normalize_staff_no(cls, value: str) -> str:
        """
        Normalize the staff number for consistent storage and uniqueness checks.
        """
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Staff number cannot be empty.")
        return normalized

    @field_validator("job_title", "professional_license_no", "specialty")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize optional free-text fields.
        """
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class StaffProfileCreateSchema(StaffProfileBaseSchema):
    """
    Schema for creating a staff profile during user onboarding.
    """
    pass


class StaffProfileUpdateSchema(BaseModel):
    """
    Schema for updating an existing staff profile.
    """

    department_id: Optional[int] = None
    service_delivery_point_ids: Optional[list[int]] = None
    facility_id: Optional[int] = None
    staff_no: Optional[str] = Field(None, min_length=2, max_length=100)
    job_title: Optional[str] = Field(None, max_length=150)
    professional_license_no: Optional[str] = Field(None, max_length=100)
    specialty: Optional[str] = Field(None, max_length=150)

    @field_validator("staff_no")
    @classmethod
    def normalize_staff_no(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize staff number when provided.
        """
        if value is None:
            return value
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Staff number cannot be empty.")
        return normalized

    @field_validator("job_title", "professional_license_no", "specialty")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize optional free-text fields.
        """
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class StaffProfileReadSchema(BaseModel):
    """
    Standard read schema for staff profile data.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    department_id: Optional[int] = None
    service_delivery_point_ids: list[int] = Field(default_factory=list, validation_alias="assigned_sdp_ids")
    staff_no: str
    job_title: Optional[str] = None
    professional_license_no: Optional[str] = None
    specialty: Optional[str] = None
    facility_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StaffProfileDetailedUserSchema(BaseModel):
    """
    Detailed linked user account representation for a staff profile response.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    phone_number: Optional[str] = None
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    status: str
    is_superuser: bool
    is_two_factor_enabled: bool
    is_email_verified: bool
    is_phone_verified: bool
    last_login_at: Optional[datetime] = None
    password_changed_at: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StaffProfileDetailedReadSchema(BaseModel):
    """
    Fully detailed staff profile response.

    Includes:
    - core staff profile fields
    - linked user account
    - assigned department
    - assigned service delivery point
    - assigned roles
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    department_id: Optional[int] = None
    service_delivery_points: list[ServiceDeliveryPointLiteSchema] = Field(default_factory=list, validation_alias="assigned_sdps")
    facility_id: Optional[int] = None
    staff_no: str
    job_title: Optional[str] = None
    professional_license_no: Optional[str] = None
    specialty: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    user: StaffProfileDetailedUserSchema
    department: Optional[DepartmentLiteSchema] = None
    roles: list[RoleLiteSchema] = Field(default_factory=list)


# ============================================================
# USER SCHEMAS
# ============================================================

class UserBaseSchema(BaseModel):
    """
    Base shared fields for user create/update operations.
    """

    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    phone_number: Optional[str] = Field(None, max_length=30)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    is_superuser: bool = False
    is_two_factor_enabled: bool = False
    is_email_verified: bool = False
    is_phone_verified: bool = False

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        """
        Normalize username for consistent storage.
        """
        normalized = value.strip()
        if not normalized:
            raise ValueError("Username cannot be empty.")
        return normalized

    @field_validator("first_name", "last_name", "middle_name")
    @classmethod
    def normalize_names(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize name-like fields.
        """
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("phone_number")
    @classmethod
    def normalize_phone(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize phone number by stripping spaces.
        """
        if value is None:
            return value
        normalized = value.strip().replace(" ", "")
        return normalized or None


class UserCreateSchema(UserBaseSchema):
    """
    Schema for creating a new user account.

    Important
    ---------
    Staff profile input is required so onboarding can capture all employment
    data together with user account details.
    """

    password: str = Field(..., min_length=8, max_length=128)
    role_ids: list[int] = Field(
        default_factory=list,
        description="Optional role IDs to assign during user creation.",
    )
    staff_profile: StaffProfileCreateSchema = Field(
        ...,
        description="Required staff profile payload for onboarding.",
    )


class UserUpdateSchema(BaseModel):
    """
    Schema for updating a user account.

    Notes
    -----
    Staff profile changes can be supplied through the nested `staff_profile`
    field when needed.
    """

    username: Optional[str] = Field(None, min_length=3, max_length=100)
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, max_length=30)
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    is_superuser: Optional[bool] = None
    is_two_factor_enabled: Optional[bool] = None
    is_email_verified: Optional[bool] = None
    is_phone_verified: Optional[bool] = None
    status: Optional[str] = None
    staff_profile: Optional[StaffProfileUpdateSchema] = None

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize username when provided.
        """
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Username cannot be empty.")
        return normalized

    @field_validator("first_name", "last_name", "middle_name")
    @classmethod
    def normalize_names(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize name-like fields.
        """
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("phone_number")
    @classmethod
    def normalize_phone(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize phone number when provided.
        """
        if value is None:
            return value
        normalized = value.strip().replace(" ", "")
        return normalized or None

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize account status string.
        """
        if value is None:
            return value
        return value.strip().upper()


class UserReadSchema(BaseModel):
    """
    Full read schema for user administration views.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    phone_number: Optional[str] = None
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    status: str
    is_superuser: bool
    is_two_factor_enabled: bool
    is_email_verified: bool
    is_phone_verified: bool
    last_login_at: Optional[datetime] = None
    password_changed_at: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    roles: list[RoleLiteSchema] = Field(default_factory=list)
    staff_profile: Optional[StaffProfileReadSchema] = None


class UserListItemSchema(BaseModel):
    """
    Lightweight user list schema for paginated user administration views.
    """

    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    status: str
    is_superuser: bool
    is_two_factor_enabled: bool
    last_login_at: Optional[datetime] = None
    role_count: int = 0
    staff_no: Optional[str] = None
    job_title: Optional[str] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    service_delivery_point_ids: list[int] = []


class UserListResponseSchema(BaseModel):
    """
    Paginated user list response.
    """

    success: bool = True
    message: str = "Users fetched successfully."
    items: list[UserListItemSchema]
    count: int
    meta: dict


# ============================================================
# ROLE ASSIGNMENT / PASSWORD / ACCOUNT CONTROL
# ============================================================

class RoleAssignmentSchema(BaseModel):
    """
    Role assignment payload.
    """

    role_ids: list[int] = Field(..., min_length=1)


class PasswordResetSchema(BaseModel):
    """
    Administrator-triggered password reset payload.
    """

    new_password: str = Field(..., min_length=8, max_length=128)
    force_password_change_on_next_login: bool = False


class PasswordChangeSchema(BaseModel):
    """
    Authenticated self-service password change payload.
    """

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class AccountStatusSchema(BaseModel):
    """
    Account activation/deactivation payload.
    """

    is_active: bool


class MFAToggleSchema(BaseModel):
    """
    Enable or disable multi-factor authentication for a user account.
    """

    enabled: bool


class SessionRevokeSchema(BaseModel):
    """
    Revoke one or more session records.
    """

    session_ids: list[int] = Field(..., min_length=1)


# ============================================================
# ACCESS / PERMISSION RESPONSES
# ============================================================

class UserAccessSummarySchema(BaseModel):
    """
    Summarized access view for a single user.

    Includes the user's roles and effective permissions aggregated from roles.
    """

    user: UserReadSchema
    permissions: list[PermissionLiteSchema]


class ActionResponseSchema(BaseModel):
    """
    Generic action response.
    """

    success: bool = True
    message: str