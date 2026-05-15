# app/schemas/meal_schemas.py
from __future__ import annotations

"""
Pydantic schemas for Dietary & Meal Management.
Covers Meal Types (catalog) and Meal Orders (transactions).
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import MealRecipient, MealStatus


# ============================================================
# MEAL TYPE SCHEMAS
# ============================================================

class MealTypeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    code: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    base_price: Decimal = Field(default=Decimal("0.00"), ge=0)
    billable_service_id: Optional[int] = None


class MealTypeCreate(MealTypeBase):
    pass


class MealTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = None
    base_price: Optional[Decimal] = Field(None, ge=0)
    billable_service_id: Optional[int] = None


class MealTypeRead(MealTypeBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MealTypeActionResponse(BaseModel):
    success: bool = True
    message: str
    meal_type: MealTypeRead


# ============================================================
# MEAL ORDER SCHEMAS
# ============================================================

class MealOrderBase(BaseModel):
    visit_id: int
    patient_id: int
    meal_type_id: int
    recipient_type: MealRecipient = MealRecipient.PATIENT
    caregiver_name: Optional[str] = Field(None, max_length=200)
    quantity: Decimal = Field(default=Decimal("1.00"), gt=0)
    notes: Optional[str] = None


class MealOrderCreate(MealOrderBase):
    """Payload for creating a new meal order."""
    pass


class MealOrderUpdate(BaseModel):
    """Payload for updating an existing meal order status."""
    status: Optional[MealStatus] = None
    caregiver_name: Optional[str] = None
    quantity: Optional[Decimal] = None
    notes: Optional[str] = None


class MealOrderRead(MealOrderBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    status: MealStatus
    unit_price: Decimal
    total_amount: Decimal
    ordered_at: datetime
    served_at: Optional[datetime] = None
    ordered_by_staff_id: Optional[int] = None
    served_by_staff_id: Optional[int] = None
    invoice_item_id: Optional[int] = None
    
    # Nested objects for detail views
    meal_type_name: Optional[str] = None
    patient_name: Optional[str] = None


class MealOrderListResponse(BaseModel):
    success: bool = True
    message: str = "Meal orders fetched successfully."
    items: list[MealOrderRead]
    count: int
    meta: dict


class MealOrderActionResponse(BaseModel):
    success: bool = True
    message: str
    meal_order: MealOrderRead
