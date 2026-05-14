# app/schemas/pharmacy_schema.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.prescription_schema import PrescriptionReadSchema

class PharmacyStockReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    store_id: int
    drug_id: int
    item_name: str
    sku: Optional[str] = None
    quantity_on_hand: Decimal
    reorder_level: Decimal
    expiry_date: Optional[datetime] = None
    batch_no: Optional[str] = None

class PharmacyWorklistResponseSchema(BaseModel):
    success: bool = True
    message: str = "Pharmacy worklist fetched successfully."
    items: list[PrescriptionReadSchema]
    count: int
    meta: dict

class PharmacyStockAlertsResponseSchema(BaseModel):
    success: bool = True
    message: str = "Pharmacy stock alerts fetched successfully."
    low_stock: list[PharmacyStockReadSchema]
    expiring_soon: list[PharmacyStockReadSchema]
