from __future__ import annotations

"""
app.schemas.ward_schemas

Pydantic schemas for ward management.

Purpose
-------
This module defines request and response schemas for the ward module.

It covers:
- creating wards
- updating wards
- reading ward details
- listing wards
- returning lightweight ward representations for nested responses

Design notes
------------
- These schemas are aligned with the current Ward ORM model.
- The current Ward model contains:
    - name
    - code
    - ward_type
    - description
- The current Ward model also has relationships to:
    - beds
    - admissions

Current model alignment
-----------------------
The current all_models.py defines Ward as:

    class Ward(BaseTable):
        name: str
        code: str
        ward_type: Optional[str]
        description: Optional[str]
        beds: relationship
        admissions: relationship

These schemas therefore avoid fields like facility_id, department_id, or
is_active because they are not present in the current Ward model.
"""

from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


# ============================================================
# BASE / SHARED SCHEMAS
# ============================================================

class WardBaseSchema(BaseModel):
    """
    Base shared ward fields.

    This schema is used as the foundation for create/update payloads.
    """

    name: str = Field(
        ...,
        min_length=2,
        max_length=150,
        description="Human-readable ward name.",
        examples=["Female Medical Ward"],
    )
    code: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Unique ward code.",
        examples=["FMW-01"],
    )
    ward_type: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional ward classification such as ICU, Pediatric, Isolation, or Surgical.",
        examples=["ICU"],
    )
    description: Optional[str] = Field(
        None,
        description="Optional ward description.",
        examples=["High-dependency inpatient ward for critical monitoring."],
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """
        Normalize and validate ward name.

        Args:
            value: Raw ward name.

        Returns:
            str: Normalized ward name.
        """
        normalized = value.strip()
        if not normalized:
            raise ValueError("Ward name cannot be empty.")
        return normalized

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        """
        Normalize and validate ward code.

        The code is uppercased for consistency.

        Args:
            value: Raw ward code.

        Returns:
            str: Normalized ward code.
        """
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Ward code cannot be empty.")
        return normalized

    @field_validator("ward_type")
    @classmethod
    def normalize_ward_type(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize optional ward type.

        Args:
            value: Optional ward type.

        Returns:
            Optional[str]: Normalized value.
        """
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize optional description.

        Args:
            value: Optional description.

        Returns:
            Optional[str]: Normalized value.
        """
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


# ============================================================
# CREATE / UPDATE SCHEMAS
# ============================================================

class WardCreateSchema(WardBaseSchema):
    """
    Schema for creating a ward.
    """
    pass


class WardUpdateSchema(BaseModel):
    """
    Schema for partially updating an existing ward.
    """

    name: Optional[str] = Field(None, min_length=2, max_length=150)
    code: Optional[str] = Field(None, min_length=2, max_length=100)
    ward_type: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize ward name when provided.
        """
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Ward name cannot be empty.")
        return normalized

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize ward code when provided.
        """
        if value is None:
            return value
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Ward code cannot be empty.")
        return normalized

    @field_validator("ward_type")
    @classmethod
    def normalize_ward_type(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize ward type when provided.
        """
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize description when provided.
        """
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


# ============================================================
# READ SCHEMAS
# ============================================================

class WardLiteSchema(BaseModel):
    """
    Lightweight ward representation for embedding inside other responses
    such as bed or admission responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    ward_type: Optional[str] = None
    description: Optional[str] = None


class WardReadSchema(BaseModel):
    """
    Standard ward read schema.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    code: str
    ward_type: Optional[str] = None
    description: Optional[str] = None
    # ORM base columns are date_created / date_updated.
    created_at: Optional[datetime] = Field(
        None, validation_alias=AliasChoices("created_at", "date_created")
    )
    updated_at: Optional[datetime] = Field(
        None, validation_alias=AliasChoices("updated_at", "date_updated")
    )


class WardDetailedReadSchema(BaseModel):
    """
    Detailed ward read schema.

    This can be used when returning ward summaries together with simple
    aggregated operational values such as bed and admission counts.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    code: str
    ward_type: Optional[str] = None
    description: Optional[str] = None
    # ORM base columns are date_created / date_updated.
    created_at: Optional[datetime] = Field(
        None, validation_alias=AliasChoices("created_at", "date_created")
    )
    updated_at: Optional[datetime] = Field(
        None, validation_alias=AliasChoices("updated_at", "date_updated")
    )

    total_beds: int = 0
    available_beds: int = 0
    occupied_beds: int = 0
    total_admissions: int = 0
    active_admissions: int = 0


class WardListItemSchema(BaseModel):
    """
    Ward list item schema for paginated ward list views.
    """

    id: int
    name: str
    code: str
    ward_type: Optional[str] = None
    description: Optional[str] = None
    total_beds: int = 0
    available_beds: int = 0
    occupied_beds: int = 0
    active_admissions: int = 0


class WardListResponseSchema(BaseModel):
    """
    Paginated ward list response schema.
    """

    success: bool = True
    message: str = "Wards fetched successfully."
    items: list[WardListItemSchema]
    count: int
    meta: dict


# ============================================================
# GENERIC ACTION RESPONSE
# ============================================================

class WardActionResponseSchema(BaseModel):
    """
    Generic action response for ward-related mutations.
    """

    success: bool = True
    message: str