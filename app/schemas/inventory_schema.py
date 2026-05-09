# app/schemas/inventory_schema.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --- STORE ---

class InventoryStoreCreateSchema(BaseModel):
    """Schema for creating a new physical or logical inventory store."""
    
    name: str = Field(..., min_length=1, max_length=150, description="Display name of the store (e.g., Main Pharmacy)")
    code: str = Field(..., min_length=1, max_length=100, description="Unique alphanumeric code for the store")
    location_description: Optional[str] = Field(None, max_length=255, description="Physical location within the facility")
    description: Optional[str] = Field(None, description="Detailed notes about the store's purpose")

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        """Normalize the store code to uppercase with underscores."""
        return v.strip().upper().replace(" ", "_")


class InventoryStoreUpdateSchema(BaseModel):
    """Schema for updating an existing inventory store's non-identifying fields."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    location_description: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None


class InventoryStoreReadSchema(BaseModel):
    """Output schema for inventory store details."""
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
    """Schema for registering a new trackable item within a specific store."""
    
    store_id: int = Field(..., description="The store where this stock item is held")
    drug_id: Optional[int] = Field(None, description="Link to the drug master record if this is a medication")
    item_type: str = Field(default="DRUG", description="DRUG, CONSUMABLE, EQUIPMENT, etc.")
    item_name: str = Field(..., min_length=1, max_length=255, description="Specific name for this batch/item")
    sku: Optional[str] = Field(None, max_length=100, description="Stock Keeping Unit")
    unit_of_measure: Optional[str] = Field(None, max_length=50, description="e.g., Tablet, Vial, Pack")
    quantity_on_hand: Decimal = Field(Decimal("0"), description="Starting balance")
    reorder_level: Optional[Decimal] = Field(None, description="Threshold for low-stock alerts")
    unit_cost: Optional[Decimal] = Field(None, description="Procurement cost per unit")
    expiry_date: Optional[date] = Field(None, description="When the item becomes unusable")
    batch_no: Optional[str] = Field(None, max_length=100, description="Manufacturer batch number")

    @field_validator("item_type")
    @classmethod
    def normalize_type(cls, v: str) -> str:
        """Validate and normalize the item type enum."""
        normalized = v.strip().upper()
        if normalized not in {"DRUG", "CONSUMABLE", "EQUIPMENT", "SUPPLY", "OTHER"}:
            raise ValueError("item_type must be one of DRUG, CONSUMABLE, EQUIPMENT, SUPPLY, OTHER.")
        return normalized


class InventoryStockItemUpdateSchema(BaseModel):
    """Schema for updating stock item metadata (not quantity)."""
    
    item_name: Optional[str] = Field(None, min_length=1, max_length=255)
    sku: Optional[str] = Field(None, max_length=100)
    unit_of_measure: Optional[str] = Field(None, max_length=50)
    reorder_level: Optional[Decimal] = None
    unit_cost: Optional[Decimal] = None
    expiry_date: Optional[date] = None
    batch_no: Optional[str] = Field(None, max_length=100)


class InventoryStockItemReadSchema(BaseModel):
    """Output schema for stock item details including current balance."""
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
    """Paginated response for stock items."""
    success: bool = True
    message: str = "Stock items fetched successfully."
    items: list[InventoryStockItemReadSchema]
    count: int
    meta: dict


class InventoryStoreListResponseSchema(BaseModel):
    """Paginated response for stores."""
    success: bool = True
    message: str = "Stores fetched successfully."
    items: list[InventoryStoreReadSchema]
    count: int
    meta: dict


class InventoryStoreActionResponseSchema(BaseModel):
    """Standard response for store creation/update."""
    success: bool = True
    message: str
    store: InventoryStoreReadSchema


class InventoryStockItemActionResponseSchema(BaseModel):
    """Standard response for stock item creation/update."""
    success: bool = True
    message: str
    stock_item: InventoryStockItemReadSchema


# --- STOCK MOVEMENT ---

class StockMovementCreateSchema(BaseModel):
    """Schema for recording a new inflow or outflow movement."""
    
    store_id: int = Field(..., description="The store where the movement occurs")
    stock_item_id: int = Field(..., description="The specific stock item record to adjust")
    performed_by_staff_id: Optional[int] = Field(None, description="The staff member responsible for the change")
    movement_type: str = Field(..., min_length=1, max_length=50, description="e.g., PURCHASE, DISPENSE, ADJUSTMENT_IN")
    reference_no: Optional[str] = Field(None, max_length=100, description="External reference (Invoice #, GRN #)")
    quantity: Decimal = Field(..., description="Amount moved (always positive; direction determined by type)")
    note: Optional[str] = Field(None, description="Reason for the movement")

    @field_validator("movement_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Ensure the movement type is a valid StockMovementType enum."""
        from app.core.enums import StockMovementType
        try:
            return StockMovementType(v.strip().upper()).value
        except ValueError:
            valid = [e.value for e in StockMovementType]
            raise ValueError(f"movement_type must be one of: {', '.join(valid)}")


class StockMovementReadSchema(BaseModel):
    """Output schema for historical stock movement records."""
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


class StockMovementListResponseSchema(BaseModel):
    """Paginated response for stock movement history."""
    success: bool = True
    message: str = "Stock movements fetched successfully."
    items: list[StockMovementReadSchema]
    count: int
    meta: dict


class StockMovementActionResponseSchema(BaseModel):
    """Standard response for recording a movement."""
    success: bool = True
    message: str
    movement: StockMovementReadSchema
