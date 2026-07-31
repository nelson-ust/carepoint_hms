# app/schemas/queue_schema.py
from __future__ import annotations

"""
Pydantic schemas for queue tickets and service-point worklists.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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

    # Demographic Context (Populated via model_validator)
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    hospital_number: Optional[str] = None

    # Extended info for providers
    previous_steps: list[QueueTicketPreviousStepSchema] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def resolve_patient_details(cls, data: Any) -> Any:
        if hasattr(data, "patient") and data.patient:
            data.patient_name = f"{data.patient.first_name} {data.patient.last_name}"
            data.patient_phone = data.patient.phone_number
            data.hospital_number = data.patient.hospital_number
        return data


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


# ============================================================
# ACTION PAYLOADS (composite hand-off actions)
# ============================================================

class QueueTicketCompleteAndRouteSchema(BaseModel):
    """Complete the current ticket and queue the patient at the next SDP."""

    target_service_delivery_point_id: int = Field(
        ..., description="SDP the patient should be queued at next."
    )
    notes: Optional[str] = Field(None, max_length=500)


class QueueTicketCompleteAndEndVisitSchema(BaseModel):
    """Complete the current ticket and close the visit."""

    note: Optional[str] = Field(None, max_length=2000)


# ============================================================
# ANALYTICS
# ============================================================

class ServicePointQueueStatsSchema(BaseModel):
    """Aggregated queue statistics for one service delivery point."""

    service_delivery_point_id: int
    service_delivery_point_name: str
    service_delivery_point_code: Optional[str] = None

    waiting_now: int = 0
    called_now: int = 0
    serving_now: int = 0

    issued: int = 0
    served: int = 0
    missed: int = 0
    cancelled: int = 0
    transferred: int = 0

    avg_wait_minutes: Optional[float] = Field(
        None, description="Mean minutes from ticket creation to service start."
    )
    avg_service_minutes: Optional[float] = Field(
        None, description="Mean minutes from service start to service end."
    )
    no_show_rate: Optional[float] = Field(
        None, description="MISSED / (SERVED + MISSED), 0..1."
    )


class QueueStatsTotalsSchema(BaseModel):
    """Whole-facility totals for the requested window."""

    waiting_now: int = 0
    called_now: int = 0
    serving_now: int = 0
    issued: int = 0
    served: int = 0
    missed: int = 0
    cancelled: int = 0
    transferred: int = 0
    avg_wait_minutes: Optional[float] = None
    avg_service_minutes: Optional[float] = None
    no_show_rate: Optional[float] = None


class QueueStatsResponseSchema(BaseModel):
    success: bool = True
    message: str = "Queue statistics computed successfully."
    date_from: datetime
    date_to: datetime
    totals: QueueStatsTotalsSchema
    service_points: list[ServicePointQueueStatsSchema] = Field(default_factory=list)


# ============================================================
# WAITING-ROOM DISPLAY BOARD
# ============================================================

class DisplayBoardTicketSchema(BaseModel):
    """Minimal, privacy-safe ticket projection for public displays."""

    queue_number: str
    status: str
    called_at: Optional[datetime] = None


class DisplayBoardEntrySchema(BaseModel):
    """Now-serving snapshot for one service delivery point."""

    service_delivery_point_id: int
    service_delivery_point_name: str
    service_delivery_point_code: Optional[str] = None
    now_serving: list[DisplayBoardTicketSchema] = Field(default_factory=list)
    now_called: list[DisplayBoardTicketSchema] = Field(default_factory=list)
    next_waiting: list[DisplayBoardTicketSchema] = Field(default_factory=list)
    waiting_count: int = 0


class QueueDisplayBoardResponseSchema(BaseModel):
    success: bool = True
    message: str = "Display board fetched successfully."
    generated_at: datetime
    service_points: list[DisplayBoardEntrySchema] = Field(default_factory=list)
