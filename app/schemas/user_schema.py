# app/schemas/user_schema.py
from __future__ import annotations

"""
app.schemas.user_schema

Pydantic schemas for administrative user management.

Purpose
-------
Defines request/response schemas for admin endpoints that:
- create users
- list and filter users
- update user profile fields
- change user status
- assign / revoke roles
- force password reset
- unlock accounts
- list active sessions
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


# ============================================================
# SHARED LITE SCHEMAS
# ============================================================

class UserRoleLiteSchema(BaseModel):
    """
    Lightweight role payload embedded in user responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: Optional[str] = None
    description: Optional[str] = None


class UserSessionLiteSchema(BaseModel):
    """
    Lightweight session payload for the user sessions endpoint.
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
    is_current: bool = False


# ============================================================
# REQUEST SCHEMAS
# ============================================================

class UserCreateSchema(BaseModel):
    """
    Schema for admin-driven user creation.
    """

    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    phone_number: Optional[str] = Field(None, max_length=30)
    password: str = Field(..., min_length=8, max_length=255)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    is_superuser: bool = False
    is_email_verified: bool = False
    is_phone_verified: bool = False
    is_two_factor_enabled: bool = False
    role_ids: list[int] = Field(default_factory=list)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("username cannot be empty.")
        return normalized

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().replace(" ", "")
        return normalized or None

    @field_validator("first_name", "last_name", "middle_name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

class UserInviteSchema(BaseModel):
    """
    Schema for inviting a new user (password is system-generated).
    """
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    phone_number: Optional[str] = Field(None, max_length=30)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    role_ids: list[int] = Field(default_factory=list)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("username cannot be empty.")
        return normalized

class UserUpdateSchema(BaseModel):
    """
    Schema for partial user profile updates by an admin.
    """

    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, max_length=30)
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    is_email_verified: Optional[bool] = None
    is_phone_verified: Optional[bool] = None
    is_two_factor_enabled: Optional[bool] = None

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().replace(" ", "")
        return normalized or None

    @field_validator("first_name", "last_name", "middle_name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class UserStatusUpdateSchema(BaseModel):
    """
    Schema for changing a user's status.
    """

    status: str = Field(..., min_length=1, max_length=50, description="ACTIVE, INACTIVE, LOCKED, SUSPENDED.")
    reason: Optional[str] = Field(None, max_length=500)

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"ACTIVE", "INACTIVE", "LOCKED", "SUSPENDED"}:
            raise ValueError("status must be one of ACTIVE, INACTIVE, LOCKED, SUSPENDED.")
        return normalized


class UserRoleAssignmentSchema(BaseModel):
    """
    Schema for assigning roles to a user.
    """

    role_ids: list[int] = Field(..., min_length=1)


class UserPasswordResetSchema(BaseModel):
    """
    Admin-initiated forced password reset payload.
    """

    new_password: str = Field(..., min_length=8, max_length=255)
    require_change_on_next_login: bool = True
    revoke_active_sessions: bool = True

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("new_password cannot be empty.")
        return value


# ============================================================
# RESPONSE SCHEMAS
# ============================================================

class UserReadSchema(BaseModel):
    """
    Standard user response schema.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    status: Optional[str] = None
    is_superuser: bool = False
    is_email_verified: bool = False
    is_phone_verified: bool = False
    is_two_factor_enabled: bool = False
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    password_changed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    roles: list[UserRoleLiteSchema] = Field(default_factory=list)


class UserListResponseSchema(BaseModel):
    """
    Paginated user list response schema.
    """

    success: bool = True
    message: str = "Users fetched successfully."
    items: list[UserReadSchema]
    count: int
    meta: dict


class UserActionResponseSchema(BaseModel):
    """
    Response wrapper for user-management actions that return the updated user.
    """

    success: bool = True
    message: str
    user: UserReadSchema


class UserSessionListResponseSchema(BaseModel):
    """
    Response schema for listing a user's sessions.
    """

    success: bool = True
    message: str = "Sessions fetched successfully."
    sessions: list[UserSessionLiteSchema] = Field(default_factory=list)


class UserDeleteResponseSchema(BaseModel):
    """
    Response schema for soft-delete operations.
    """

    success: bool = True
    message: str = "User deactivated successfully."
    user_id: int
