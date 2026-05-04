# app/schemas/permission_schema.py
from __future__ import annotations

"""
app.schemas.permission_schema

Pydantic schemas for fine-grained permission management.

Purpose
-------
This module defines request and response schemas for the RBAC permission
catalog used by Carepoint HMS.

It covers:
- creating permissions
- updating permissions
- reading permission details
- listing permissions
- bulk-creating permissions during seeding
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PermissionBaseSchema(BaseModel):
    """
    Base shared fields for permission schemas.
    """

    name: str = Field(..., min_length=2, max_length=150, description="Human-readable permission name.")
    code: str = Field(..., min_length=2, max_length=150, description="Stable permission code, e.g. PATIENT_CREATE.")
    module: Optional[str] = Field(None, max_length=100, description="Logical module/domain this permission belongs to.")
    description: Optional[str] = Field(None, description="Optional permission description.")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Permission name cannot be empty.")
        return normalized

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        normalized = value.strip().upper().replace(" ", "_")
        if not normalized:
            raise ValueError("Permission code cannot be empty.")
        return normalized

    @field_validator("module")
    @classmethod
    def validate_module(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None


class PermissionCreateSchema(PermissionBaseSchema):
    """
    Schema for creating a new permission.
    """

    is_system: bool = Field(default=False, description="Mark this permission as a system permission (immutable).")


class PermissionUpdateSchema(BaseModel):
    """
    Schema for partial permission updates.
    """

    name: Optional[str] = Field(None, min_length=2, max_length=150)
    code: Optional[str] = Field(None, min_length=2, max_length=150)
    module: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Permission name cannot be empty.")
        return normalized

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper().replace(" ", "_")
        if not normalized:
            raise ValueError("Permission code cannot be empty.")
        return normalized

    @field_validator("module")
    @classmethod
    def validate_module(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None


class PermissionReadSchema(BaseModel):
    """
    Permission response schema.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    module: Optional[str] = None
    description: Optional[str] = None
    is_system: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PermissionListResponseSchema(BaseModel):
    """
    Paginated permission list response schema.
    """

    success: bool = True
    message: str = "Permissions fetched successfully."
    items: list[PermissionReadSchema]
    count: int
    meta: dict


class PermissionBulkCreateSchema(BaseModel):
    """
    Bulk creation schema used by seed scripts and admin tooling.
    """

    permissions: list[PermissionCreateSchema] = Field(..., min_length=1)


class PermissionBulkCreateResponseSchema(BaseModel):
    """
    Response for bulk-creation/upsert of permissions.
    """

    success: bool = True
    message: str = "Permissions processed successfully."
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    items: list[PermissionReadSchema] = Field(default_factory=list)
