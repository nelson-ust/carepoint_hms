"""
Doctor calendar / availability / slot endpoints.

Two audiences:

* **Tenant admins / scheduling staff** — define weekly availability,
  block leave, materialise slots.
* **Patients (or front-desk on their behalf)** — discover open slots,
  see calendar views, reserve a slot through the appointment service.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser, CurrentActiveUser
from app.core.enums import (
    AppointmentSlotStatus,
    DoctorAvailabilityType,
)
from app.services.doctor_calendar_service import DoctorCalendarService


router = APIRouter(prefix="/doctor-calendar", tags=["Doctor Calendar"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TemplateCreateSchema(BaseModel):
    staff_profile_id: int
    weekday: int = Field(..., ge=0, le=6, description="0=Mon … 6=Sun")
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    slot_duration_minutes: int = Field(30, ge=5, le=240)
    max_patients_per_slot: int = Field(1, ge=1, le=20)
    appointment_type: Optional[str] = None
    facility_id: Optional[int] = None
    service_delivery_point_id: Optional[int] = None
    timezone_name: Optional[str] = None
    notes: Optional[str] = None


class TemplateReadSchema(BaseModel):
    id: int
    staff_profile_id: int
    weekday: int
    start_time: str
    end_time: str
    slot_duration_minutes: int
    max_patients_per_slot: int
    appointment_type: Optional[str] = None
    facility_id: Optional[int] = None
    service_delivery_point_id: Optional[int] = None
    is_active: bool
    timezone: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TimeOffCreateSchema(BaseModel):
    staff_profile_id: int
    starts_at: datetime
    ends_at: datetime
    availability_type: DoctorAvailabilityType = DoctorAvailabilityType.BLOCKED
    reason: Optional[str] = None
    approved_by_user_id: Optional[int] = None


class TimeOffReadSchema(BaseModel):
    id: int
    staff_profile_id: int
    starts_at: datetime
    ends_at: datetime
    availability_type: DoctorAvailabilityType
    reason: Optional[str] = None
    approved_by_user_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class MaterialiseSlotsSchema(BaseModel):
    staff_profile_id: int
    from_date: date
    through_date: date


class SlotReadSchema(BaseModel):
    id: int
    staff_profile_id: int
    facility_id: Optional[int] = None
    service_delivery_point_id: Optional[int] = None
    appointment_id: Optional[int] = None
    starts_at: datetime
    ends_at: datetime
    capacity: int
    booked_count: int
    appointment_type: Optional[str] = None
    status: AppointmentSlotStatus
    block_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


def _service(db: Annotated[Session, Depends(get_db)]) -> DoctorCalendarService:
    return DoctorCalendarService(db)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


@router.get(
    "/templates",
    response_model=list[TemplateReadSchema],
    summary="List availability templates",
)
def list_templates(
    _: AdminUser,
    service: Annotated[DoctorCalendarService, Depends(_service)],
    staff_profile_id: Optional[int] = None,
    only_active: bool = False,
):
    return service.list_templates(staff_profile_id=staff_profile_id, only_active=only_active)


@router.post(
    "/templates",
    response_model=TemplateReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a weekly availability template",
)
def create_template(
    payload: TemplateCreateSchema,
    _: AdminUser,
    service: Annotated[DoctorCalendarService, Depends(_service)],
):
    return service.create_template(**payload.model_dump())


@router.post(
    "/templates/{template_id}/deactivate",
    response_model=TemplateReadSchema,
    summary="Deactivate an availability template",
)
def deactivate_template(
    template_id: int,
    _: AdminUser,
    service: Annotated[DoctorCalendarService, Depends(_service)],
):
    return service.deactivate_template(template_id)


# ---------------------------------------------------------------------------
# Time off
# ---------------------------------------------------------------------------


@router.post(
    "/time-off",
    response_model=TimeOffReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Block a doctor's calendar (leave / holiday / unavailable)",
)
def add_time_off(
    payload: TimeOffCreateSchema,
    _: AdminUser,
    service: Annotated[DoctorCalendarService, Depends(_service)],
):
    return service.add_time_off(**payload.model_dump())


# ---------------------------------------------------------------------------
# Slot materialisation + queries
# ---------------------------------------------------------------------------


@router.post(
    "/slots/materialise",
    summary="Materialise concrete slots from active templates",
)
def materialise_slots(
    payload: MaterialiseSlotsSchema,
    _: AdminUser,
    service: Annotated[DoctorCalendarService, Depends(_service)],
):
    created = service.materialise_slots(
        staff_profile_id=payload.staff_profile_id,
        from_date=payload.from_date,
        through_date=payload.through_date,
    )
    return {"created": created}


@router.get(
    "/slots",
    response_model=list[SlotReadSchema],
    summary="Calendar view — daily / weekly / monthly slot listing",
)
def list_slots(
    _: CurrentActiveUser,
    service: Annotated[DoctorCalendarService, Depends(_service)],
    staff_profile_id: Optional[int] = None,
    from_dt: datetime = ...,  # required
    to_dt: datetime = ...,    # required
    appointment_type: Optional[str] = None,
    only_open: bool = False,
):
    return service.slots_in_range(
        staff_profile_id=staff_profile_id,
        from_dt=from_dt,
        to_dt=to_dt,
        appointment_type=appointment_type,
        only_open=only_open,
    )


@router.get(
    "/workload/{staff_profile_id}",
    summary="Daily workload counters for a doctor",
)
def doctor_workload(
    staff_profile_id: int,
    on_date: date,
    _: CurrentActiveUser,
    service: Annotated[DoctorCalendarService, Depends(_service)],
):
    return service.doctor_workload(staff_profile_id=staff_profile_id, on_date=on_date)


@router.post(
    "/slots/{slot_id}/reserve",
    response_model=SlotReadSchema,
    summary="Reserve a slot for an appointment (used by the AppointmentService)",
)
def reserve_slot(
    slot_id: int,
    appointment_id: int,
    _: AdminUser,
    service: Annotated[DoctorCalendarService, Depends(_service)],
):
    return service.reserve_slot(slot_id=slot_id, appointment_id=appointment_id)


@router.post(
    "/slots/{slot_id}/release",
    response_model=SlotReadSchema,
    summary="Release a slot (cancellation / reschedule)",
)
def release_slot(
    slot_id: int,
    _: AdminUser,
    service: Annotated[DoctorCalendarService, Depends(_service)],
):
    return service.release_slot(slot_id=slot_id)
