#app/schemas/role_schemas
from __future__ import annotations

"""
app.schemas.role_schemas

Pydantic schemas for role and permission management.

Purpose
-------
This module defines request and response schemas for the RBAC role module.

It covers:
- creating roles
- updating roles
- reading role details
- listing roles
- attaching and detaching permissions from roles
- returning permission details alongside role records

Design notes
------------
- These schemas are intended for FastAPI request/response use.
- They are compatible with Pydantic v2 style configuration.
- They mirror the current RBAC ORM models:
    - Role
    - Permission
    - RolePermissionAssociation
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


class PermissionLiteSchema(BaseModel):
    """
    Lightweight permission representation for embedding inside role responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    module: Optional[str] = None
    description: Optional[str] = None


class RoleBaseSchema(BaseModel):
    """
    Base shared fields for role schemas.
    """

    name: str = Field(..., min_length=2, max_length=100, description="Human-readable role name.")
    code: str = Field(..., min_length=2, max_length=100, description="Unique role code.")
    description: Optional[str] = Field(None, description="Optional role description.")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """
        Normalize and validate role name.
        """
        normalized = value.strip()
        if not normalized:
            raise ValueError("Role name cannot be empty.")
        return normalized

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        """
        Normalize and validate role code.

        Role codes are stored uppercase for consistency.
        """
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Role code cannot be empty.")
        return normalized


class RoleCreateSchema(RoleBaseSchema):
    """
    Schema for creating a new role.
    """

    permission_ids: list[int] = Field(
        default_factory=list,
        description="Optional permission IDs to attach during role creation.",
    )


class RoleUpdateSchema(BaseModel):
    """
    Schema for partial role updates.
    """

    name: Optional[str] = Field(None, min_length=2, max_length=100)
    code: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize role name when provided.
        """
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Role name cannot be empty.")
        return normalized

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize role code when provided.
        """
        if value is None:
            return value
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Role code cannot be empty.")
        return normalized


class RoleReadSchema(BaseModel):
    """
    Full role response schema.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    permissions: list[PermissionLiteSchema] = Field(default_factory=list)


class RoleListItemSchema(BaseModel):
    """
    Lightweight role list response schema.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: Optional[str] = None
    permission_count: int = 0
    user_count: int = 0


class RoleListResponseSchema(BaseModel):
    """
    Paginated role list response schema.
    """

    success: bool = True
    message: str = "Roles fetched successfully."
    items: list[RoleListItemSchema]
    count: int
    meta: dict


class PermissionAssignmentSchema(BaseModel):
    """
    Schema for assigning permissions to a role.
    """

    permission_ids: list[int] = Field(
        ...,
        min_length=1,
        description="Permission IDs to assign to the role.",
    )


class RolePermissionUpdateResponseSchema(BaseModel):
    """
    Response schema after permission assignment/removal.
    """

    success: bool = True
    message: str
    role: RoleReadSchema