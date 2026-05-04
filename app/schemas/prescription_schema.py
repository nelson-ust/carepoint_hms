# app/schemas/prescription_schema.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PrescriptionItemCreateSchema(BaseModel):
    drug_id: int
    dosage: Optional[str] = Field(None, max_length=100)
    frequency: Optional[str] = Field(None, max_length=100)
    duration: Optional[str] = Field(None, max_length=100)
    route: Optional[str] = Field(None, max_length=100)
    quantity_prescribed: Decimal = Field(..., gt=0)
    instructions: Optional[str] = Field(None, max_length=2000)


class PrescriptionItemUpdateSchema(BaseModel):
    dosage: Optional[str] = Field(None, max_length=100)
    frequency: Optional[str] = Field(None, max_length=100)
    duration: Optional[str] = Field(None, max_length=100)
    route: Optional[str] = Field(None, max_length=100)
    quantity_prescribed: Optional[Decimal] = None
    instructions: Optional[str] = Field(None, max_length=2000)


class PrescriptionCreateSchema(BaseModel):
    visit_id: int
    consultation_id: Optional[int] = None
    prescribed_by_staff_id: Optional[int] = None
    note: Optional[str] = Field(None, max_length=4000)
    items: list[PrescriptionItemCreateSchema] = Field(..., min_length=1)
    auto_capture_charge: bool = True
    route_to_pharmacy_service_delivery_point_id: Optional[int] = None
    route_to_cashier_service_delivery_point_id: Optional[int] = None


class PrescriptionCancelSchema(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


class PrescriptionItemReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prescription_id: int
    drug_id: int
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    route: Optional[str] = None
    quantity_prescribed: Decimal
    quantity_dispensed: Decimal
    instructions: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PrescriptionReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    consultation_id: Optional[int] = None
    prescribed_by_staff_id: Optional[int] = None
    prescription_no: str
    status: str
    note: Optional[str] = None
    prescribed_at: datetime
    items: list[PrescriptionItemReadSchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PrescriptionActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    prescription: PrescriptionReadSchema


class PrescriptionListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Prescriptions fetched successfully."
    items: list[PrescriptionReadSchema]
    count: int
    meta: dict
