# app/schemas/lab_schema.py
from __future__ import annotations

"""
Schemas for the LabTestCatalog (master list of laboratory tests).
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LabTestCatalogCreateSchema(BaseModel):
    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    sample_type: Optional[str] = Field(None, max_length=100)
    unit_of_measure: Optional[str] = Field(None, max_length=50)
    reference_range: Optional[str] = Field(None, max_length=255)
    default_price: Optional[Decimal] = None
    description: Optional[str] = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper().replace(" ", "_")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class LabTestCatalogUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    sample_type: Optional[str] = Field(None, max_length=100)
    unit_of_measure: Optional[str] = Field(None, max_length=50)
    reference_range: Optional[str] = Field(None, max_length=255)
    default_price: Optional[Decimal] = None
    description: Optional[str] = None


class LabTestCatalogReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    sample_type: Optional[str] = None
    unit_of_measure: Optional[str] = None
    reference_range: Optional[str] = None
    default_price: Optional[Decimal] = None
    description: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LabTestCatalogListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Lab tests fetched successfully."
    items: list[LabTestCatalogReadSchema]
    count: int
    meta: dict


class LabTestCatalogActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    lab_test: LabTestCatalogReadSchema
