# app/repositories/queue_repository.py
from __future__ import annotations

"""
Repository for queue ticket persistence and worklist queries.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import func, and_
from sqlalchemy.orm import Session, joinedload

from app.core.enums import QueueStatus
from app.core.exceptions import NotFoundError
from app.models.all_models import (
    QueueTicket,
    ServiceDeliveryPoint,
    Visit,
)
from app.utils.queue_number import generate_queue_number, normalize_queue_prefix


class QueueRepository:
    """
    Persistence layer for QueueTicket lifecycle.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ============================================================
    # LOOKUPS
    # ============================================================

    def get_by_id(self, ticket_id: int) -> Optional[QueueTicket]:
        return (
            self.db.query(QueueTicket)
            .filter(QueueTicket.id == ticket_id, QueueTicket.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, ticket_id: int) -> QueueTicket:
        ticket = self.get_by_id(ticket_id)
        if not ticket:
            raise NotFoundError(message="Queue ticket not found.", detail={"ticket_id": ticket_id})
        return ticket

    def get_service_delivery_point(self, sdp_id: int) -> Optional[ServiceDeliveryPoint]:
        return (
            self.db.query(ServiceDeliveryPoint)
            .filter(
                ServiceDeliveryPoint.id == sdp_id,
                ServiceDeliveryPoint.is_deleted.is_(False),
            )
            .first()
        )

    def get_visit(self, visit_id: int) -> Optional[Visit]:
        return (
            self.db.query(Visit)
            .filter(Visit.id == visit_id, Visit.is_deleted.is_(False))
            .first()
        )

    # ============================================================
    # NUMBERING / POSITIONING
    # ============================================================

    def next_queue_position(self, service_delivery_point_id: int) -> int:
        """
        Compute the next queue position for the active ticket set at a SDP
        (only WAITING/CALLED tickets count toward positioning).
        """
        max_position = (
            self.db.query(func.coalesce(func.max(QueueTicket.queue_position), 0))
            .filter(
                QueueTicket.service_delivery_point_id == service_delivery_point_id,
                QueueTicket.is_deleted.is_(False),
                QueueTicket.status.in_([QueueStatus.WAITING, QueueStatus.CALLED]),
            )
            .scalar()
            or 0
        )
        return int(max_position) + 1

    def next_queue_number(self, service_delivery_point_id: int) -> str:
        """
        Build a deterministic queue number using the SDP's queue_prefix and a
        sequence equal to today's tickets +1 at that SDP.
        """
        sdp = self.get_service_delivery_point(service_delivery_point_id)
        prefix = normalize_queue_prefix(getattr(sdp, "queue_prefix", None) or getattr(sdp, "code", None) or "Q")

        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        today_count = (
            self.db.query(func.count(QueueTicket.id))
            .filter(
                QueueTicket.service_delivery_point_id == service_delivery_point_id,
                QueueTicket.is_deleted.is_(False),
                QueueTicket.date_created >= start_of_day,
                QueueTicket.date_created < end_of_day,
            )
            .scalar()
            or 0
        )
        return generate_queue_number(prefix=prefix, sequence=int(today_count) + 1, when=now)

    # ============================================================
    # CREATE / UPDATE
    # ============================================================

    def create_ticket(
        self,
        *,
        visit_id: int,
        patient_id: int,
        service_delivery_point_id: int,
        visit_flow_step_id: Optional[int] = None,
        queue_number: Optional[str] = None,
        queue_position: Optional[int] = None,
        status: QueueStatus = QueueStatus.WAITING,
        transferred_from_ticket_id: Optional[int] = None,
    ) -> QueueTicket:
        ticket = QueueTicket(
            visit_id=visit_id,
            patient_id=patient_id,
            service_delivery_point_id=service_delivery_point_id,
            visit_flow_step_id=visit_flow_step_id,
            queue_number=queue_number or self.next_queue_number(service_delivery_point_id),
            queue_position=queue_position or self.next_queue_position(service_delivery_point_id),
            status=status,
            transferred_from_ticket_id=transferred_from_ticket_id,
        )
        self.db.add(ticket)
        self.db.flush()
        self.db.refresh(ticket)
        return ticket

    def save(self, ticket: QueueTicket) -> QueueTicket:
        self.db.add(ticket)
        self.db.flush()
        self.db.refresh(ticket)
        return ticket

    # ============================================================
    # WORKLISTS
    # ============================================================

    def list_for_service_point(
        self,
        service_delivery_point_id: int,
        *,
        statuses: Optional[list[QueueStatus]] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[QueueTicket], int]:
        query = (
            self.db.query(QueueTicket)
            .options(joinedload(QueueTicket.visit), joinedload(QueueTicket.patient))
            .filter(
                QueueTicket.service_delivery_point_id == service_delivery_point_id,
                QueueTicket.is_deleted.is_(False),
            )
        )
        if statuses:
            query = query.filter(QueueTicket.status.in_(statuses))

        total = query.with_entities(func.count(QueueTicket.id)).scalar() or 0
        items = (
            query.order_by(
                QueueTicket.status.asc(),
                QueueTicket.queue_position.asc().nullslast(),
                QueueTicket.id.asc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def list_for_visit(self, visit_id: int) -> list[QueueTicket]:
        return (
            self.db.query(QueueTicket)
            .filter(
                QueueTicket.visit_id == visit_id,
                QueueTicket.is_deleted.is_(False),
            )
            .order_by(QueueTicket.id.asc())
            .all()
        )

    def count_today_by_status(self, service_delivery_point_id: int, status: QueueStatus) -> int:
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        return int(
            self.db.query(func.count(QueueTicket.id))
            .filter(
                QueueTicket.service_delivery_point_id == service_delivery_point_id,
                QueueTicket.is_deleted.is_(False),
                QueueTicket.status == status,
                QueueTicket.date_updated >= start_of_day,
                QueueTicket.date_updated < end_of_day,
            )
            .scalar()
            or 0
        )

    # ============================================================
    # CURRENTLY-SERVED LOOKUP
    # ============================================================

    def has_serving_ticket(self, service_delivery_point_id: int) -> bool:
        return bool(
            self.db.query(QueueTicket.id)
            .filter(
                QueueTicket.service_delivery_point_id == service_delivery_point_id,
                QueueTicket.is_deleted.is_(False),
                QueueTicket.status == QueueStatus.SERVING,
            )
            .first()
        )

    def get_active_ticket_for_visit(self, visit_id: int) -> Optional[QueueTicket]:
        return (
            self.db.query(QueueTicket)
            .filter(
                QueueTicket.visit_id == visit_id,
                QueueTicket.is_deleted.is_(False),
                QueueTicket.status.in_([QueueStatus.WAITING, QueueStatus.CALLED, QueueStatus.SERVING]),
            )
            .order_by(QueueTicket.id.desc())
            .first()
        )

    def get_previous_tickets_for_visit(self, visit_id: int, current_ticket_id: int) -> list[QueueTicket]:
        """
        Fetch all historical tickets for the visit that occurred before the current one.
        """
        return (
            self.db.query(QueueTicket)
            .options(joinedload(QueueTicket.service_delivery_point))
            .filter(
                QueueTicket.visit_id == visit_id,
                QueueTicket.id < current_ticket_id,
                QueueTicket.is_deleted.is_(False),
                QueueTicket.status.in_([QueueStatus.SERVED, QueueStatus.TRANSFERRED]),
            )
            .order_by(QueueTicket.id.asc())
            .all()
        )

    def get_batch_previous_tickets(self, visit_ids: list[int], current_ticket_ids: list[int]) -> list[QueueTicket]:
        """
        Fetch historical tickets for multiple visits in a single query.
        """
        if not visit_ids:
            return []
            
        return (
            self.db.query(QueueTicket)
            .options(joinedload(QueueTicket.service_delivery_point))
            .filter(
                QueueTicket.visit_id.in_(visit_ids),
                QueueTicket.is_deleted.is_(False),
                QueueTicket.status.in_([QueueStatus.SERVED, QueueStatus.TRANSFERRED]),
            )
            .order_by(QueueTicket.id.asc())
            .all()
        )

    # ============================================================
    # ANALYTICS & DISPLAY BOARD
    # ============================================================

    def list_service_points(self) -> list[ServiceDeliveryPoint]:
        """All non-deleted service delivery points, name-ordered."""
        return (
            self.db.query(ServiceDeliveryPoint)
            .filter(ServiceDeliveryPoint.is_deleted.is_(False))
            .order_by(ServiceDeliveryPoint.name.asc())
            .all()
        )

    def get_stats_rows(
        self, date_from: datetime, date_to: datetime
    ) -> list[tuple]:
        """
        Raw per-ticket rows for the stats window. Aggregation happens in the
        service layer so the computation stays portable across DB backends.

        Returns tuples of:
        (sdp_id, status, date_created, called_at, service_started_at, service_ended_at)
        """
        return (
            self.db.query(
                QueueTicket.service_delivery_point_id,
                QueueTicket.status,
                QueueTicket.date_created,
                QueueTicket.called_at,
                QueueTicket.service_started_at,
                QueueTicket.service_ended_at,
            )
            .filter(
                QueueTicket.is_deleted.is_(False),
                QueueTicket.date_created >= date_from,
                QueueTicket.date_created < date_to,
            )
            .all()
        )

    def get_live_status_counts(self) -> dict[tuple[int, QueueStatus], int]:
        """
        Current WAITING / CALLED / SERVING counts per service delivery point,
        regardless of when the ticket was created.
        """
        rows = (
            self.db.query(
                QueueTicket.service_delivery_point_id,
                QueueTicket.status,
                func.count(QueueTicket.id),
            )
            .filter(
                QueueTicket.is_deleted.is_(False),
                QueueTicket.status.in_(
                    [QueueStatus.WAITING, QueueStatus.CALLED, QueueStatus.SERVING]
                ),
            )
            .group_by(QueueTicket.service_delivery_point_id, QueueTicket.status)
            .all()
        )
        return {(sdp_id, status): int(count) for sdp_id, status, count in rows}

    def get_display_tickets(self) -> list[QueueTicket]:
        """
        Active tickets (WAITING / CALLED / SERVING) across every service
        delivery point, ordered for the waiting-room display board.
        """
        return (
            self.db.query(QueueTicket)
            .options(joinedload(QueueTicket.service_delivery_point))
            .filter(
                QueueTicket.is_deleted.is_(False),
                QueueTicket.status.in_(
                    [QueueStatus.WAITING, QueueStatus.CALLED, QueueStatus.SERVING]
                ),
            )
            .order_by(
                QueueTicket.service_delivery_point_id.asc(),
                QueueTicket.queue_position.asc().nullslast(),
                QueueTicket.id.asc(),
            )
            .all()
        )
