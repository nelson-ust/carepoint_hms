# app/api/v1/endpoints/queue_routes.py
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    AnyAuthenticatedUser,
    CurrentActiveUser,
    require_plan_feature,
)

from app.dependencies.role import require_permission, require_any_permission
from app.dependencies.service_delivery_point import (
    require_assigned_to_sdp,
    require_assigned_to_ticket_sdp,
)
from app.models.all_models import User
from app.schemas.queue_schema import (
    QueueDisplayBoardResponseSchema,
    QueueStatsResponseSchema,
    QueueTicketActionResponseSchema,
    QueueTicketCallSchema,
    QueueTicketCancelSchema,
    QueueTicketCompleteAndEndVisitSchema,
    QueueTicketCompleteAndRouteSchema,
    QueueTicketCompleteSchema,
    QueueTicketListResponseSchema,
    QueueTicketReadSchema,
    QueueTicketServeSchema,
    QueueTicketTransferSchema,
    ServicePointWorklistResponseSchema,
)
from app.services.queue_service import QueueService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/queue", 
    tags=["Queue"],
    dependencies=[Depends(require_plan_feature("clinical"))]
)



def get_queue_service(db: Annotated[Session, Depends(get_db)]) -> QueueService:
    return QueueService(db)


# ============================================================
# READ ROUTES
# ============================================================

@router.get(
    "/my-worklist",
    response_model=ServicePointWorklistResponseSchema,
    summary="Worklist for the caller's assigned service delivery point",
)
def get_my_worklist(
    actor: AnyAuthenticatedUser,
    service: Annotated[QueueService, Depends(get_queue_service)],
    service_delivery_point_id: Optional[int] = Query(None, description="Optional SDP ID to view if user has multiple assignments."),
):
    """
    Returns the worklist for the staff member's assigned service delivery
    point.
    """
    return service.get_my_worklist(actor, sdp_id=service_delivery_point_id)


@router.get(
    "/stats",
    response_model=QueueStatsResponseSchema,
    summary="Queue throughput and wait-time statistics per service point",
)
def get_queue_stats(
    _: AnyAuthenticatedUser,
    service: Annotated[QueueService, Depends(get_queue_service)],
    date_from: Optional[datetime] = Query(None, description="Window start (ISO 8601). Defaults to start of today UTC."),
    date_to: Optional[datetime] = Query(None, description="Window end (ISO 8601, exclusive). Defaults to end of today UTC."),
):
    """
    Per-service-point aggregates for the requested window: tickets issued,
    served / missed / cancelled / transferred, live queue depth, average
    wait, average service time and no-show rate.
    """
    data = service.get_queue_stats(date_from=date_from, date_to=date_to)
    return {"success": True, "message": "Queue statistics computed successfully.", **data}


@router.get(
    "/display-board",
    response_model=QueueDisplayBoardResponseSchema,
    summary="Waiting-room display board (now serving / up next)",
)
def get_display_board(
    _: AnyAuthenticatedUser,
    service: Annotated[QueueService, Depends(get_queue_service)],
    waiting_limit: int = Query(5, ge=1, le=20, description="How many upcoming tickets to show per service point."),
):
    """
    Privacy-safe snapshot for waiting-room screens: per service point, the
    tickets now being served, just called, and the next few waiting numbers.
    Only queue numbers are exposed — no patient identifiers.
    """
    data = service.get_display_board(waiting_limit=waiting_limit)
    return {"success": True, "message": "Display board fetched successfully.", **data}


@router.get(
    "/service-points/{service_delivery_point_id}/worklist",
    response_model=ServicePointWorklistResponseSchema,
    summary="Get worklist for a service-point workstation",
)
def get_worklist(
    service_delivery_point_id: int,
    _: Annotated[User, Depends(require_assigned_to_sdp(sdp_param_name="service_delivery_point_id"))],
    service: Annotated[QueueService, Depends(get_queue_service)],
):
    return service.get_worklist(service_delivery_point_id)


