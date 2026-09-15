# app/schemas/lab_order_schema.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    
    # Contextual fields
    test_name: Optional[str] = Field(None, description="Derived from lab_test_catalog.name")
    test_code: Optional[str] = Field(None, description="Derived from lab_test_catalog.code")

    @model_validator(mode="before")
    @classmethod
    def resolve_test_metadata(cls, data: Any) -> Any:
        if hasattr(data, "lab_test_catalog") and data.lab_test_catalog:
            # Inject metadata for the schema to pick up
            data.test_name = data.lab_test_catalog.name
            data.test_code = data.lab_test_catalog.code
        return data

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
    
    # Contextual fields
    patient_name: Optional[str] = None
    hospital_number: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_patient_metadata(cls, data: Any) -> Any:
        if hasattr(data, "visit") and data.visit and data.visit.patient:
            p = data.visit.patient
            data.patient_name = f"{p.first_name} {p.last_name}"
            data.hospital_number = p.hospital_number
        return data

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


# ---------------------------------------------------------------------------
# Hospital-wide lab result tracker
# ---------------------------------------------------------------------------

class LabOrderTrackItemSchema(BaseModel):
    """A single test line within a tracked lab order."""

    model_config = ConfigDict(from_attributes=True)

    item_id: int
    test: str
    item_status: str
    result_status: str
    released_at: Optional[datetime] = None


class LabOrderTrackRowSchema(BaseModel):
    """One lab order as seen from the cross-hospital tracker."""

    model_config = ConfigDict(from_attributes=True)

    order_id: int
    order_no: str
    status: str
    ordered_at: Optional[datetime] = None
    visit_id: Optional[int] = None
    patient_id: Optional[int] = None
    patient_name: str
    hospital_number: Optional[str] = None
    items: list[LabOrderTrackItemSchema] = Field(default_factory=list)
    report_available: bool = False


class LabOrderTrackResponseSchema(BaseModel):
    """Paginated tracker response."""

    total: int
    skip: int
    limit: int
    items: list[LabOrderTrackRowSchema] = Field(default_factory=list)
