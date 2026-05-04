from __future__ import annotations

"""
app.schemas.bed_schemas

Pydantic schemas for bed management.

Purpose
-------
This module defines request and response schemas for the bed module.

It covers:
- creating beds
- updating beds
- reading bed details
- listing beds
- returning lightweight embedded bed representations
- returning detailed bed responses with ward context

Design notes
------------
- These schemas are aligned with the current Bed ORM model.
- The current Bed model contains:
    - ward_id
    - bed_no
    - bed_status
    - bed_type
    - notes
- The current Bed model belongs to Ward and can also be linked to Admissions.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================
# EMBEDDED / LITE SCHEMAS
# ============================================================

class WardLiteSchema(BaseModel):
    """
    Lightweight ward representation for nested bed responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    ward_type: Optional[str] = None
    description: Optional[str] = None


# ============================================================
# BASE / SHARED SCHEMAS
# ============================================================

class BedBaseSchema(BaseModel):
    """
    Base shared fields for bed schemas.
    """

    ward_id: int = Field(
        ...,
        description="Ward ID the bed belongs to.",
        examples=[1],
    )
    bed_no: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Ward-unique bed number or code.",
        examples=["B-01"],
    )
    bed_status: str = Field(
        ...,
        description="Bed operational status.",
        examples=["AVAILABLE"],
    )
    bed_type: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional bed type such as General, ICU, Pediatric, Electric, etc.",
        examples=["General"],
    )
    notes: Optional[str] = Field(
        None,
        description="Optional notes about the bed.",
        examples=["Near nursing station."],
    )

    @field_validator("bed_no")
    @classmethod
    def normalize_bed_no(cls, value: str) -> str:
        """
        Normalize and validate bed number/code.
        """
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Bed number cannot be empty.")
        return normalized

    @field_validator("bed_status")
    @classmethod
    def normalize_bed_status(cls, value: str) -> str:
        """
        Normalize bed status for consistent storage.

        The current allowed statuses in the model enum are:
        AVAILABLE, RESERVED, OCCUPIED, OUT_OF_SERVICE.
        """
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Bed status cannot be empty.")
        return normalized

    @field_validator("bed_type")
    @classmethod
    def normalize_bed_type(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize optional bed type.
        """
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize optional notes.
        """
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


# ============================================================
# CREATE / UPDATE SCHEMAS
# ============================================================

class BedCreateSchema(BedBaseSchema):
    """
    Schema for creating a bed.
    """
    pass


class BedUpdateSchema(BaseModel):
    """
    Schema for partially updating an existing bed.
    """

    ward_id: Optional[int] = None
    bed_no: Optional[str] = Field(None, min_length=1, max_length=100)
    bed_status: Optional[str] = None
    bed_type: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None

    @field_validator("bed_no")
    @classmethod
    def normalize_bed_no(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize bed number when provided.
        """
        if value is None:
            return value
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Bed number cannot be empty.")
        return normalized

    @field_validator("bed_status")
    @classmethod
    def normalize_bed_status(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize bed status when provided.
        """
        if value is None:
            return value
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Bed status cannot be empty.")
        return normalized

    @field_validator("bed_type")
    @classmethod
    def normalize_bed_type(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize bed type when provided.
        """
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: Optional[str]) -> Optional[str]:
        """
        Normalize notes when provided.
        """
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


# ============================================================
# READ SCHEMAS
# ============================================================

class BedLiteSchema(BaseModel):
    """
    Lightweight bed representation for embedding inside admission responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    ward_id: int
    bed_no: str
    bed_status: str
    bed_type: Optional[str] = None
    notes: Optional[str] = None


class BedReadSchema(BaseModel):
    """
    Standard bed read schema.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    ward_id: int
    bed_no: str
    bed_status: str
    bed_type: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BedDetailedReadSchema(BaseModel):
    """
    Detailed bed read schema including ward context and simple admission summary.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    ward_id: int
    bed_no: str
    bed_status: str
    bed_type: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    ward: Optional[WardLiteSchema] = None
    admission_count: int = 0
    has_active_admission: bool = False


class BedListItemSchema(BaseModel):
    """
    Bed list item schema for paginated bed list views.
    """

    id: int
    ward_id: int
    bed_no: str
    bed_status: str
    bed_type: Optional[str] = None
    notes: Optional[str] = None
    ward_name: Optional[str] = None
    ward_code: Optional[str] = None
    admission_count: int = 0
    has_active_admission: bool = False


class BedListResponseSchema(BaseModel):
    """
    Paginated bed list response schema.
    """

    success: bool = True
    message: str = "Beds fetched successfully."
    items: list[BedListItemSchema]
    count: int
    meta: dict


# ============================================================
# GENERIC ACTION RESPONSE
# ============================================================

class BedActionResponseSchema(BaseModel):
    """
    Generic action response for bed-related mutations.
    """

    success: bool = True
    message: str