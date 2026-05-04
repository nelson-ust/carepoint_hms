# app/schemas/drug_schema.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ------- DRUG CATEGORY -------

class DrugCategoryCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    code: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v):
        if v is None:
            return v
        return v.strip().upper().replace(" ", "_") or None


class DrugCategoryUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    code: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None


class DrugCategoryReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ------- DRUG -------

class DrugCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    generic_name: Optional[str] = Field(None, max_length=255)
    brand_name: Optional[str] = Field(None, max_length=255)
    strength: Optional[str] = Field(None, max_length=100)
    dosage_form: Optional[str] = Field(None, max_length=100)
    pack_size: Optional[str] = Field(None, max_length=100)
    sku: Optional[str] = Field(None, max_length=100)
    drug_category_id: Optional[int] = None
    unit_price: Optional[Decimal] = None
    reorder_level: Optional[Decimal] = None
    is_controlled: bool = False


class DrugUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    generic_name: Optional[str] = Field(None, max_length=255)
    brand_name: Optional[str] = Field(None, max_length=255)
    strength: Optional[str] = Field(None, max_length=100)
    dosage_form: Optional[str] = Field(None, max_length=100)
    pack_size: Optional[str] = Field(None, max_length=100)
    sku: Optional[str] = Field(None, max_length=100)
    drug_category_id: Optional[int] = None
    unit_price: Optional[Decimal] = None
    reorder_level: Optional[Decimal] = None
    is_controlled: Optional[bool] = None


class DrugReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    generic_name: Optional[str] = None
    brand_name: Optional[str] = None
    strength: Optional[str] = None
    dosage_form: Optional[str] = None
    pack_size: Optional[str] = None
    sku: Optional[str] = None
    drug_category_id: Optional[int] = None
    unit_price: Optional[Decimal] = None
    reorder_level: Optional[Decimal] = None
    is_controlled: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DrugListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Drugs fetched successfully."
    items: list[DrugReadSchema]
    count: int
    meta: dict


class DrugActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    drug: DrugReadSchema


class DrugCategoryActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    category: DrugCategoryReadSchema


class DrugCategoryListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Drug categories fetched successfully."
    items: list[DrugCategoryReadSchema]
    count: int
    meta: dict
