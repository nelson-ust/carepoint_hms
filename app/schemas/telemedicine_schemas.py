# app/schemas/telemedicine_schemas.py
from __future__ import annotations

"""Pydantic schemas for the Telemedicine module."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    TelemedicineModality,
    TelemedicineProvider,
    TelemedicineSenderRole,
    TelemedicineStatus,
)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
class TelemedicineSessionCreateSchema(BaseModel):
    patient_id: int
    clinician_staff_id: Optional[int] = None
    appointment_id: Optional[int] = None
    home_visit_id: Optional[int] = None
    care_plan_id: Optional[int] = None
    modality: TelemedicineModality = TelemedicineModality.VIDEO
    reason: Optional[str] = None
    provider: TelemedicineProvider = TelemedicineProvider.JITSI
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None


class TelemedicineSessionUpdateSchema(BaseModel):
    clinician_staff_id: Optional[int] = None
    appointment_id: Optional[int] = None
    home_visit_id: Optional[int] = None
    care_plan_id: Optional[int] = None
    modality: Optional[TelemedicineModality] = None
    reason: Optional[str] = None
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None


class TelemedicineNoteUpsertSchema(BaseModel):
    subjective_note: Optional[str] = None
    objective_note: Optional[str] = None
    assessment_note: Optional[str] = None
    plan_note: Optional[str] = None
    summary: Optional[str] = None
    follow_up_required: Optional[bool] = None
    follow_up_notes: Optional[str] = None


class TelemedicineCompleteSchema(TelemedicineNoteUpsertSchema):
    """Finish a session, optionally persisting final SOAP notes in one call."""


class TelemedicineCancelSchema(BaseModel):
    reason: Optional[str] = None


class TelemedicineSessionReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_code: str
    patient_id: int
    clinician_staff_id: Optional[int] = None
    appointment_id: Optional[int] = None
    home_visit_id: Optional[int] = None
    care_plan_id: Optional[int] = None
    modality: str
    status: str
    reason: Optional[str] = None
    provider: str
    room_name: str
    room_url: Optional[str] = None
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None
    waiting_since: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    patient_joined_at: Optional[datetime] = None
    clinician_joined_at: Optional[datetime] = None
    subjective_note: Optional[str] = None
    objective_note: Optional[str] = None
    assessment_note: Optional[str] = None
    plan_note: Optional[str] = None
    summary: Optional[str] = None
    follow_up_required: bool = False
    follow_up_notes: Optional[str] = None
    cancellation_reason: Optional[str] = None
    # denormalized (populated by service)
    patient_name: Optional[str] = None
    clinician_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Join (returns the connection details the client needs to enter the room)
# ---------------------------------------------------------------------------
class TelemedicineJoinInfoSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_code: str
    provider: str
    modality: str
    status: str
    room_name: str
    room_url: Optional[str] = None
    domain: str = "meet.jit.si"
    display_name: Optional[str] = None
    is_clinician: bool = False


# ---------------------------------------------------------------------------
# Messages (in-session secure chat)
# ---------------------------------------------------------------------------
class TelemedicineMessageCreateSchema(BaseModel):
    body: str = Field(min_length=1)
    attachment_key: Optional[str] = None
    attachment_name: Optional[str] = None


class TelemedicineMessageReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    sender_user_id: Optional[int] = None
    sender_role: str
    sender_name: Optional[str] = None
    body: str
    attachment_key: Optional[str] = None
    attachment_name: Optional[str] = None
    sent_at: datetime


# ---------------------------------------------------------------------------
# Response wrappers
# ---------------------------------------------------------------------------
class TelemedicineActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    session: TelemedicineSessionReadSchema


class TelemedicineListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Telemedicine sessions fetched successfully."
    items: list[TelemedicineSessionReadSchema]
    count: int
    meta: dict


class TelemedicineJoinResponseSchema(BaseModel):
    success: bool = True
    message: str = "Join details."
    join: TelemedicineJoinInfoSchema
    session: TelemedicineSessionReadSchema


class TelemedicineMessageResponseSchema(BaseModel):
    success: bool = True
    message: str = "Message sent."
    chat_message: TelemedicineMessageReadSchema


class TelemedicineMessageListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Messages fetched successfully."
    items: list[TelemedicineMessageReadSchema]
    count: int
    meta: dict
