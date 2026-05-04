# app/schemas/inventory_schema.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --- STORE ---

class InventoryStoreCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    code: str = Field(..., min_length=1, max_length=100)
    location_description: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "_")


class InventoryStoreUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    location_description: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None


class InventoryStoreReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    location_description: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# --- STOCK ITEM ---

class InventoryStockItemCreateSchema(BaseModel):
    store_id: int
    drug_id: Optional[int] = None
    item_type: str = Field(default="DRUG")
    item_name: str = Field(..., min_length=1, max_length=255)
    sku: Optional[str] = Field(None, max_length=100)
    unit_of_measure: Optional[str] = Field(None, max_length=50)
    quantity_on_hand: Decimal = Decimal("0")
    reorder_level: Optional[Decimal] = None
    unit_cost: Optional[Decimal] = None
    expiry_date: Optional[date] = None
    batch_no: Optional[str] = Field(None, max_length=100)

    @field_validator("item_type")
    @classmethod
    def normalize_type(cls, v: str) -> str:
        normalized = v.strip().upper()
        if normalized not in {"DRUG", "CONSUMABLE", "EQUIPMENT", "SUPPLY", "OTHER"}:
            raise ValueError("item_type must be one of DRUG, CONSUMABLE, EQUIPMENT, SUPPLY, OTHER.")
        return normalized


class InventoryStockItemUpdateSchema(BaseModel):
    item_name: Optional[str] = Field(None, min_length=1, max_length=255)
    sku: Optional[str] = Field(None, max_length=100)
    unit_of_measure: Optional[str] = Field(None, max_length=50)
    reorder_level: Optional[Decimal] = None
    unit_cost: Optional[Decimal] = None
    expiry_date: Optional[date] = None
    batch_no: Optional[str] = Field(None, max_length=100)


class InventoryStockItemReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    store_id: int
    drug_id: Optional[int] = None
    item_type: str
    item_name: str
    sku: Optional[str] = None
    unit_of_measure: Optional[str] = None
    quantity_on_hand: Decimal
    reorder_level: Optional[Decimal] = None
    unit_cost: Optional[Decimal] = None
    expiry_date: Optional[date] = None
    batch_no: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class InventoryStockItemListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Stock items fetched successfully."
    items: list[InventoryStockItemReadSchema]
    count: int
    meta: dict


class InventoryStoreListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Stores fetched successfully."
    items: list[InventoryStoreReadSchema]
    count: int
    meta: dict


class InventoryStoreActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    store: InventoryStoreReadSchema


class InventoryStockItemActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    stock_item: InventoryStockItemReadSchema
