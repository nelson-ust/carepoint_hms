# app/schemas/dispense_schema.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DispenseItemCreateSchema(BaseModel):
    prescription_item_id: int
    quantity_dispensed: Decimal = Field(..., gt=0)
    stock_item_id: Optional[int] = Field(
        None, description="Optional explicit stock item to deduct from. If omitted, FEFO selection is used."
    )
    note: Optional[str] = Field(None, max_length=500)


class DispenseCreateSchema(BaseModel):
    prescription_id: int
    dispensed_by_staff_id: Optional[int] = None
    note: Optional[str] = Field(None, max_length=2000)
    items: list[DispenseItemCreateSchema] = Field(..., min_length=1)
    store_id: Optional[int] = Field(
        None, description="Default store to deduct from when stock_item_id is not specified per line."
    )


class DispenseItemReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dispense_id: int
    prescription_item_id: int
    quantity_dispensed: Decimal
    note: Optional[str] = None
    created_at: Optional[datetime] = None


class DispenseReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prescription_id: int
    dispensed_by_staff_id: Optional[int] = None
    dispense_no: str
    status: str
    dispensed_at: Optional[datetime] = None
    note: Optional[str] = None
    items: list[DispenseItemReadSchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DispenseActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    dispense: DispenseReadSchema


class DispenseListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Dispenses fetched successfully."
    items: list[DispenseReadSchema]
    count: int
    meta: dict
