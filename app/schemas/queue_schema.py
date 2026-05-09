# app/schemas/queue_schema.py
from __future__ import annotations

"""
Pydantic schemas for queue tickets and service-point worklists.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QueueTicketCreateSchema(BaseModel):
    """Create a queue ticket explicitly. Most callers use the visit flow service."""

    visit_id: int
    visit_flow_step_id: Optional[int] = None
    patient_id: int
    service_delivery_point_id: int
    queue_number: Optional[str] = None
    queue_position: Optional[int] = None
    status: str = "WAITING"

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: str) -> str:
        return value.strip().upper()


class QueueTicketCallSchema(BaseModel):
    """Mark a ticket as CALLED."""

    note: Optional[str] = Field(None, max_length=500)


class QueueTicketServeSchema(BaseModel):
    """Mark a ticket as SERVING (service started)."""

    note: Optional[str] = Field(None, max_length=500)


class QueueTicketCompleteSchema(BaseModel):
    """Mark a ticket as SERVED (service ended)."""

    note: Optional[str] = Field(None, max_length=500)


class QueueTicketTransferSchema(BaseModel):
    """Transfer a ticket to another service delivery point."""

    target_service_delivery_point_id: int
    reason: Optional[str] = Field(None, max_length=500)


class QueueTicketCancelSchema(BaseModel):
    """Cancel an outstanding ticket."""

    reason: Optional[str] = Field(None, max_length=500)


class QueueTicketPreviousStepSchema(BaseModel):
    """Summarizes a previous step in the patient's current visit."""

    service_delivery_point_id: int
    service_delivery_point_name: str
    status: str
    services_provided: list[str] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class QueueTicketReadSchema(BaseModel):
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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Extended info for providers
    previous_steps: list[QueueTicketPreviousStepSchema] = Field(default_factory=list)


class QueueTicketListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Queue tickets fetched successfully."
    items: list[QueueTicketReadSchema]
    count: int
    meta: dict


class QueueTicketActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    ticket: QueueTicketReadSchema


class ServicePointWorklistResponseSchema(BaseModel):
    """Worklist view for a service-point workstation."""

    success: bool = True
    message: str = "Worklist fetched successfully."
    service_delivery_point_id: int
    service_delivery_point_name: Optional[str] = None
    waiting: list[QueueTicketReadSchema] = Field(default_factory=list)
    serving: list[QueueTicketReadSchema] = Field(default_factory=list)
    served_today: int = 0
    cancelled_today: int = 0
