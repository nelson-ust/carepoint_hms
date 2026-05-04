from __future__ import annotations

"""
app.api.v1.endpoints.visit_routes

FastAPI routes for visit initiation and operational care workflow.

Purpose
-------
This module exposes API endpoints for:

- initiating visits
- rerouting active visits
- retrieving visit details
- listing visits
- updating visit state

Security
--------
These endpoints are intended for authorized registration/front-desk/admin staff
and are protected with the admin dependency.
"""

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser
from app.schemas.visit_schemas import (
    QueueTicketReadSchema,
    VisitActionResponseSchema,
    VisitDetailedReadSchema,
    VisitInitiateSchema,
    VisitInitiationResultSchema,
    VisitListResponseSchema,
    VisitReadSchema,
    VisitRerouteResultSchema,
    VisitRerouteSchema,
    VisitUpdateSchema,
)
from app.services.visit_service import VisitService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/visits",
    tags=["Visit Management"],
)


def get_visit_service(
    db: Annotated[Session, Depends(get_db)],
) -> VisitService:
    """
    Dependency provider for the visit service.
    """
    return VisitService(db)


# ============================================================
# SERIALIZATION HELPERS
# ============================================================

def _safe_enum(value) -> Optional[str]:
    """
    Convert enum-like values to strings safely.
    """
    if value is None:
        return None
    return str(value)


def _serialize_patient(patient) -> Optional[dict[str, Any]]:
    """
    Serialize a lightweight patient payload for visit responses.
    """
    if not patient:
        return None

    return {
        "id": patient.id,
        "hospital_number": patient.hospital_number,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "middle_name": getattr(patient, "middle_name", None),
        "gender": _safe_enum(getattr(patient, "gender", None)),
        "phone_number": getattr(patient, "phone_number", None),
    }


def _serialize_appointment(appointment) -> Optional[dict[str, Any]]:
    """
    Serialize a lightweight appointment payload.
    """
    if not appointment:
        return None

    return {
        "id": appointment.id,
        "appointment_code": appointment.appointment_code,
        "scheduled_start_at": appointment.scheduled_start_at,
        "scheduled_end_at": getattr(appointment, "scheduled_end_at", None),
        "reason": getattr(appointment, "reason", None),
        "status": _safe_enum(getattr(appointment, "status", None)),
        "patient_id": appointment.patient_id,
        "service_delivery_point_id": getattr(appointment, "service_delivery_point_id", None),
        "staff_profile_id": getattr(appointment, "staff_profile_id", None),
    }


def _serialize_service_delivery_point(service_point) -> Optional[dict[str, Any]]:
    """
    Serialize a lightweight service delivery point payload.
    """
    if not service_point:
        return None

    return {
        "id": service_point.id,
        "name": service_point.name,
        "code": service_point.code,
        "service_point_type": _safe_enum(getattr(service_point, "service_point_type", None)),
        "department_id": getattr(service_point, "department_id", None),
        "location_description": getattr(service_point, "location_description", None),
        "queue_prefix": getattr(service_point, "queue_prefix", None),
        "supports_appointments": getattr(service_point, "supports_appointments", False),
        "supports_walk_in": getattr(service_point, "supports_walk_in", False),
    }


def _serialize_flow_step(flow_step) -> Optional[dict[str, Any]]:
    """
    Serialize a runtime visit flow step.
    """
    if not flow_step:
        return None

    return {
        "id": flow_step.id,
        "visit_id": flow_step.visit_id,
        "service_delivery_point_id": flow_step.service_delivery_point_id,
        "step_order": flow_step.step_order,
        "status": _safe_enum(flow_step.status),
        "is_current": flow_step.is_current,
        "is_required": flow_step.is_required,
        "is_skipped": flow_step.is_skipped,
        "routed_by_id": flow_step.routed_by_id,
        "started_at": flow_step.started_at,
        "completed_at": flow_step.completed_at,
        "notes": flow_step.notes,
        "service_delivery_point": _serialize_service_delivery_point(
            getattr(flow_step, "service_delivery_point", None)
        ),
        "created_at": getattr(flow_step, "date_created", None),
        "updated_at": getattr(flow_step, "date_updated", None),
    }