@router.get(
    "/service-points/{service_delivery_point_id}/tickets",
    response_model=QueueTicketListResponseSchema,
    summary="List tickets at a service delivery point",
)
def list_service_point_tickets(
    service_delivery_point_id: int,
    _: Annotated[User, Depends(require_assigned_to_sdp(sdp_param_name="service_delivery_point_id"))],
    service: Annotated[QueueService, Depends(get_queue_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    statuses: Optional[list[str]] = Query(
        None, description="Filter by status: WAITING, CALLED, SERVING, SERVED, MISSED, CANCELLED, TRANSFERRED."
    ),
):
    items, total = service.list_for_service_point(
        service_delivery_point_id, statuses=statuses, skip=skip, limit=limit
    )
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Queue tickets fetched successfully.",
    )


@router.get(
    "/visits/{visit_id}/tickets",
    response_model=QueueTicketListResponseSchema,
    summary="List queue tickets for a visit",
)
def list_visit_tickets(
    visit_id: int,
    _: Annotated[User, Depends(require_any_permission("VISIT_READ", "PATIENTS:VIEW"))],
    service: Annotated[QueueService, Depends(get_queue_service)],
):
    items = service.list_for_visit(visit_id)
    return paginate_response(
        items=items,
        total=len(items),
        skip=0,
        limit=len(items) or 1,
        message="Queue tickets for visit fetched successfully.",
    )


@router.get(
    "/tickets/{ticket_id}",
    response_model=QueueTicketReadSchema,
    summary="Get queue ticket details",
)
def get_ticket(
    ticket_id: int,
    _: Annotated[User, Depends(require_any_permission("VISIT_READ", "PATIENTS:VIEW"))],
    service: Annotated[QueueService, Depends(get_queue_service)],
):
    return service.get_ticket(ticket_id)


# ============================================================
# MUTATION ROUTES
# ============================================================

@router.post(
    "/tickets/{ticket_id}/call",
    response_model=QueueTicketActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Call a queue ticket",
)
def call_ticket(
    ticket_id: int,
    payload: QueueTicketCallSchema,
    actor: CurrentActiveUser,
    service: Annotated[QueueService, Depends(get_queue_service)],
    _: Annotated[User, Depends(require_any_permission("QUEUE_MANAGE", "QUEUE:MANAGE"))],
    __: Annotated[User, Depends(require_assigned_to_ticket_sdp())],
):
    ticket = service.call_ticket(ticket_id, actor_user_id=actor.id)
    return {"success": True, "message": "Ticket called.", "ticket": ticket}


@router.post(
    "/tickets/{ticket_id}/serve",
    response_model=QueueTicketActionResponseSchema,
    summary="Start serving a queue ticket",
)
def start_serving_ticket(
    ticket_id: int,
    payload: QueueTicketServeSchema,
    actor: CurrentActiveUser,
    service: Annotated[QueueService, Depends(get_queue_service)],
    _: Annotated[User, Depends(require_any_permission("QUEUE_MANAGE", "QUEUE:MANAGE"))],
    __: Annotated[User, Depends(require_assigned_to_ticket_sdp())],
):
    ticket = service.start_serving(ticket_id, actor_user_id=actor.id)
    return {"success": True, "message": "Ticket serving started.", "ticket": ticket}


@router.post(
    "/tickets/{ticket_id}/complete",
    response_model=QueueTicketActionResponseSchema,
    summary="Complete a queue ticket",
)
def complete_ticket(
    ticket_id: int,
    payload: QueueTicketCompleteSchema,
    actor: CurrentActiveUser,
    service: Annotated[QueueService, Depends(get_queue_service)],
    _: Annotated[User, Depends(require_any_permission("QUEUE_MANAGE", "QUEUE:MANAGE"))],
    __: Annotated[User, Depends(require_assigned_to_ticket_sdp())],
):
    ticket = service.complete_ticket(ticket_id, actor_user_id=actor.id)
    return {"success": True, "message": "Ticket completed.", "ticket": ticket}


@router.post(
    "/tickets/{ticket_id}/complete-and-route",
    response_model=QueueTicketActionResponseSchema,
    summary="Complete current ticket and route the patient to the next SDP",
)
def complete_and_route_ticket(
    ticket_id: int,
    payload: QueueTicketCompleteAndRouteSchema,
    actor: CurrentActiveUser,
    service: Annotated[QueueService, Depends(get_queue_service)],
    _: Annotated[User, Depends(require_any_permission("QUEUE_MANAGE", "QUEUE:MANAGE", "VISIT_ROUTE", "VISITS:ROUTE"))],
    __: Annotated[User, Depends(require_assigned_to_ticket_sdp())],
):
    """
    Mark the current ticket SERVED, close the linked visit-flow step, then
    create a brand-new VisitFlowStep + QueueTicket at the requested SDP.
    """
    new_ticket = service.complete_and_route_to(
        ticket_id,
        payload.target_service_delivery_point_id,
        notes=payload.notes,
        actor_user_id=actor.id,
    )
    return {
        "success": True,
        "message": "Patient handed off to the next service delivery point.",
        "ticket": new_ticket,
    }


@router.post(
    "/tickets/{ticket_id}/complete-and-end-visit",
    summary="Complete the current ticket and end the visit",
)
def complete_and_end_visit_ticket(
    ticket_id: int,
    payload: QueueTicketCompleteAndEndVisitSchema,
    actor: CurrentActiveUser,
    service: Annotated[QueueService, Depends(get_queue_service)],
    _: Annotated[User, Depends(require_any_permission("QUEUE_MANAGE", "QUEUE:MANAGE", "VISIT_ROUTE", "VISITS:ROUTE"))],
    __: Annotated[User, Depends(require_assigned_to_ticket_sdp())],
):
    """
    The patient has reached the final service delivery point. This action
    closes the current ticket and marks the Visit COMPLETED.
    """
    visit = service.complete_and_end_visit(
        ticket_id,
        note=payload.note,
        actor_user_id=actor.id,
    )
    return {
        "success": True,
        "message": "Visit marked completed.",
        "visit_id": visit.id,
        "visit_status": str(visit.status),
        "check_out_time": visit.check_out_time,
    }


@router.post(
    "/tickets/{ticket_id}/miss",
    response_model=QueueTicketActionResponseSchema,
    summary="Mark a queue ticket as missed",
)
def miss_ticket(
    ticket_id: int,
    actor: CurrentActiveUser,
    service: Annotated[QueueService, Depends(get_queue_service)],
    _: Annotated[User, Depends(require_any_permission("QUEUE_MANAGE", "QUEUE:MANAGE"))],
    __: Annotated[User, Depends(require_assigned_to_ticket_sdp())],
):
    ticket = service.mark_missed(ticket_id, actor_user_id=actor.id)
    return {"success": True, "message": "Ticket marked missed.", "ticket": ticket}


@router.post(
    "/tickets/{ticket_id}/cancel",
    response_model=QueueTicketActionResponseSchema,
    summary="Cancel a queue ticket",
)
def cancel_ticket(
    ticket_id: int,
    payload: QueueTicketCancelSchema,
    actor: CurrentActiveUser,
    service: Annotated[QueueService, Depends(get_queue_service)],
    _: Annotated[User, Depends(require_any_permission("QUEUE_MANAGE", "QUEUE:MANAGE"))],
    __: Annotated[User, Depends(require_assigned_to_ticket_sdp())],
):
    ticket = service.cancel_ticket(ticket_id, reason=payload.reason, actor_user_id=actor.id)
    return {"success": True, "message": "Ticket cancelled.", "ticket": ticket}


@router.post(
    "/tickets/{ticket_id}/transfer",
    response_model=QueueTicketActionResponseSchema,
    summary="Transfer a misqueued ticket to another service point",
)
def transfer_ticket(
    ticket_id: int,
    payload: QueueTicketTransferSchema,
    actor: CurrentActiveUser,
    service: Annotated[QueueService, Depends(get_queue_service)],
    _: Annotated[User, Depends(require_any_permission("QUEUE_MANAGE", "QUEUE:MANAGE", "VISIT_ROUTE", "VISITS:ROUTE"))],
    __: Annotated[User, Depends(require_assigned_to_ticket_sdp())],
):
    """
    Use this for routing **errors** (patient was placed in the wrong queue).
    """
    new_ticket = service.transfer_ticket(
        ticket_id,
        payload.target_service_delivery_point_id,
        reason=payload.reason,
        actor_user_id=actor.id,
    )
    return {
        "success": True,
        "message": "Ticket transferred. New ticket created at the target service point.",
        "ticket": new_ticket,
    }
