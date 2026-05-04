# app/schemas/lab_order_schema.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LabOrderItemCreateSchema(BaseModel):
    lab_test_catalog_id: int
    note: Optional[str] = Field(None, max_length=500)


class LabOrderCreateSchema(BaseModel):
    visit_id: int
    consultation_id: Optional[int] = None
    ordered_by_staff_id: Optional[int] = None
    clinical_note: Optional[str] = Field(None, max_length=4000)
    items: list[LabOrderItemCreateSchema] = Field(..., min_length=1)
    auto_capture_charge: bool = Field(default=True, description="Create billing items for the ordered tests.")
    route_to_lab_service_delivery_point_id: Optional[int] = Field(
        None, description="Optional lab SDP to route the patient to immediately."
    )
    route_to_cashier_service_delivery_point_id: Optional[int] = Field(
        None, description="Optional cashier SDP for pre-paid policies."
    )


class LabOrderItemSpecimenSchema(BaseModel):
    specimen_id: Optional[str] = Field(None, max_length=100)
    collected_by_staff_id: Optional[int] = None
    note: Optional[str] = Field(None, max_length=500)


class LabOrderCancelSchema(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


class LabOrderItemReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lab_order_id: int
    lab_test_catalog_id: int
    status: str
    specimen_id: Optional[str] = None
    sample_collected_at: Optional[datetime] = None
    collected_by_staff_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LabOrderReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    consultation_id: Optional[int] = None
    ordered_by_staff_id: Optional[int] = None
    order_no: str
    status: str
    clinical_note: Optional[str] = None
    ordered_at: datetime
    items: list[LabOrderItemReadSchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LabOrderActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    lab_order: LabOrderReadSchema


class LabOrderListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Lab orders fetched successfully."
    items: list[LabOrderReadSchema]
    count: int
    meta: dict
