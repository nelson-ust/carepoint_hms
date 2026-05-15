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
from app.core.dependencies import AdminUser, AnyAuthenticatedUser, require_plan_feature

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
    VisitSwitchFlowResultSchema,
    VisitSwitchFlowSchema,
    VisitUpdateSchema,
)
from app.services.visit_service import VisitService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/visits",
    tags=["Visit Management"],
    dependencies=[Depends(require_plan_feature("clinical"))]
)



def get_visit_service(
    db: Annotated[Session, Depends(get_db)],
) -> VisitService:
    """
    Dependency provider for the visit service.
    """
    return VisitService(db)


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
        "visit": result["visit"],
        "first_flow_step": result.get("first_flow_step"),
        "first_queue_ticket": result.get("first_queue_ticket"),
        "applied_template": result.get("applied_template"),
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
        "visit": result["visit"],
        "new_flow_step": result["new_flow_step"],
        "new_queue_ticket": result.get("new_queue_ticket"),
    }


@router.post(
    "/{visit_id}/switch-flow",
    response_model=VisitSwitchFlowResultSchema,
    status_code=status.HTTP_200_OK,
    summary="Switch visit flow template",
)
def switch_visit_flow(
    visit_id: int,
    payload: VisitSwitchFlowSchema,
    current_user: AdminUser,
    service: Annotated[VisitService, Depends(get_visit_service)],
):
    """
    Switch the entire remaining care pathway for a patient by applying a new
    visit flow template. Existing pending steps are cancelled and replaced
    by steps from the new template.
    """
    payload.routed_by_id = current_user.id
    result = service.switch_visit_flow(visit_id, payload)

    return {
        "success": True,
        "message": result["message"],
        "visit": result["visit"],
        "added_steps": result["added_steps"],
        "new_queue_ticket": result.get("new_queue_ticket"),
    }


@router.get(
    "/",
    response_model=VisitListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List visits",
)
def list_visits(
    _: AnyAuthenticatedUser,
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
        items=items,
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
    _: AnyAuthenticatedUser,
    service: Annotated[VisitService, Depends(get_visit_service)],
):
    """
    Return a single visit record.
    """
    return service.get_visit(visit_id)


@router.get(
    "/{visit_id}/detailed",
    response_model=VisitDetailedReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get detailed visit",
)
def get_detailed_visit(
    visit_id: int,
    _: AnyAuthenticatedUser,
    service: Annotated[VisitService, Depends(get_visit_service)],
):
    """
    Return a detailed visit record including patient, appointment, flow steps,
    and queue tickets.
    """
    return service.get_detailed_visit(visit_id)


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
    return service.update_visit(visit_id, payload)


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