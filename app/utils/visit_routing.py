# app/utils/visit_routing.py
from __future__ import annotations

"""
Helpers used across clinical/lab/pharmacy services to advance a Visit
to the next service delivery point.

The helpers handle:
- closing the current VisitFlowStep
- creating a new VisitFlowStep at the target SDP
- creating a QueueTicket at the new SDP
- updating Visit.current_service_delivery_point_id
- ending the visit if requested
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    QueueStatus,
    VisitFlowStepStatus,
    VisitStatus,
)
from app.core.exceptions import NotFoundError
from app.models.all_models import (
    QueueTicket,
    ServiceDeliveryPoint,
    Visit,
    VisitFlowStep,
)
from app.repositories.queue_repository import QueueRepository
from app.repositories.visit_flow_repository import VisitFlowRepository


def route_visit_to_next_sdp(
    db: Session,
    *,
    visit_id: int,
    target_service_delivery_point_id: int,
    routed_by_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> tuple[VisitFlowStep, QueueTicket]:
    """
    Append a new flow step at `target_service_delivery_point_id`, mark it as
    current, close the previous current step (if any), and emit a queue ticket.

    Returns:
        tuple[VisitFlowStep, QueueTicket]: the new step and the new queue ticket.
    """
    flow_repo = VisitFlowRepository(db)
    queue_repo = QueueRepository(db)

    visit = flow_repo.get_visit_by_id(visit_id)
    if not visit:
        raise NotFoundError(message="Visit not found.", detail={"visit_id": visit_id})

    sdp = flow_repo.get_service_delivery_point_by_id(target_service_delivery_point_id)
    if not sdp:
        raise NotFoundError(
            message="Target service delivery point not found.",
            detail={"service_delivery_point_id": target_service_delivery_point_id},
        )

    now = datetime.now(timezone.utc)

    # Close any currently active step.
    current = flow_repo.get_current_visit_step(visit_id)
    if current is not None:
        if current.status not in {
            VisitFlowStepStatus.COMPLETED,
            VisitFlowStepStatus.SKIPPED,
            VisitFlowStepStatus.CANCELLED,
            VisitFlowStepStatus.FAILED,
        }:
            current.status = VisitFlowStepStatus.COMPLETED
            current.completed_at = now
        current.is_current = False
        flow_repo.update_visit_step(current)

    # Determine next step order.
    next_order = flow_repo.get_next_visit_step_order(visit_id)

    new_step = flow_repo.create_visit_step(
        visit_id=visit.id,
        service_delivery_point_id=sdp.id,
        step_order=next_order,
        status=VisitFlowStepStatus.QUEUED,
        is_current=True,
        is_required=True,
        is_skipped=False,
        routed_by_id=routed_by_id,
        started_at=None,
        completed_at=None,
        notes=notes,
    )

    new_ticket = queue_repo.create_ticket(
        visit_id=visit.id,
        patient_id=visit.patient_id,
        service_delivery_point_id=sdp.id,
        visit_flow_step_id=new_step.id,
        status=QueueStatus.WAITING,
    )

    visit.current_service_delivery_point_id = sdp.id
    if visit.status not in {VisitStatus.COMPLETED, VisitStatus.CANCELLED}:
        visit.status = VisitStatus.IN_PROGRESS
    db.add(visit)
    db.flush()

    return new_step, new_ticket


def end_visit(
    db: Session,
    *,
    visit_id: int,
    actor_user_id: Optional[int] = None,
    note: Optional[str] = None,
) -> Visit:
    """
    Close out a visit at its current SDP and set status to COMPLETED.
    """
    flow_repo = VisitFlowRepository(db)
    visit = flow_repo.get_visit_by_id(visit_id)
    if not visit:
        raise NotFoundError(message="Visit not found.", detail={"visit_id": visit_id})

    now = datetime.now(timezone.utc)
    current = flow_repo.get_current_visit_step(visit_id)
    if current is not None and current.status not in {
        VisitFlowStepStatus.COMPLETED,
        VisitFlowStepStatus.CANCELLED,
        VisitFlowStepStatus.SKIPPED,
        VisitFlowStepStatus.FAILED,
    }:
        current.status = VisitFlowStepStatus.COMPLETED
        current.completed_at = now
        current.is_current = False
        flow_repo.update_visit_step(current)

    visit.status = VisitStatus.COMPLETED
    visit.check_out_time = now
    db.add(visit)
    db.flush()
    return visit
