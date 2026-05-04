from __future__ import annotations

"""
app.schemas.service_delivery_point_schemas

Pydantic schemas for service delivery point configuration and retrieval.

Purpose
-------
This module defines request and response schemas for:

- creating service delivery points
- updating service delivery points
- retrieving service delivery point details
- listing service delivery points for routing/queue selection
- filtering active service delivery points for operations

Domain summary
--------------
A ServiceDeliveryPoint represents an operational workstation or care-routing
destination such as:

- registration desk
- triage point
- clinic / consultation room
- laboratory desk
- pharmacy counter
- cashier / billing desk
- ward station
- emergency point

These records are used by visits, appointments, queue tickets, and runtime
visit flow steps to determine where a patient should be routed next.

Typical usage
-------------
- Appointments may be booked against a service delivery point.
- Visits may start at a service delivery point.
- Queue tickets are issued within the context of a service delivery point.
- Visit flow steps reference service delivery points as runtime care stages.
"""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================
# SHARED / LITE SCHEMAS
# ============================================================

class ServiceDeliveryPointLiteSchema(BaseModel):
    """
    Lightweight service delivery point representation for nested responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    service_point_type: str
    department_id: Optional[int] = None
    location_description: Optional[str] = None
    queue_prefix: Optional[str] = None
    supports_appointments: bool
    supports_walk_in: bool
    is_active: bool = True


# ============================================================
# BASE SCHEMA
# ============================================================

class ServiceDeliveryPointBaseSchema(BaseModel):
    """
    Base shared fields for service delivery point create/update operations.
    """

    name: str = Field(..., min_length=1, max_length=150)
    code: str = Field(..., min_length=1, max_length=100)
    service_point_type: str = Field(..., min_length=1, max_length=100)

    department_id: Optional[int] = Field(
        None,
        description="Owning department/unit identifier if applicable.",
    )
    location_description: Optional[str] = Field(
        None,
        description="Physical or operational location description.",
    )
    queue_prefix: Optional[str] = Field(
        None,
        max_length=20,
        description="Short prefix used for queue-number generation.",
    )
    supports_appointments: bool = Field(
        default=False,
        description="Whether appointment booking is supported for this point.",
    )
    supports_walk_in: bool = Field(
        default=True,
        description="Whether walk-in routing is supported for this point.",
    )
    is_active: bool = Field(
        default=True,
        description="Operational activation flag.",
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty.")
        return normalized

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("code cannot be empty.")
        return normalized

    @field_validator("service_point_type")
    @classmethod
    def normalize_service_point_type(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("service_point_type cannot be empty.")
        return normalized

    @field_validator("location_description")
    @classmethod
    def normalize_location_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("queue_prefix")
    @classmethod
    def normalize_queue_prefix(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None


# ============================================================
# CREATE / UPDATE SCHEMAS
# ============================================================

class ServiceDeliveryPointCreateSchema(ServiceDeliveryPointBaseSchema):
    """
    Schema for creating a service delivery point.
    """
    pass


class ServiceDeliveryPointUpdateSchema(BaseModel):
    """
    Schema for partially updating a service delivery point.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=150)
    code: Optional[str] = Field(None, min_length=1, max_length=100)
    service_point_type: Optional[str] = Field(None, min_length=1, max_length=100)

    department_id: Optional[int] = None
    location_description: Optional[str] = None
    queue_prefix: Optional[str] = Field(None, max_length=20)
    supports_appointments: Optional[bool] = None
    supports_walk_in: Optional[bool] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty.")
        return normalized

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("code cannot be empty.")
        return normalized

    @field_validator("service_point_type")
    @classmethod
    def normalize_service_point_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("service_point_type cannot be empty.")
        return normalized

    @field_validator("location_description")
    @classmethod
    def normalize_location_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("queue_prefix")
    @classmethod
    def normalize_queue_prefix(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None


# ============================================================
# READ SCHEMAS
# ============================================================

class ServiceDeliveryPointReadSchema(BaseModel):
    """
    Full read schema for service delivery points.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    service_point_type: str

    department_id: Optional[int] = None
    location_description: Optional[str] = None
    queue_prefix: Optional[str] = None
    supports_appointments: bool
    supports_walk_in: bool
    is_active: bool

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ServiceDeliveryPointListItemSchema(BaseModel):
    """
    List item schema for service delivery point list views.
    """

    id: int
    name: str
    code: str
    service_point_type: str
    department_id: Optional[int] = None
    queue_prefix: Optional[str] = None
    supports_appointments: bool
    supports_walk_in: bool
    is_active: bool


class ServiceDeliveryPointListResponseSchema(BaseModel):
    """
    Paginated list response for service delivery points.
    """

    success: bool = True
    message: str = "Service delivery points fetched successfully."
    items: list[ServiceDeliveryPointListItemSchema]
    count: int
    meta: dict[str, Any]


# ============================================================
# FILTER / QUERY SCHEMAS
# ============================================================

class ServiceDeliveryPointFilterSchema(BaseModel):
    """
    Optional filter schema for querying service delivery points.
    """

    name: Optional[str] = None
    code: Optional[str] = None
    service_point_type: Optional[str] = None
    department_id: Optional[int] = None
    supports_appointments: Optional[bool] = None
    supports_walk_in: Optional[bool] = None
    is_active: Optional[bool] = None

    @field_validator("name", "code", "service_point_type")
    @classmethod
    def normalize_text_filters(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


# ============================================================
# ACTION RESPONSE SCHEMAS
# ============================================================

class ServiceDeliveryPointActionResponseSchema(BaseModel):
    """
    Generic action response for service delivery point mutations.
    """

    success: bool = True
    message: str


class ServiceDeliveryPointStatusToggleSchema(BaseModel):
    """
    Schema for explicitly activating or deactivating a service delivery point.
    """

    is_active: bool