def _serialize_queue_ticket(ticket) -> Optional[dict[str, Any]]:
    """
    Serialize a queue ticket.
    """
    if not ticket:
        return None

    return {
        "id": ticket.id,
        "visit_id": ticket.visit_id,
        "visit_flow_step_id": ticket.visit_flow_step_id,
        "patient_id": ticket.patient_id,
        "service_delivery_point_id": ticket.service_delivery_point_id,
        "queue_number": ticket.queue_number,
        "queue_position": ticket.queue_position,
        "status": _safe_enum(ticket.status),
        "called_at": ticket.called_at,
        "service_started_at": ticket.service_started_at,
        "service_ended_at": ticket.service_ended_at,
        "transferred_from_ticket_id": ticket.transferred_from_ticket_id,
        "service_delivery_point": _serialize_service_delivery_point(
            getattr(ticket, "service_delivery_point", None)
        ),
        "created_at": getattr(ticket, "date_created", None),
        "updated_at": getattr(ticket, "date_updated", None),
    }


def _serialize_template_step(template_step) -> Optional[dict[str, Any]]:
    """
    Serialize a reusable visit-flow template step.
    """
    if not template_step:
        return None

    return {
        "id": template_step.id,
        "template_id": template_step.template_id,
        "service_delivery_point_id": template_step.service_delivery_point_id,
        "step_order": template_step.step_order,
        "is_required": template_step.is_required,
        "notes": template_step.notes,
        "service_delivery_point": _serialize_service_delivery_point(
            getattr(template_step, "service_delivery_point", None)
        ),
        "created_at": getattr(template_step, "date_created", None),
        "updated_at": getattr(template_step, "date_updated", None),
    }


def _serialize_template(template) -> Optional[dict[str, Any]]:
    """
    Serialize a reusable visit-flow template.
    """
    if not template:
        return None

    return {
        "id": template.id,
        "name": template.name,
        "code": template.code,
        "description": template.description,
        "steps": [
            _serialize_template_step(step)
            for step in (getattr(template, "steps", []) or [])
            if not getattr(step, "is_deleted", False)
        ],
        "created_at": getattr(template, "date_created", None),
        "updated_at": getattr(template, "date_updated", None),
    }


def _serialize_visit(visit) -> dict[str, Any]:
    """
    Serialize a standard visit payload.
    """
    return {
        "id": visit.id,
        "patient_id": visit.patient_id,
        "appointment_id": visit.appointment_id,
        "visit_code": visit.visit_code,
        "visit_date": visit.visit_date,
        "status": _safe_enum(visit.status),
        "priority": _safe_enum(visit.priority),
        "first_service_delivery_point_id": visit.first_service_delivery_point_id,
        "current_service_delivery_point_id": visit.current_service_delivery_point_id,
        "referred_from": visit.referred_from,
        "visit_reason": visit.visit_reason,
        "check_in_time": visit.check_in_time,
        "check_out_time": visit.check_out_time,
        "created_at": getattr(visit, "date_created", None),
        "updated_at": getattr(visit, "date_updated", None),
    }


def _serialize_detailed_visit(visit) -> dict[str, Any]:
    """
    Serialize a detailed visit payload.
    """
    payload = _serialize_visit(visit)
    payload.update(
        {
            "patient": _serialize_patient(getattr(visit, "patient", None)),
            "appointment": _serialize_appointment(getattr(visit, "appointment", None)),
            "first_service_delivery_point": _serialize_service_delivery_point(
                getattr(visit, "first_service_delivery_point", None)
            ),
            "current_service_delivery_point": _serialize_service_delivery_point(
                getattr(visit, "current_service_delivery_point", None)
            ),
            "flow_steps": [
                _serialize_flow_step(step)
                for step in (getattr(visit, "flow_steps", []) or [])
                if not getattr(step, "is_deleted", False)
            ],
            "queue_tickets": [
                _serialize_queue_ticket(ticket)
                for ticket in (getattr(visit, "queue_tickets", []) or [])
                if not getattr(ticket, "is_deleted", False)
            ],
        }
    )
    return payload


def _serialize_visit_list_item(visit) -> dict[str, Any]:
    """
    Serialize a visit list item.
    """
    return {
        "id": visit.id,
        "patient_id": visit.patient_id,
        "appointment_id": visit.appointment_id,
        "visit_code": visit.visit_code,
        "visit_date": visit.visit_date,
        "status": _safe_enum(visit.status),
        "priority": _safe_enum(visit.priority),
        "first_service_delivery_point_id": visit.first_service_delivery_point_id,
        "current_service_delivery_point_id": visit.current_service_delivery_point_id,
        "visit_reason": visit.visit_reason,
    }


