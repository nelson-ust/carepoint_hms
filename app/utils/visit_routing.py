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
    OrderStatus,
    QueueStatus,
    RadiologyOrderStatus,
    ServicePointType,
    VisitFlowStepStatus,
    VisitStatus,
)
from app.core.exceptions import BadRequestError, NotFoundError
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


def validate_visit_sdp_activity(
    db: Session,
    *,
    visit_id: int,
    required_sdp_types: list[ServicePointType],
    activity_name: str,
) -> VisitFlowStep:
    """
    Validate that the visit's current SDP matches one of the required types for
    the specified activity.

    Raises BadRequestError if the patient is not currently at a valid SDP.
    """
    from app.repositories.visit_flow_repository import VisitFlowRepository
    flow_repo = VisitFlowRepository(db)

    current_step = flow_repo.get_current_visit_step(visit_id)
    if not current_step:
        raise BadRequestError(
            message=f"No active visit flow step found. Cannot perform {activity_name}.",
            detail={"visit_id": visit_id}
        )

    sdp = flow_repo.get_service_delivery_point_by_id(current_step.service_delivery_point_id)
    if not sdp or sdp.service_point_type not in required_sdp_types:
        allowed_types_str = ", ".join([str(t) for t in required_sdp_types])
        raise BadRequestError(
            message=f"{activity_name} can only be performed at a {allowed_types_str} service delivery point.",
            detail={
                "visit_id": visit_id,
                "current_sdp": sdp.name if sdp else "Unknown",
                "current_sdp_type": str(sdp.service_point_type) if sdp else "Unknown",
                "required_types": [str(t) for t in required_sdp_types]
            }
        )

    return current_step


# ============================================================
# Investigation return-loop helpers
# ============================================================

# A consultation can be resumed at any of these point types (the patient is
# sent back to the doctor who ordered the investigation).
CONSULT_SDP_TYPES = {
    ServicePointType.CLINIC,
    ServicePointType.EMERGENCY,
    ServicePointType.PROCEDURE_ROOM,
}


def resolve_ordering_consultation_sdp(db: Session, *, visit_id: int) -> Optional[int]:
    """
    Find the consulting room to send a patient back to after investigations:
    the most recent CLINIC/EMERGENCY/PROCEDURE_ROOM step on the visit, falling
    back to any clinic in the facility. Returns the SDP id or None.
    """
    steps = (
        db.query(VisitFlowStep)
        .filter(
            VisitFlowStep.visit_id == visit_id,
            VisitFlowStep.is_deleted.is_(False),
        )
        .order_by(VisitFlowStep.step_order.desc())
        .all()
    )
    for st in steps:
        sdp = (
            db.query(ServiceDeliveryPoint)
            .filter(ServiceDeliveryPoint.id == st.service_delivery_point_id)
            .first()
        )
        if sdp is not None and sdp.service_point_type in CONSULT_SDP_TYPES:
            return sdp.id

    sdp = (
        db.query(ServiceDeliveryPoint)
        .filter(
            ServiceDeliveryPoint.service_point_type == ServicePointType.CLINIC,
            ServiceDeliveryPoint.is_deleted.is_(False),
        )
        .first()
    )
    return sdp.id if sdp else None


def has_pending_investigations(db: Session, *, visit_id: int) -> bool:
    """
    True while the visit still has lab or radiology work outstanding, so the
    patient is only routed back to the doctor once every ordered investigation
    has produced a (released) result.
    """
    from app.models.all_models import LabOrder, LabOrderItem, RadiologyOrder

    lab_pending = (
        db.query(LabOrderItem.id)
        .join(LabOrder, LabOrder.id == LabOrderItem.lab_order_id)
        .filter(
            LabOrder.visit_id == visit_id,
            LabOrder.is_deleted.is_(False),
            LabOrderItem.is_deleted.is_(False),
            LabOrderItem.status.notin_(
                [OrderStatus.COMPLETED, OrderStatus.CANCELLED]
            ),
        )
        .first()
    )
    if lab_pending is not None:
        return True

    rad_pending = (
        db.query(RadiologyOrder.id)
        .filter(
            RadiologyOrder.visit_id == visit_id,
            RadiologyOrder.is_deleted.is_(False),
            RadiologyOrder.status.notin_(
                [
                    RadiologyOrderStatus.COMPLETED,
                    RadiologyOrderStatus.CANCELLED,
                    RadiologyOrderStatus.RELEASED,
                ]
            ),
        )
        .first()
    )
    return rad_pending is not None


def maybe_route_back_to_consultation(
    db: Session,
    *,
    visit_id: int,
    routed_by_id: Optional[int] = None,
    note: Optional[str] = None,
) -> Optional[tuple[VisitFlowStep, QueueTicket]]:
    """
    When a visit has no further pending investigations, route the patient back
    to the ordering consulting room for results review. No-op (returns None)
    when investigations are still outstanding, no consulting room can be found,
    or the patient is already queued at a consulting room.
    """
    if has_pending_investigations(db, visit_id=visit_id):
        return None

    target_sdp_id = resolve_ordering_consultation_sdp(db, visit_id=visit_id)
    if target_sdp_id is None:
        return None

    # Don't double-route if the patient is already at that consulting room.
    flow_repo = VisitFlowRepository(db)
    current = flow_repo.get_current_visit_step(visit_id)
    if current is not None and current.service_delivery_point_id == target_sdp_id:
        return None

    return route_visit_to_next_sdp(
        db,
        visit_id=visit_id,
        target_service_delivery_point_id=target_sdp_id,
        routed_by_id=routed_by_id,
        notes=note or "Investigations complete — returned to consulting room for review.",
    )
