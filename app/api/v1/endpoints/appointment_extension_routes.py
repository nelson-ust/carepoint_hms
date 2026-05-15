"""
Endpoints for the additive scheduling features that sit alongside the
existing appointment_routes.py: reminder rules, recurrence, and
cancellation history.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser, CurrentActiveUser, require_plan_feature
from app.core.enums import (
    AppointmentRecurrence,
    AppointmentReminderRule,
)
from app.services.appointment_extension_service import (
    AppointmentExtensionService,
)


router = APIRouter(
    prefix="/appointment-scheduling",
    tags=["Appointment Scheduling Extensions"],
    dependencies=[Depends(require_plan_feature("appointments"))]
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ReminderScheduleSchema(BaseModel):
    appointment_id: int
    rules: list[AppointmentReminderRule] = Field(
        default_factory=lambda: [
            AppointmentReminderRule.H24_BEFORE,
            AppointmentReminderRule.H2_BEFORE,
        ],
    )
    channels: Optional[list[str]] = None
    custom_offset_minutes: Optional[int] = None


class ReminderJobReadSchema(BaseModel):
    id: int
    appointment_id: int
    rule: AppointmentReminderRule
    fire_at: datetime
    fired_at: Optional[datetime] = None
    channels: Optional[list[str]] = None
    status: str
    last_error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CancellationLogSchema(BaseModel):
    appointment_id: int
    action: str = Field(..., pattern=r"^(CANCELLED|RESCHEDULED|NO_SHOW)$")
    reason: Optional[str] = None
    previous_start_at: Optional[datetime] = None
    new_start_at: Optional[datetime] = None


class CancellationLogReadSchema(BaseModel):
    id: int
    appointment_id: int
    action: str
    reason: Optional[str] = None
    actor_user_id: Optional[int] = None
    previous_start_at: Optional[datetime] = None
    new_start_at: Optional[datetime] = None
    occurred_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecurrenceCreateSchema(BaseModel):
    parent_appointment_id: int
    recurrence: AppointmentRecurrence = AppointmentRecurrence.WEEKLY
    interval_count: int = 1
    occurrences: Optional[int] = None
    until_date: Optional[date] = None
    weekdays: Optional[list[int]] = None


class RecurrenceReadSchema(BaseModel):
    id: int
    parent_appointment_id: int
    recurrence: AppointmentRecurrence
    interval_count: int
    occurrences: Optional[int] = None
    until_date: Optional[date] = None
    weekdays: Optional[list[int]] = None

    model_config = ConfigDict(from_attributes=True)


def _service(db: Annotated[Session, Depends(get_db)]) -> AppointmentExtensionService:
    return AppointmentExtensionService(db)


# ---------------------------------------------------------------------------
# Reminder routes
# ---------------------------------------------------------------------------


@router.post(
    "/reminders/schedule",
    response_model=list[ReminderJobReadSchema],
    status_code=status.HTTP_201_CREATED,
    summary="Materialise reminder jobs for an appointment",
)
def schedule_reminders(
    payload: ReminderScheduleSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AppointmentExtensionService, Depends(_service)],
):
    from app.models.all_models import Appointment

    appt = db.query(Appointment).filter(Appointment.id == payload.appointment_id).first()
    if appt is None:
        return []
    return service.schedule_reminders(
        appt,
        rules=payload.rules,
        channels=payload.channels,
        custom_offset_minutes=payload.custom_offset_minutes,
    )


@router.post(
    "/reminders/dispatch-due",
    summary="Dispatch any reminder jobs whose fire_at has passed",
)
def dispatch_due_reminders(
    _: AdminUser,
    service: Annotated[AppointmentExtensionService, Depends(_service)],
):
    return service.dispatch_due_reminders()


# ---------------------------------------------------------------------------
# Cancellation history
# ---------------------------------------------------------------------------


@router.post(
    "/history/{appointment_id}/log",
    response_model=CancellationLogReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Log a cancellation / reschedule / no-show",
)
def log_history(
    appointment_id: int,
    payload: CancellationLogSchema,
    actor: AdminUser,
    service: Annotated[AppointmentExtensionService, Depends(_service)],
):
    return service.log_cancellation(
        appointment_id=appointment_id,
        action=payload.action,
        reason=payload.reason,
        actor_user_id=getattr(actor, "id", None),
        previous_start_at=payload.previous_start_at,
        new_start_at=payload.new_start_at,
    )


@router.get(
    "/history/{appointment_id}",
    response_model=list[CancellationLogReadSchema],
    summary="Read appointment history (cancellations, reschedules, no-shows)",
)
def read_history(
    appointment_id: int,
    _: CurrentActiveUser,
    service: Annotated[AppointmentExtensionService, Depends(_service)],
):
    return service.history(appointment_id)


# ---------------------------------------------------------------------------
# Recurrence
# ---------------------------------------------------------------------------


@router.post(
    "/recurrence",
    response_model=RecurrenceReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Define a recurrence rule for an appointment series",
)
def create_recurrence(
    payload: RecurrenceCreateSchema,
    _: AdminUser,
    service: Annotated[AppointmentExtensionService, Depends(_service)],
):
    return service.create_recurrence(**payload.model_dump())


@router.post(
    "/recurrence/{rule_id}/expand",
    summary="Expand a recurrence rule into concrete child appointments",
)
def expand_recurrence(
    rule_id: int,
    max_create: int = 24,
    _: AdminUser = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    service: AppointmentExtensionService = Depends(_service),
):
    from app.models.all_models import AppointmentRecurrenceRule

    rule = db.query(AppointmentRecurrenceRule).filter(AppointmentRecurrenceRule.id == rule_id).first()
    if rule is None:
        return {"created": 0}
    out = service.expand_recurrence(rule, max_create=max_create)
    return {"created": len(out)}
