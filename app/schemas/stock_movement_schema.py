# app/schemas/stock_movement_schema.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


_VALID_MOVEMENT_TYPES = {
    "OPENING_BALANCE", "PURCHASE", "ISSUE", "DISPENSE",
    "TRANSFER_IN", "TRANSFER_OUT", "ADJUSTMENT_IN", "ADJUSTMENT_OUT",
    "RETURN_IN", "RETURN_OUT", "WRITE_OFF",
}


class StockMovementCreateSchema(BaseModel):
    store_id: int
    stock_item_id: int
    movement_type: str
    quantity: Decimal
    reference_no: Optional[str] = Field(None, max_length=100)
    note: Optional[str] = Field(None, max_length=500)
    performed_by_staff_id: Optional[int] = None

    @field_validator("movement_type")
    @classmethod
    def normalize_movement_type(cls, v: str) -> str:
        normalized = v.strip().upper()
        if normalized not in _VALID_MOVEMENT_TYPES:
            raise ValueError(f"movement_type must be one of {sorted(_VALID_MOVEMENT_TYPES)}")
        return normalized

    @field_validator("quantity")
    @classmethod
    def normalize_quantity(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("quantity must be greater than zero.")
        return v


class StockTransferSchema(BaseModel):
    from_stock_item_id: int
    to_store_id: int
    quantity: Decimal
    note: Optional[str] = Field(None, max_length=500)
    performed_by_staff_id: Optional[int] = None

    @field_validator("quantity")
    @classmethod
    def positive_quantity(cls, v):
        if v <= 0:
            raise ValueError("quantity must be greater than zero.")
        return v


class StockMovementReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    store_id: int
    stock_item_id: int
    performed_by_staff_id: Optional[int] = None
    movement_type: str
    reference_no: Optional[str] = None
    quantity: Decimal
    balance_after: Optional[Decimal] = None
    movement_date: datetime
    note: Optional[str] = None
    created_at: Optional[datetime] = None


class StockMovementListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Stock movements fetched successfully."
    items: list[StockMovementReadSchema]
    count: int
    meta: dict


class StockMovementActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    movement: StockMovementReadSchema
