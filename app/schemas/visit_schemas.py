from __future__ import annotations

"""
app.schemas.visit_schemas

Pydantic schemas for visit initiation and runtime operational care workflow.

Purpose
-------
This module defines request and response schemas for:

- initiating a visit for an existing or newly registered patient
- selecting or inheriting the first service delivery point
- optionally using a reusable visit flow template
- creating runtime visit flow steps
- creating queue tickets for service delivery points
- supporting fast-track urgent/emergency handling
- supporting rerouting, skipping, and runtime flow adjustment

Requirements coverage
---------------------
UC-02 - Initiate Visit for Existing or New Patient

Normal flow supported by these schemas:
1. Retrieve patient record
2. Create visit with visit code and visit reason
3. Set first service delivery point or use appointment context
4. Create first flow step and queue ticket for the selected point
5. Mark visit as initiated or waiting

Alternate flow supported by these schemas:
- Visit can inherit booked service delivery point from appointment
- Priority can be set to urgent or emergency
- Patient can be fast-tracked
- Runtime flow can be adjusted dynamically
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================
# EMBEDDED / LITE SCHEMAS
# ============================================================

class PatientVisitLiteSchema(BaseModel):
    """
    Lightweight patient representation for visit responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    hospital_number: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    gender: Optional[str] = None
    phone_number: Optional[str] = None


class AppointmentVisitLiteSchema(BaseModel):
    """
    Lightweight appointment representation for visit responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    appointment_code: str
    scheduled_start_at: datetime
    scheduled_end_at: Optional[datetime] = None
    reason: Optional[str] = None
    status: Optional[str] = None
    patient_id: int
    service_delivery_point_id: Optional[int] = None
    staff_profile_id: Optional[int] = None


class ServiceDeliveryPointLiteSchema(BaseModel):
    """
    Lightweight service delivery point representation.
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


# ============================================================
# VISIT FLOW TEMPLATE SCHEMAS
# ============================================================

