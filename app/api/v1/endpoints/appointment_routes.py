# app/api/v1/endpoints/appointment_routes.py
from __future__ import annotations

"""
FastAPI routes for the appointment scheduling module (Stage 7).

Endpoints
---------
- ``GET    /appointments``                            list with filters
- ``GET    /appointments/arrival-board``              day-of board for a SDP
- ``GET    /appointments/availability``               check a slot
- ``POST   /appointments``                            book a new appointment
- ``GET    /appointments/{appointment_id}``           single appointment
- ``POST   /appointments/{appointment_id}/reschedule`` reschedule
- ``POST   /appointments/{appointment_id}/cancel``    cancel
- ``POST   /appointments/{appointment_id}/no-show``   mark missed
- ``POST   /appointments/{appointment_id}/check-in``  check in (initiates visit)

Permission codes
----------------
- ``APPOINTMENT_READ``    — list / get / availability / arrival board
- ``APPOINTMENT_CREATE``  — book / reschedule
- ``APPOINTMENT_UPDATE``  — reschedule / no-show / check-in
- ``APPOINTMENT_CANCEL``  — cancel
- ``VISIT_INITIATE``      — required (alongside) for check-in
"""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.appointment_schemas import (
    AppointmentActionResponseSchema,
    AppointmentAvailabilityResponseSchema,
    AppointmentCancelSchema,
    AppointmentCheckInResponseSchema,
    AppointmentCheckInSchema,
    AppointmentCreateSchema,
    AppointmentListResponseSchema,
    AppointmentNoShowSchema,
    AppointmentReadSchema,
    AppointmentRescheduleSchema,
)
from app.services.appointment_service import AppointmentService
from app.utils.pagination import paginate_response

router = APIRouter(prefix="/appointments", tags=["Appointments"])


def get_appointment_service(db: Annotated[Session, Depends(get_db)]) -> AppointmentService:
    """FastAPI dependency that constructs an AppointmentService per-request."""
    return AppointmentService(db)


# ============================================================
# READ
# ============================================================


@router.get(
    "/",
    response_model=AppointmentListResponseSchema,
    summary="List appointments",
)
def list_appointments(
    _: Annotated[User, Depends(require_permission("APPOINTMENT_READ"))],
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    patient_id: Optional[int] = Query(None),
    staff_profile_id: Optional[int] = Query(None),
    service_delivery_point_id: Optional[int] = Query(None),
    facility_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="SCHEDULED, ARRIVED, IN_PROGRESS, COMPLETED, MISSED, CANCELLED, RESCHEDULED.",
    ),
    from_dt: Optional[datetime] = Query(None, description="Earliest scheduled_start_at (UTC)."),
    to_dt: Optional[datetime] = Query(None, description="Latest exclusive scheduled_start_at (UTC)."),
):
    """Paginated list of appointments with the most common filters."""
    items, total = service.list_appointments(
        skip=skip, limit=limit,
        patient_id=patient_id,
        staff_profile_id=staff_profile_id,
        service_delivery_point_id=service_delivery_point_id,
        facility_id=facility_id,
        status=status_filter,
        from_dt=from_dt,
        to_dt=to_dt,
    )
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Appointments fetched successfully.",
    )


@router.get(
    "/arrival-board",
    response_model=AppointmentListResponseSchema,
    summary="Arrival board for a given date",
)
def arrival_board(
    _: Annotated[User, Depends(require_permission("APPOINTMENT_READ"))],
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
    for_date: datetime = Query(..., description="UTC midnight of the target day."),
    service_delivery_point_id: Optional[int] = Query(None),
    facility_id: Optional[int] = Query(None),
):
    """Active appointments scheduled for the given day."""
    items = service.arrival_board(
        for_date=for_date,
        service_delivery_point_id=service_delivery_point_id,
        facility_id=facility_id,
    )
    return paginate_response(
        items=items,
        total=len(items),
        skip=0,
        limit=len(items) or 1,
        message="Arrival board fetched successfully.",
    )


