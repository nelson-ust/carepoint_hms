# app/schemas/billing_schemas.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ------- BILLABLE SERVICE -------

class BillableServiceCreateSchema(BaseModel):
    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    default_price: Decimal = Decimal("0")
    description: Optional[str] = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "_")


class BillableServiceUpdateSchema(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    default_price: Optional[Decimal] = None
    description: Optional[str] = None


class BillableServiceReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    category: Optional[str] = None
    default_price: Decimal
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BillableServiceListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Billable services fetched successfully."
    items: list[BillableServiceReadSchema]
    count: int
    meta: dict


# ------- BILLING / BILLING ITEM -------

class BillingItemCreateSchema(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=255)
    service_code: Optional[str] = Field(None, max_length=100)
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    billable_service_id: Optional[int] = None
    source_reference: Optional[str] = Field(None, max_length=100)


class BillingCreateSchema(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    patient_insurance_id: Optional[int] = None
    notes: Optional[str] = None
    items: list[BillingItemCreateSchema] = Field(default_factory=list)


class BillingItemReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    billing_id: int
    billable_service_id: Optional[int] = None
    service_name: str
    service_code: Optional[str] = None
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    line_total: Decimal
    source_reference: Optional[str] = None
    created_at: Optional[datetime] = None


class BillingReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    visit_id: Optional[int] = None
    patient_insurance_id: Optional[int] = None
    billing_no: str
    billing_date: datetime
    status: Optional[str] = None
    gross_amount: Decimal
    discount_amount: Decimal
    net_amount: Decimal
    notes: Optional[str] = None
    items: list[BillingItemReadSchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BillingListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Billings fetched successfully."
    items: list[BillingReadSchema]
    count: int
    meta: dict


class BillingActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    billing: BillingReadSchema


class BillableServiceActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    service: BillableServiceReadSchema