# ============================================================
# ROUTES
# ============================================================

@router.post(
    "/initiate",
    response_model=VisitInitiationResultSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate visit",
)
def initiate_visit(
    payload: VisitInitiateSchema,
    current_user: AdminUser,
    service: Annotated[VisitService, Depends(get_visit_service)],
):
    """
    Initiate a patient visit, resolve the first care point, create the first
    flow step, and place the patient into the operational queue.
    """
    result = service.initiate_visit(payload, routed_by_id=current_user.id)

    return {
        "success": True,
        "message": result["message"],
        "visit": _serialize_detailed_visit(result["visit"]),
        "first_flow_step": _serialize_flow_step(result.get("first_flow_step")),
        "first_queue_ticket": _serialize_queue_ticket(result.get("first_queue_ticket")),
        "applied_template": _serialize_template(result.get("applied_template")),
        "inherited_from_appointment": result.get("inherited_from_appointment", False),
        "fast_tracked": result.get("fast_tracked", False),
    }


@router.post(
    "/{visit_id}/reroute",
    response_model=VisitRerouteResultSchema,
    status_code=status.HTTP_200_OK,
    summary="Reroute visit",
)
def reroute_visit(
    visit_id: int,
    payload: VisitRerouteSchema,
    _: AdminUser,
    service: Annotated[VisitService, Depends(get_visit_service)],
):
    """
    Reroute an active visit to another service delivery point and optionally
    create a new queue ticket at that destination.
    """
    result = service.reroute_visit(visit_id, payload)

    return {
        "success": True,
        "message": result["message"],
        "visit": _serialize_detailed_visit(result["visit"]),
        "new_flow_step": _serialize_flow_step(result["new_flow_step"]),
        "new_queue_ticket": _serialize_queue_ticket(result.get("new_queue_ticket")),
    }


@router.get(
    "/",
    response_model=VisitListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List visits",
)
def list_visits(
    _: AdminUser,
    service: Annotated[VisitService, Depends(get_visit_service)],
    skip: int = Query(0, ge=0, description="Pagination offset."),
    limit: int = Query(20, ge=1, le=100, description="Pagination size."),
    patient_id: Optional[int] = Query(None),
    appointment_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    service_delivery_point_id: Optional[int] = Query(None),
):
    """
    Return a paginated list of visits with optional filters.
    """
    items, total = service.list_visits(
        skip=skip,
        limit=limit,
        patient_id=patient_id,
        appointment_id=appointment_id,
        status=status_filter,
        priority=priority,
        service_delivery_point_id=service_delivery_point_id,
    )

    return paginate_response(
        items=[_serialize_visit_list_item(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Visits fetched successfully.",
    )


@router.get(
    "/{visit_id}",
    response_model=VisitReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get visit",
)
def get_visit(
    visit_id: int,
    _: AdminUser,
    service: Annotated[VisitService, Depends(get_visit_service)],
):
    """
    Return a single visit record.
    """
    visit = service.get_visit(visit_id)
    return _serialize_visit(visit)


@router.get(
    "/{visit_id}/detailed",
    response_model=VisitDetailedReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get detailed visit",
)
def get_detailed_visit(
    visit_id: int,
    _: AdminUser,
    service: Annotated[VisitService, Depends(get_visit_service)],
):
    """
    Return a detailed visit record including patient, appointment, flow steps,
    and queue tickets.
    """
    visit = service.get_detailed_visit(visit_id)
    return _serialize_detailed_visit(visit)


@router.put(
    "/{visit_id}",
    response_model=VisitDetailedReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update visit",
)
def update_visit(
    visit_id: int,
    payload: VisitUpdateSchema,
    _: AdminUser,
    service: Annotated[VisitService, Depends(get_visit_service)],
):
    """
    Update visit operational fields such as status, priority, current service
    point, or timing information.
    """
    visit = service.update_visit(visit_id, payload)
    return _serialize_detailed_visit(visit)


@router.delete(
    "/{visit_id}",
    response_model=VisitActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Close or remove visit placeholder response",
)
def delete_visit_placeholder(
    visit_id: int,
    _: AdminUser,
):
    """
    Placeholder route for future visit delete/cancel behavior.

    This route is included only to keep the visit route surface consistent.
    Replace with a real cancel/delete implementation when that requirement is added.
    """
    return {
        "success": True,
        "message": f"Visit endpoint placeholder reached for visit_id={visit_id}.",
    }