@router.get(
    "/availability",
    response_model=AppointmentAvailabilityResponseSchema,
    summary="Check slot availability",
)
def check_availability(
    _: Annotated[User, Depends(require_permission("APPOINTMENT_READ"))],
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
    scheduled_start_at: datetime = Query(...),
    scheduled_end_at: Optional[datetime] = Query(None),
    staff_profile_id: Optional[int] = Query(None),
    service_delivery_point_id: Optional[int] = Query(None),
    exclude_appointment_id: Optional[int] = Query(None),
):
    """Returns ``available=True`` and an empty conflicts list when free."""
    conflicts = service.check_availability(
        scheduled_start_at=scheduled_start_at,
        scheduled_end_at=scheduled_end_at,
        staff_profile_id=staff_profile_id,
        service_delivery_point_id=service_delivery_point_id,
        exclude_appointment_id=exclude_appointment_id,
    )
    return {
        "success": True,
        "message": "Availability fetched successfully.",
        "available": not conflicts,
        "conflicts": conflicts,
    }


@router.get(
    "/{appointment_id}",
    response_model=AppointmentReadSchema,
    summary="Get an appointment",
)
def get_appointment(
    appointment_id: int,
    _: Annotated[User, Depends(require_permission("APPOINTMENT_READ"))],
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
):
    """Read a single appointment by id."""
    return service.get(appointment_id)


# ============================================================
# WRITE
# ============================================================


@router.post(
    "/",
    response_model=AppointmentActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Book an appointment",
)
def book_appointment(
    payload: AppointmentCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
    _: Annotated[User, Depends(require_permission("APPOINTMENT_CREATE"))],
):
    """Book a new appointment. Detects double-booking against staff or SDP."""
    appointment = service.book_appointment(payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Appointment booked.",
        "appointment": appointment,
    }


@router.post(
    "/{appointment_id}/reschedule",
    response_model=AppointmentActionResponseSchema,
    summary="Reschedule an appointment",
)
def reschedule_appointment(
    appointment_id: int,
    payload: AppointmentRescheduleSchema,
    actor: CurrentActiveUser,
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
    _: Annotated[User, Depends(require_permission("APPOINTMENT_UPDATE", "APPOINTMENT_CREATE"))],
):
    """Move the appointment to a new slot, re-validating contention."""
    appointment = service.reschedule(appointment_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Appointment rescheduled.",
        "appointment": appointment,
    }


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentActionResponseSchema,
    summary="Cancel an appointment",
)
def cancel_appointment(
    appointment_id: int,
    payload: AppointmentCancelSchema,
    actor: CurrentActiveUser,
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
    _: Annotated[User, Depends(require_permission("APPOINTMENT_CANCEL"))],
):
    """Cancel an appointment, optionally with a reason captured in the audit."""
    appointment = service.cancel(appointment_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Appointment cancelled.",
        "appointment": appointment,
    }


@router.post(
    "/{appointment_id}/no-show",
    response_model=AppointmentActionResponseSchema,
    summary="Mark an appointment as no-show",
)
def mark_no_show(
    appointment_id: int,
    payload: AppointmentNoShowSchema,
    actor: CurrentActiveUser,
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
    _: Annotated[User, Depends(require_permission("APPOINTMENT_UPDATE"))],
):
    """Mark the appointment as MISSED."""
    appointment = service.mark_no_show(appointment_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Appointment marked missed.",
        "appointment": appointment,
    }


@router.post(
    "/{appointment_id}/check-in",
    response_model=AppointmentCheckInResponseSchema,
    summary="Check in: mark ARRIVED and optionally initiate the visit",
)
def check_in_appointment(
    appointment_id: int,
    payload: AppointmentCheckInSchema,
    actor: CurrentActiveUser,
    service: Annotated[AppointmentService, Depends(get_appointment_service)],
    _: Annotated[User, Depends(require_permission("APPOINTMENT_UPDATE", "VISIT_INITIATE"))],
):
    """
    Mark the appointment as ARRIVED. When ``initiate_visit`` is True the
    response also carries the new visit + first queue ticket.
    """
    result = service.check_in(appointment_id, payload, actor_user_id=actor.id)

    appointment = result["appointment"]
    visit = result["visit"]
    queue_ticket = result["queue_ticket"]

    return {
        "success": True,
        "message": (
            "Appointment checked in and visit initiated."
            if visit is not None
            else "Appointment checked in."
        ),
        "appointment": appointment,
        "visit_id": getattr(visit, "id", None),
        "visit_code": getattr(visit, "visit_code", None),
        "queue_ticket_id": getattr(queue_ticket, "id", None),
        "queue_number": getattr(queue_ticket, "queue_number", None),
        "queue_position": getattr(queue_ticket, "queue_position", None),
        "first_service_delivery_point_id": getattr(visit, "first_service_delivery_point_id", None),
    }
