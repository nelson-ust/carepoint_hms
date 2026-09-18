# app/schemas/home_orders_schemas.py
from __future__ import annotations

"""Schemas for home lab orders and home medication orders/delivery."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import HomeLabOrderStatus, HomeMedicationStatus, HomeVisitPriority


# ===========================================================================
# Home Lab Orders
# ===========================================================================
class HomeLabItemCreateSchema(BaseModel):
    lab_test_catalog_id: int


class HomeLabOrderCreateSchema(BaseModel):
    patient_id: int
    home_visit_id: Optional[int] = None
    care_plan_id: Optional[int] = None
    priority: HomeVisitPriority = HomeVisitPriority.NORMAL
    clinical_note: Optional[str] = None
    collection_address: Optional[str] = None
    scheduled_collection_at: Optional[datetime] = None
    items: list[HomeLabItemCreateSchema] = Field(min_length=1)


class HomeLabStatusChangeSchema(BaseModel):
    status: HomeLabOrderStatus
    note: Optional[str] = None


class HomeLabResultEntrySchema(BaseModel):
    result_value: Optional[str] = None
    result_unit: Optional[str] = None
    reference_range: Optional[str] = None
    is_abnormal: bool = False
    interpretation: Optional[str] = None


class HomeLabItemReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    home_lab_order_id: int
    lab_test_catalog_id: int
    status: str
    result_value: Optional[str] = None
    result_unit: Optional[str] = None
    reference_range: Optional[str] = None
    is_abnormal: bool = False
    interpretation: Optional[str] = None
    resulted_at: Optional[datetime] = None
    test_name: Optional[str] = None
    test_code: Optional[str] = None


class HomeLabOrderReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_no: str
    patient_id: int
    home_visit_id: Optional[int] = None
    care_plan_id: Optional[int] = None
    ordered_by_staff_id: Optional[int] = None
    status: str
    priority: str
    clinical_note: Optional[str] = None
    collection_address: Optional[str] = None
    scheduled_collection_at: Optional[datetime] = None
    sample_collected_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    resulted_at: Optional[datetime] = None
    ordered_at: datetime
    patient_name: Optional[str] = None
    items: list[HomeLabItemReadSchema] = []
    created_at: Optional[datetime] = None


class HomeLabOrderActionResponse(BaseModel):
    success: bool = True
    message: str
    order: HomeLabOrderReadSchema


class HomeLabOrderListResponse(BaseModel):
    success: bool = True
    message: str = "Home lab orders fetched successfully."
    items: list[HomeLabOrderReadSchema]
    count: int
    meta: dict


# ===========================================================================
# Home Medication Orders (dispense + delivery)
# ===========================================================================
class HomeMedItemCreateSchema(BaseModel):
    drug_id: int
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    route: Optional[str] = None
    quantity: Decimal = Decimal("1")
    instructions: Optional[str] = None


class HomeMedicationOrderCreateSchema(BaseModel):
    patient_id: int
    home_visit_id: Optional[int] = None
    care_plan_id: Optional[int] = None
    note: Optional[str] = None
    delivery_address: Optional[str] = None
    items: list[HomeMedItemCreateSchema] = Field(min_length=1)


class HomeMedDispenseSchema(BaseModel):
    dispensed_by_staff_id: Optional[int] = None
    note: Optional[str] = None
    # optional per-item dispensed quantities: {item_id: qty}
    quantities: Optional[dict[int, Decimal]] = None


class HomeMedDeliverySchema(BaseModel):
    courier_name: Optional[str] = None
    delivery_tracking_ref: Optional[str] = None
    delivered_by_staff_id: Optional[int] = None
    note: Optional[str] = None


class HomeMedStatusChangeSchema(BaseModel):
    status: HomeMedicationStatus
    note: Optional[str] = None


class HomeMedItemReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    home_medication_order_id: int
    drug_id: int
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    route: Optional[str] = None
    quantity: Decimal
    quantity_dispensed: Decimal
    instructions: Optional[str] = None
    drug_name: Optional[str] = None
    drug_strength: Optional[str] = None


class HomeMedicationOrderReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_no: str
    patient_id: int
    home_visit_id: Optional[int] = None
    care_plan_id: Optional[int] = None
    prescribed_by_staff_id: Optional[int] = None
    status: str
    note: Optional[str] = None
    delivery_address: Optional[str] = None
    dispensed_by_staff_id: Optional[int] = None
    dispensed_at: Optional[datetime] = None
    courier_name: Optional[str] = None
    delivery_tracking_ref: Optional[str] = None
    delivered_at: Optional[datetime] = None
    prescribed_at: datetime
    patient_name: Optional[str] = None
    items: list[HomeMedItemReadSchema] = []
    created_at: Optional[datetime] = None


class HomeMedicationOrderActionResponse(BaseModel):
    success: bool = True
    message: str
    order: HomeMedicationOrderReadSchema


class HomeMedicationOrderListResponse(BaseModel):
    success: bool = True
    message: str = "Home medication orders fetched successfully."
    items: list[HomeMedicationOrderReadSchema]
    count: int
    meta: dict