class VisitFlowTemplateStepReadSchema(BaseModel):
    """
    Read schema for reusable visit flow template steps.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: int
    service_delivery_point_id: int
    step_order: int
    is_required: bool
    notes: Optional[str] = None
    service_delivery_point: Optional[ServiceDeliveryPointLiteSchema] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class VisitFlowTemplateReadSchema(BaseModel):
    """
    Read schema for a reusable visit flow template.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: Optional[str] = None
    steps: list[VisitFlowTemplateStepReadSchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================
# FLOW STEP / QUEUE SCHEMAS
# ============================================================

class VisitFlowStepBaseSchema(BaseModel):
    """
    Base schema for runtime visit flow steps.
    """

    service_delivery_point_id: int = Field(..., gt=0)
    step_order: int = Field(..., ge=1)
    status: Optional[str] = Field(None, max_length=50)
    is_current: bool = False
    is_required: bool = True
    is_skipped: bool = False
    routed_by_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class VisitFlowStepCreateSchema(VisitFlowStepBaseSchema):
    """
    Schema for explicitly adding a runtime visit flow step.
    """
    pass


class VisitFlowStepUpdateSchema(BaseModel):
    """
    Schema for updating a runtime visit flow step.

    Supports:
    - marking current step
    - completing step
    - skipping step
    - rerouting
    """

    service_delivery_point_id: Optional[int] = None
    step_order: Optional[int] = Field(None, ge=1)
    status: Optional[str] = Field(None, max_length=50)
    is_current: Optional[bool] = None
    is_required: Optional[bool] = None
    is_skipped: Optional[bool] = None
    routed_by_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class VisitFlowStepReadSchema(BaseModel):
    """
    Read schema for runtime visit flow steps.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    service_delivery_point_id: int
    step_order: int
    status: str
    is_current: bool
    is_required: bool
    is_skipped: bool
    routed_by_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    service_delivery_point: Optional[ServiceDeliveryPointLiteSchema] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class QueueTicketBaseSchema(BaseModel):
    """
    Base schema for queue ticket data.
    """

    service_delivery_point_id: int = Field(..., gt=0)
    queue_number: str = Field(..., min_length=1, max_length=100)
    queue_position: Optional[int] = Field(None, ge=1)
    status: Optional[str] = Field(None, max_length=50)
    called_at: Optional[datetime] = None
    service_started_at: Optional[datetime] = None
    service_ended_at: Optional[datetime] = None
    transferred_from_ticket_id: Optional[int] = None

    @field_validator("queue_number")
    @classmethod
    def normalize_queue_number(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("queue_number cannot be empty.")
        return normalized

    @field_validator("status")
    @classmethod
    def normalize_queue_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None


class QueueTicketCreateSchema(QueueTicketBaseSchema):
    """
    Schema for explicitly creating a queue ticket.
    """

    visit_flow_step_id: Optional[int] = None
    patient_id: int = Field(..., gt=0)
    visit_id: int = Field(..., gt=0)


class QueueTicketUpdateSchema(BaseModel):
    """
    Schema for updating queue ticket state.
    """

    queue_position: Optional[int] = Field(None, ge=1)
    status: Optional[str] = Field(None, max_length=50)
    called_at: Optional[datetime] = None
    service_started_at: Optional[datetime] = None
    service_ended_at: Optional[datetime] = None
    transferred_from_ticket_id: Optional[int] = None

    @field_validator("status")
    @classmethod
    def normalize_queue_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None


class QueueTicketReadSchema(BaseModel):
    """
    Read schema for queue tickets.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    visit_flow_step_id: Optional[int] = None
    patient_id: int
    service_delivery_point_id: int
    queue_number: str
    queue_position: Optional[int] = None
    status: str
    called_at: Optional[datetime] = None
    service_started_at: Optional[datetime] = None
    service_ended_at: Optional[datetime] = None
    transferred_from_ticket_id: Optional[int] = None
    service_delivery_point: Optional[ServiceDeliveryPointLiteSchema] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================
# VISIT CREATE / INITIATION SCHEMAS
# ============================================================

class VisitBaseSchema(BaseModel):
    """
    Base shared fields for visit creation/update.
    """

    patient_id: int = Field(..., gt=0)
    appointment_id: Optional[int] = None
    visit_reason: Optional[str] = None
    referred_from: Optional[str] = Field(None, max_length=150)
    priority: Optional[str] = Field(
        None,
        max_length=50,
        description="Examples: NORMAL, URGENT, EMERGENCY.",
    )
    status: Optional[str] = Field(
        None,
        max_length=50,
        description="Examples: INITIATED, WAITING, IN_PROGRESS.",
    )
    first_service_delivery_point_id: Optional[int] = Field(
        None,
        description="Required when not inheriting from appointment context or template.",
    )
    use_appointment_service_point: bool = Field(
        default=False,
        description="If true, derive first service point from appointment context.",
    )
    visit_flow_template_id: Optional[int] = Field(
        None,
        description="Optional reusable template to initialize visit flow.",
    )
    visit_date: Optional[datetime] = Field(
        None,
        description="Defaults to current datetime if omitted in service/repository layer.",
    )
    check_in_time: Optional[datetime] = None

    @field_validator("priority", "status")
    @classmethod
    def normalize_enum_like_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("referred_from", "visit_reason")
    @classmethod
    def normalize_text_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class VisitInitiateSchema(VisitBaseSchema):
    """
    Request schema for initiating a visit.

    Supports:
    - direct first service point selection
    - appointment-context inheritance
    - reusable visit flow template selection
    - first flow step creation
    - first queue ticket creation
    - urgent/emergency fast-track handling
    """

    create_first_flow_step: bool = Field(
        default=True,
        description="Create the first runtime visit flow step.",
    )
    create_queue_ticket: bool = Field(
        default=True,
        description="Create the first queue ticket for the selected service point.",
    )
    first_step_status: Optional[str] = Field(
        default="PENDING",
        max_length=50,
        description="Initial runtime status for the first visit flow step.",
    )
    first_queue_status: Optional[str] = Field(
        default="WAITING",
        max_length=50,
        description="Initial queue status.",
    )
    mark_visit_waiting: bool = Field(
        default=True,
        description="If true, visit may be marked WAITING after initiation.",
    )
    fast_track: bool = Field(
        default=False,
        description="If true, supports urgent/emergency fast-tracking.",
    )
    queue_position: Optional[int] = Field(
        None,
        ge=1,
        description="Optional explicitly assigned queue position.",
    )
    flow_step_notes: Optional[str] = None
    queue_notes: Optional[str] = None

    @field_validator("first_step_status", "first_queue_status")
    @classmethod
    def normalize_initial_statuses(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("flow_step_notes", "queue_notes")
    @classmethod
    def normalize_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class VisitRerouteSchema(BaseModel):
    """
    Schema for rerouting an active visit to a new service delivery point.

    Supports runtime care-path changes.
    """

    service_delivery_point_id: int = Field(..., gt=0)
    routed_by_id: Optional[int] = None
    reason: Optional[str] = None
    create_queue_ticket: bool = True
    queue_status: Optional[str] = Field(default="WAITING", max_length=50)
    queue_position: Optional[int] = Field(None, ge=1)
    mark_as_current: bool = True

    @field_validator("queue_status")
    @classmethod
    def normalize_queue_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class VisitUpdateSchema(BaseModel):
    """
    Partial update schema for visit records.
    """

    appointment_id: Optional[int] = None
    visit_reason: Optional[str] = None
    referred_from: Optional[str] = Field(None, max_length=150)
    priority: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(None, max_length=50)
    first_service_delivery_point_id: Optional[int] = None
    current_service_delivery_point_id: Optional[int] = None
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None

    @field_validator("priority", "status")
    @classmethod
    def normalize_enum_like_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("visit_reason", "referred_from")
    @classmethod
    def normalize_text_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


# ============================================================
# VISIT READ SCHEMAS
# ============================================================

class VisitReadSchema(BaseModel):
    """
    Standard read schema for visit records.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    appointment_id: Optional[int] = None
    visit_code: str
    visit_date: datetime
    status: str
    priority: str
    first_service_delivery_point_id: Optional[int] = None
    current_service_delivery_point_id: Optional[int] = None
    referred_from: Optional[str] = None
    visit_reason: Optional[str] = None
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class VisitDetailedReadSchema(VisitReadSchema):
    """
    Detailed read schema for visit records.

    Includes:
    - patient
    - appointment
    - first/current service points
    - runtime flow steps
    - queue tickets
    """

    patient: Optional[PatientVisitLiteSchema] = None
    appointment: Optional[AppointmentVisitLiteSchema] = None
    first_service_delivery_point: Optional[ServiceDeliveryPointLiteSchema] = None
    current_service_delivery_point: Optional[ServiceDeliveryPointLiteSchema] = None
    flow_steps: list[VisitFlowStepReadSchema] = Field(default_factory=list)
    queue_tickets: list[QueueTicketReadSchema] = Field(default_factory=list)


class VisitInitiationResultSchema(BaseModel):
    """
    Response schema for successful visit initiation.

    Main UC-02 response schema.
    """

    success: bool = True
    message: str
    visit: VisitDetailedReadSchema
    first_flow_step: Optional[VisitFlowStepReadSchema] = None
    first_queue_ticket: Optional[QueueTicketReadSchema] = None
    applied_template: Optional[VisitFlowTemplateReadSchema] = None
    inherited_from_appointment: bool = False
    fast_tracked: bool = False


class VisitRerouteResultSchema(BaseModel):
    """
    Response schema for visit rerouting.
    """

    success: bool = True
    message: str
    visit: VisitDetailedReadSchema
    new_flow_step: VisitFlowStepReadSchema
    new_queue_ticket: Optional[QueueTicketReadSchema] = None


class VisitListItemSchema(BaseModel):
    """
    List item schema for visit list views.
    """

    id: int
    patient_id: int
    appointment_id: Optional[int] = None
    visit_code: str
    visit_date: datetime
    status: str
    priority: str
    first_service_delivery_point_id: Optional[int] = None
    current_service_delivery_point_id: Optional[int] = None
    visit_reason: Optional[str] = None


class VisitListResponseSchema(BaseModel):
    """
    Paginated visit list response schema.
    """

    success: bool = True
    message: str = "Visits fetched successfully."
    items: list[VisitListItemSchema]
    count: int
    meta: dict


class VisitActionResponseSchema(BaseModel):
    """
    Generic action response for visit-related mutations.
    """

    success: bool = True
    message: str