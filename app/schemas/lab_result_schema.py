# app/schemas/lab_result_schema.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LabResultEnterSchema(BaseModel):
    lab_order_item_id: int
    entered_by_staff_id: Optional[int] = None
    result_value: Optional[str] = Field(None, max_length=255)
    result_text: Optional[str] = Field(None, max_length=4000)
    unit_of_measure: Optional[str] = Field(None, max_length=50)
    reference_range: Optional[str] = Field(None, max_length=255)
    interpretation: Optional[str] = Field(None, max_length=2000)


class LabResultUpdateSchema(BaseModel):
    result_value: Optional[str] = Field(None, max_length=255)
    result_text: Optional[str] = Field(None, max_length=4000)
    unit_of_measure: Optional[str] = Field(None, max_length=50)
    reference_range: Optional[str] = Field(None, max_length=255)
    interpretation: Optional[str] = Field(None, max_length=2000)


class LabResultVerifySchema(BaseModel):
    verified_by_staff_id: Optional[int] = None
    verification_note: Optional[str] = Field(None, max_length=2000)


class LabResultReleaseSchema(BaseModel):
    release_note: Optional[str] = Field(None, max_length=2000)
    notify_clinician: bool = True
    route_to_service_delivery_point_id: Optional[int] = Field(
        None,
        description=(
            "Optional SDP to route the visit back to once the result is released "
            "(typically the clinic SDP that ordered the test)."
        ),
    )


class LabResultReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lab_order_item_id: int
    entered_by_staff_id: Optional[int] = None
    verified_by_staff_id: Optional[int] = None
    result_status: str
    result_value: Optional[str] = None
    result_text: Optional[str] = None
    unit_of_measure: Optional[str] = None
    reference_range: Optional[str] = None
    interpretation: Optional[str] = None
    entered_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    released_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LabResultActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    result: LabResultReadSchema


class LabResultListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Lab results fetched successfully."
    items: list[LabResultReadSchema]
    count: int
    meta: dict
