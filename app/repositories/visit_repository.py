from __future__ import annotations

"""
app.repositories.visit_repository

Repository layer for visit initiation and operational workflow entry.

Purpose
-------
This module centralizes direct database operations for:

- retrieving patient and appointment context for visit initiation
- creating visit records
- resolving the first service delivery point
- optionally applying a visit flow template
- creating runtime visit flow steps
- creating queue tickets
- rerouting visits to new service delivery points
- switching current flow steps
- supporting queue transfer lineage
- listing and retrieving visits

Design goals
------------
- keep raw SQLAlchemy query logic out of route handlers
- keep business rules mostly out of the repository layer
- expose reusable persistence/query helpers for the service layer
- support dynamic visit workflows that can change at runtime
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.enums import (
    QueueStatus,
    VisitFlowStepStatus,
    VisitPriority,
    VisitStatus,
)
from app.models.all_models import (
    Appointment,
    Patient,
    QueueTicket,
    ServiceDeliveryPoint,
    Visit,
    VisitFlowStep,
    VisitFlowTemplate,
    VisitFlowTemplateStep,
)

try:
    from app.utils.visit_code import generate_visit_code
except Exception:
    generate_visit_code = None

try:
    from app.utils.queue_number import generate_queue_number
except Exception:
    generate_queue_number = None


class VisitRepository:
    """
    Repository for visit initiation, runtime visit flow management,
    and queue placement.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize the repository with an active SQLAlchemy session.

        Args:
            db: Active SQLAlchemy session.
        """
        self.db = db

    # ============================================================
    # BASIC LOOKUPS
    # ============================================================

    def get_patient_by_id(self, patient_id: int) -> Optional[Patient]:
        """
        Return a patient by ID if not soft-deleted.
        """
        return (
            self.db.query(Patient)
            .filter(
                Patient.id == patient_id,
                Patient.is_deleted.is_(False),
            )
            .first()
        )

    def get_service_delivery_point_by_id(
        self,
        service_delivery_point_id: int,
    ) -> Optional[ServiceDeliveryPoint]:
        """
        Return a service delivery point by ID if not soft-deleted.
        """
        return (
            self.db.query(ServiceDeliveryPoint)
            .filter(
                ServiceDeliveryPoint.id == service_delivery_point_id,
                ServiceDeliveryPoint.is_deleted.is_(False),
            )
            .first()
        )
    
    def get_service_delivery_point_by_type(
        self,
        service_point_type: str,
    ) -> Optional[ServiceDeliveryPoint]:
        """
        Return the first service delivery point matching the type.
        """
        return (
            self.db.query(ServiceDeliveryPoint)
            .filter(
                ServiceDeliveryPoint.type == service_point_type,
                ServiceDeliveryPoint.is_deleted.is_(False),
            )
            .first()
        )

    def get_appointment_by_id(self, appointment_id: int) -> Optional[Appointment]:
        """
        Return an appointment by ID if not soft-deleted.
        """
        return (
            self.db.query(Appointment)
            .options(
                joinedload(Appointment.patient),
                joinedload(Appointment.service_delivery_point),
            )
            .filter(
                Appointment.id == appointment_id,
                Appointment.is_deleted.is_(False),
            )
            .first()
        )

    def get_visit_by_id(self, visit_id: int) -> Optional[Visit]:
        """
        Return a visit by ID if not soft-deleted.
        """
        return (
            self.db.query(Visit)
            .filter(
                Visit.id == visit_id,
                Visit.is_deleted.is_(False),
            )
            .first()
        )

    def get_visit_by_code(self, visit_code: str) -> Optional[Visit]:
        """
        Return a visit by unique visit code.
        """
        return (
            self.db.query(Visit)
            .filter(
                Visit.visit_code == visit_code,
                Visit.is_deleted.is_(False),
            )
            .first()
        )

    def get_detailed_visit_by_id(self, visit_id: int) -> Optional[Visit]:
        """
        Return a visit with related patient, appointment, service-point,
        flow-step, and queue context.
        """
        return (
            self.db.query(Visit)
            .options(
                joinedload(Visit.patient),
                joinedload(Visit.appointment),
                joinedload(Visit.first_service_delivery_point),
                joinedload(Visit.current_service_delivery_point),
                selectinload(
                    Visit.flow_steps.and_(
                        VisitFlowStep.is_deleted.is_(False)
                    )
                ).joinedload(
                    VisitFlowStep.service_delivery_point
                ),
                selectinload(
                    Visit.queue_tickets.and_(
                        QueueTicket.is_deleted.is_(False)
                    )
                ).joinedload(
                    QueueTicket.service_delivery_point
                ),
            )
            .filter(
                Visit.id == visit_id,
                Visit.is_deleted.is_(False),
            )
            .first()
        )

    # ============================================================
    # TEMPLATE LOOKUPS
    # ============================================================

    def get_visit_flow_template_by_id(
        self,
        template_id: int,
    ) -> Optional[VisitFlowTemplate]:
        """
        Return a visit flow template by ID with ordered steps.
        """
        return (
            self.db.query(VisitFlowTemplate)
            .options(
                selectinload(
                    VisitFlowTemplate.steps.and_(
                        VisitFlowTemplateStep.is_deleted.is_(False)
                    )
                ).joinedload(
                    VisitFlowTemplateStep.service_delivery_point
                )
            )
            .filter(
                VisitFlowTemplate.id == template_id,
                VisitFlowTemplate.is_deleted.is_(False),
            )
            .first()
        )

    def get_visit_flow_template_by_code(
        self,
        code: str,
    ) -> Optional[VisitFlowTemplate]:
        """
        Return a visit flow template by unique code.
        """
        return (
            self.db.query(VisitFlowTemplate)
            .options(
                selectinload(
                    VisitFlowTemplate.steps.and_(
                        VisitFlowTemplateStep.is_deleted.is_(False)
                    )
                ).joinedload(
                    VisitFlowTemplateStep.service_delivery_point
                )
            )
            .filter(
                VisitFlowTemplate.code == code,
                VisitFlowTemplate.is_deleted.is_(False),
            )
            .first()
        )

    def get_default_visit_flow_template(self) -> Optional[VisitFlowTemplate]:
        """
        Return the tenant's default visit flow template (care pathway).

        Preference order:
        1. The standard outpatient pathway (code ``STANDARD_OPD``)
        2. The earliest active template that actually has steps

        Returns ``None`` when no usable template exists. Templates are returned
        with their ordered, non-deleted steps eagerly loaded so the caller can
        resolve the first service delivery point immediately.
        """
        standard = self.get_visit_flow_template_by_code("STANDARD_OPD")
        if standard is not None and standard.steps:
            return standard

        rows = (
            self.db.query(VisitFlowTemplate)
            .filter(VisitFlowTemplate.is_deleted.is_(False))
            .order_by(VisitFlowTemplate.id.asc())
            .all()
        )
        for row in rows:
            full = self.get_visit_flow_template_by_id(row.id)
            if full is not None and full.steps:
                return full
        return None

    # ============================================================
    # LIST / SEARCH
    # ============================================================

    def list_visits(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        patient_id: Optional[int] = None,
        appointment_id: Optional[int] = None,
        status: Optional[VisitStatus | str] = None,
        priority: Optional[VisitPriority | str] = None,
        service_delivery_point_id: Optional[int] = None,
    ) -> tuple[list[Visit], int]:
        """
        Return paginated visits with optional filters.
        """
        # Define base filters to reuse in both count and data queries
        base_filters = [Visit.is_deleted.is_(False)]
        
        if patient_id is not None:
            base_filters.append(Visit.patient_id == patient_id)
        if appointment_id is not None:
            base_filters.append(Visit.appointment_id == appointment_id)
        if status is not None:
            base_filters.append(Visit.status == status)
        if priority is not None:
            base_filters.append(Visit.priority == priority)
        if service_delivery_point_id is not None:
            base_filters.append(
                (Visit.current_service_delivery_point_id == service_delivery_point_id)
                | (Visit.first_service_delivery_point_id == service_delivery_point_id)
            )

        # 1. Count query - Lightweight
        total = (
            self.db.query(func.count(Visit.id))
            .filter(*base_filters)
            .scalar()
        ) or 0

        if total == 0:
            return [], 0

        # 2. Data query - Eager load primary contexts
        items = (
            self.db.query(Visit)
            .filter(*base_filters)
            .options(
                joinedload(Visit.patient),
                joinedload(Visit.appointment),
                joinedload(Visit.first_service_delivery_point),
                joinedload(Visit.current_service_delivery_point),
            )
            .order_by(Visit.visit_date.desc(), Visit.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return items, int(total)

    # ============================================================
    # VISIT INITIATION HELPERS
    # ============================================================

    def resolve_first_service_delivery_point(
        self,
        *,
        first_service_delivery_point_id: Optional[int] = None,
        use_appointment_service_point: bool = False,
        appointment: Optional[Appointment] = None,
        visit_flow_template: Optional[VisitFlowTemplate] = None,
    ) -> "tuple[Optional[ServiceDeliveryPoint], Optional[str]]":
        """
        Resolve the first service delivery point for a visit.

        Returns a ``(service_delivery_point, source)`` tuple where ``source`` is
        one of ``"explicit"``, ``"appointment"`` or ``"template"`` (or ``None``
        when nothing resolved). The source lets the caller apply the right
        validation - e.g. only require appointment-support when the point
        actually came from the appointment, so a template-driven first stage
        (Registration/Triage) is never rejected for "not supporting
        appointments".

        Resolution order
        ----------------
        1. Explicit first_service_delivery_point_id
        2. Appointment service point when requested and present
        3. First step from the visit flow template (the care pathway)
        """
        if first_service_delivery_point_id is not None:
            return (
                self.get_service_delivery_point_by_id(first_service_delivery_point_id),
                "explicit",
            )

        if use_appointment_service_point and appointment is not None:
            if appointment.service_delivery_point_id is not None:
                return (
                    self.get_service_delivery_point_by_id(
                        appointment.service_delivery_point_id
                    ),
                    "appointment",
                )

        if visit_flow_template is not None and visit_flow_template.steps:
            first_step = sorted(visit_flow_template.steps, key=lambda x: x.step_order)[0]
            return (
                self.get_service_delivery_point_by_id(first_step.service_delivery_point_id),
                "template",
            )

        return None, None

    def get_next_visit_flow_step_order(self, visit_id: int) -> int:
        """
        Return the next step order number for a visit.
        """
        current_max = (
            self.db.query(func.max(VisitFlowStep.step_order))
            .filter(
                VisitFlowStep.visit_id == visit_id,
                VisitFlowStep.is_deleted.is_(False),
            )
            .scalar()
        )
        return int(current_max or 0) + 1

    def get_next_queue_position(
        self,
        *,
        service_delivery_point_id: int,
        active_statuses: Optional[list[QueueStatus]] = None,
    ) -> int:
        """
        Calculate the next queue position for a service delivery point.
        """
        statuses = active_statuses or [
            QueueStatus.WAITING,
            QueueStatus.CALLED,
            QueueStatus.SERVING,
        ]

        current_max = (
            self.db.query(func.max(QueueTicket.queue_position))
            .filter(
                QueueTicket.service_delivery_point_id == service_delivery_point_id,
                QueueTicket.status.in_(statuses),
                QueueTicket.is_deleted.is_(False),
            )
            .scalar()
        )
        return int(current_max or 0) + 1

    def generate_unique_visit_code(
        self,
        *,
        patient_id: int,
        when: Optional[datetime] = None,
        max_attempts: int = 20,
    ) -> str:
        """
        Generate a unique visit code.
        """
        current = when or datetime.now(timezone.utc)

        for attempt in range(max_attempts):
            if generate_visit_code:
                candidate = generate_visit_code(
                    patient_identifier=patient_id,
                    when=current,
                )
            else:
                candidate = f"VIS-{current.strftime('%Y%m%d-%H%M%S')}-{patient_id}"

            if attempt:
                candidate = f"{candidate}-{attempt}"

            existing = self.get_visit_by_code(candidate)
            if not existing:
                return candidate

        raise ValueError("Unable to generate a unique visit code.")

    def generate_queue_number_for_service_point(
        self,
        *,
        service_delivery_point: ServiceDeliveryPoint,
        sequence: int,
        when: Optional[datetime] = None,
    ) -> str:
        """
        Generate a queue number for a service delivery point.
        """
        prefix = service_delivery_point.queue_prefix or service_delivery_point.code

        if generate_queue_number:
            return generate_queue_number(
                prefix=prefix,
                sequence=sequence,
                when=when,
            )

        current = when or datetime.now(timezone.utc)
        return f"{prefix}-{current.strftime('%Y%m%d')}-{sequence:04d}"

    # ============================================================
    # CREATE VISIT / FLOW STEP / QUEUE TICKET
    # ============================================================

    def create_visit(
        self,
        *,
        patient_id: int,
        visit_code: str,
        visit_reason: Optional[str] = None,
        appointment_id: Optional[int] = None,
        visit_date: Optional[datetime] = None,
        status: VisitStatus = VisitStatus.INITIATED,
        priority: VisitPriority = VisitPriority.NORMAL,
        first_service_delivery_point_id: Optional[int] = None,
        current_service_delivery_point_id: Optional[int] = None,
        referred_from: Optional[str] = None,
        check_in_time: Optional[datetime] = None,
    ) -> Visit:
        """
        Create and persist a visit record.
        """
        visit = Visit(
            patient_id=patient_id,
            appointment_id=appointment_id,
            visit_code=visit_code,
            visit_date=visit_date or datetime.now(timezone.utc),
            status=status,
            priority=priority,
            first_service_delivery_point_id=first_service_delivery_point_id,
            current_service_delivery_point_id=current_service_delivery_point_id,
            referred_from=referred_from,
            visit_reason=visit_reason,
            check_in_time=check_in_time,
        )
        self.db.add(visit)
        self.db.flush()
        self.db.refresh(visit)
        return visit

    def create_visit_flow_step(
        self,
        *,
        visit_id: int,
        service_delivery_point_id: int,
        step_order: int,
        status: VisitFlowStepStatus = VisitFlowStepStatus.PENDING,
        is_current: bool = False,
        is_required: bool = True,
        is_skipped: bool = False,
        routed_by_id: Optional[int] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> VisitFlowStep:
        """
        Create and persist a runtime visit flow step.
        """
        flow_step = VisitFlowStep(
            visit_id=visit_id,
            service_delivery_point_id=service_delivery_point_id,
            step_order=step_order,
            status=status,
            is_current=is_current,
            is_required=is_required,
            is_skipped=is_skipped,
            routed_by_id=routed_by_id,
            started_at=started_at,
            completed_at=completed_at,
            notes=notes,
        )
        self.db.add(flow_step)
        self.db.flush()
        self.db.refresh(flow_step)
        return flow_step

    def create_first_visit_flow_step(
        self,
        *,
        visit_id: int,
        service_delivery_point_id: int,
        step_order: int = 1,
        status: VisitFlowStepStatus = VisitFlowStepStatus.PENDING,
        is_current: bool = True,
        is_required: bool = True,
        is_skipped: bool = False,
        routed_by_id: Optional[int] = None,
        started_at: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> VisitFlowStep:
        """
        Convenience helper for the first runtime flow step.
        """
        return self.create_visit_flow_step(
            visit_id=visit_id,
            service_delivery_point_id=service_delivery_point_id,
            step_order=step_order,
            status=status,
            is_current=is_current,
            is_required=is_required,
            is_skipped=is_skipped,
            routed_by_id=routed_by_id,
            started_at=started_at,
            notes=notes,
        )

    def create_flow_steps_from_template(
        self,
        *,
        visit_id: int,
        template: VisitFlowTemplate,
        first_step_status: VisitFlowStepStatus = VisitFlowStepStatus.PENDING,
        routed_by_id: Optional[int] = None,
        started_at_for_first: Optional[datetime] = None,
    ) -> list[VisitFlowStep]:
        """
        Create runtime visit flow steps from a reusable template.

        The first step is marked current by default.
        """
        created_steps: list[VisitFlowStep] = []

        steps = sorted(template.steps, key=lambda x: x.step_order)
        for index, template_step in enumerate(steps, start=1):
            step = self.create_visit_flow_step(
                visit_id=visit_id,
                service_delivery_point_id=template_step.service_delivery_point_id,
                step_order=index,
                status=first_step_status if index == 1 else VisitFlowStepStatus.PENDING,
                is_current=index == 1,
                is_required=template_step.is_required,
                is_skipped=False,
                routed_by_id=routed_by_id,
                started_at=started_at_for_first if index == 1 else None,
                notes=template_step.notes,
            )
            created_steps.append(step)

        return created_steps

    def create_queue_ticket(
        self,
        *,
        visit_id: int,
        patient_id: int,
        service_delivery_point_id: int,
        queue_number: str,
        queue_position: Optional[int] = None,
        status: QueueStatus = QueueStatus.WAITING,
        visit_flow_step_id: Optional[int] = None,
        transferred_from_ticket_id: Optional[int] = None,
    ) -> QueueTicket:
        """
        Create a queue ticket for a service delivery point.
        """
        ticket = QueueTicket(
            visit_id=visit_id,
            visit_flow_step_id=visit_flow_step_id,
            patient_id=patient_id,
            service_delivery_point_id=service_delivery_point_id,
            queue_number=queue_number,
            queue_position=queue_position,
            status=status,
            transferred_from_ticket_id=transferred_from_ticket_id,
        )
        self.db.add(ticket)
        self.db.flush()
        self.db.refresh(ticket)
        return ticket

    # ============================================================
    # CURRENT STEP / FLOW CONTROL
    # ============================================================

    def get_current_visit_flow_step(self, visit_id: int) -> Optional[VisitFlowStep]:
        """
        Return the current runtime flow step for a visit.
        """
        return (
            self.db.query(VisitFlowStep)
            .filter(
                VisitFlowStep.visit_id == visit_id,
                VisitFlowStep.is_current.is_(True),
                VisitFlowStep.is_deleted.is_(False),
            )
            .first()
        )

    def list_visit_flow_steps(self, visit_id: int) -> list[VisitFlowStep]:
        """
        Return all runtime flow steps for a visit ordered by step_order.
        """
        return (
            self.db.query(VisitFlowStep)
            .options(joinedload(VisitFlowStep.service_delivery_point))
            .filter(
                VisitFlowStep.visit_id == visit_id,
                VisitFlowStep.is_deleted.is_(False),
            )
            .order_by(VisitFlowStep.step_order.asc())
            .all()
        )

    def clear_current_flags_for_visit(self, visit_id: int) -> None:
        """
        Clear current-step flags for all runtime steps in a visit.
        """
        steps = (
            self.db.query(VisitFlowStep)
            .filter(
                VisitFlowStep.visit_id == visit_id,
                VisitFlowStep.is_current.is_(True),
                VisitFlowStep.is_deleted.is_(False),
            )
            .all()
        )
        for step in steps:
            step.is_current = False
            self.db.add(step)
        self.db.flush()

    def mark_flow_step_as_current(self, flow_step: VisitFlowStep) -> VisitFlowStep:
        """
        Mark the supplied flow step as the current step for its visit.
        """
        self.clear_current_flags_for_visit(flow_step.visit_id)
        flow_step.is_current = True
        self.db.add(flow_step)
        self.db.flush()
        self.db.refresh(flow_step)
        return flow_step

    def cancel_pending_flow_steps(self, visit_id: int) -> int:
        """
        Cancel all PENDING or QUEUED runtime steps for a visit.
        """
        steps = (
            self.db.query(VisitFlowStep)
            .filter(
                VisitFlowStep.visit_id == visit_id,
                VisitFlowStep.status.in_([VisitFlowStepStatus.PENDING, VisitFlowStepStatus.QUEUED]),
                VisitFlowStep.is_deleted.is_(False),
            )
            .all()
        )
        for step in steps:
            step.status = VisitFlowStepStatus.CANCELLED
            step.is_current = False
            self.db.add(step)
        self.db.flush()
        return len(steps)

    def append_flow_steps_from_template(
        self,
        *,
        visit_id: int,
        template: VisitFlowTemplate,
        first_step_status: VisitFlowStepStatus = VisitFlowStepStatus.PENDING,
        routed_by_id: Optional[int] = None,
        started_at_for_first: Optional[datetime] = None,
        mark_first_as_current: bool = True,
    ) -> list[VisitFlowStep]:
        """
        Append runtime visit flow steps from a template to an existing visit flow.
        """
        next_order = self.get_next_visit_flow_step_order(visit_id)
        created_steps: list[VisitFlowStep] = []

        if mark_first_as_current:
            self.clear_current_flags_for_visit(visit_id)

        steps = sorted(template.steps, key=lambda x: x.step_order)
        for index, template_step in enumerate(steps):
            step = self.create_visit_flow_step(
                visit_id=visit_id,
                service_delivery_point_id=template_step.service_delivery_point_id,
                step_order=next_order + index,
                status=first_step_status if index == 0 else VisitFlowStepStatus.PENDING,
                is_current=mark_first_as_current if index == 0 else False,
                is_required=template_step.is_required,
                is_skipped=False,
                routed_by_id=routed_by_id,
                started_at=started_at_for_first if index == 0 else None,
                notes=template_step.notes,
            )
            created_steps.append(step)

        return created_steps

    # ============================================================
    # QUEUE HELPERS / TRANSFERS
    # ============================================================

    def get_latest_queue_ticket_for_visit(
        self,
        visit_id: int,
    ) -> Optional[QueueTicket]:
        """
        Return the most recently created queue ticket for a visit.
        """
        return (
            self.db.query(QueueTicket)
            .filter(
                QueueTicket.visit_id == visit_id,
                QueueTicket.is_deleted.is_(False),
            )
            .order_by(QueueTicket.date_created.desc(), QueueTicket.id.desc())
            .first()
        )

    def list_queue_tickets_for_visit(self, visit_id: int) -> list[QueueTicket]:
        """
        Return queue tickets for a visit ordered by creation time.
        """
        return (
            self.db.query(QueueTicket)
            .options(joinedload(QueueTicket.service_delivery_point))
            .filter(
                QueueTicket.visit_id == visit_id,
                QueueTicket.is_deleted.is_(False),
            )
            .order_by(QueueTicket.date_created.asc(), QueueTicket.id.asc())
            .all()
        )

    # ============================================================
    # REROUTE SUPPORT
    # ============================================================

    def create_rerouted_flow_step(
        self,
        *,
        visit_id: int,
        service_delivery_point_id: int,
        routed_by_id: Optional[int] = None,
        status: VisitFlowStepStatus = VisitFlowStepStatus.PENDING,
        is_required: bool = True,
        notes: Optional[str] = None,
        mark_as_current: bool = True,
    ) -> VisitFlowStep:
        """
        Create a new runtime flow step for a reroute.

        The new step is appended at the end of the current flow.
        """
        next_order = self.get_next_visit_flow_step_order(visit_id)

        if mark_as_current:
            self.clear_current_flags_for_visit(visit_id)

        step = self.create_visit_flow_step(
            visit_id=visit_id,
            service_delivery_point_id=service_delivery_point_id,
            step_order=next_order,
            status=status,
            is_current=mark_as_current,
            is_required=is_required,
            is_skipped=False,
            routed_by_id=routed_by_id,
            started_at=None,
            completed_at=None,
            notes=notes,
        )
        return step

    def create_rerouted_queue_ticket(
        self,
        *,
        visit_id: int,
        visit_flow_step_id: int,
        patient_id: int,
        service_delivery_point: ServiceDeliveryPoint,
        status: QueueStatus = QueueStatus.WAITING,
        queue_position: Optional[int] = None,
        transferred_from_ticket_id: Optional[int] = None,
        when: Optional[datetime] = None,
    ) -> QueueTicket:
        """
        Create a new queue ticket for a rerouted visit step.
        """
        position = queue_position or self.get_next_queue_position(
            service_delivery_point_id=service_delivery_point.id,
        )
        queue_number = self.generate_queue_number_for_service_point(
            service_delivery_point=service_delivery_point,
            sequence=position,
            when=when,
        )

        return self.create_queue_ticket(
            visit_id=visit_id,
            visit_flow_step_id=visit_flow_step_id,
            patient_id=patient_id,
            service_delivery_point_id=service_delivery_point.id,
            queue_number=queue_number,
            queue_position=position,
            status=status,
            transferred_from_ticket_id=transferred_from_ticket_id,
        )

    # ============================================================
    # UPDATE HELPERS
    # ============================================================

    def update_visit(self, visit: Visit) -> Visit:
        """
        Persist updates to an existing visit.
        """
        self.db.add(visit)
        self.db.flush()
        self.db.refresh(visit)
        return visit

    def update_visit_flow_step(self, flow_step: VisitFlowStep) -> VisitFlowStep:
        """
        Persist updates to a visit flow step.
        """
        self.db.add(flow_step)
        self.db.flush()
        self.db.refresh(flow_step)
        return flow_step

    def update_queue_ticket(self, ticket: QueueTicket) -> QueueTicket:
        """
        Persist updates to a queue ticket.
        """
        self.db.add(ticket)
        self.db.flush()
        self.db.refresh(ticket)
        return ticket

    # ============================================================
    # OPERATIONAL CHECKS
    # ============================================================

    def patient_has_open_or_waiting_visit(self, patient_id: int) -> bool:
        """
        Check whether a patient already has an active visit.
        """
        count = (
            self.db.query(func.count(Visit.id))
            .filter(
                Visit.patient_id == patient_id,
                Visit.status.in_(
                    [
                        VisitStatus.INITIATED,
                        VisitStatus.WAITING,
                        VisitStatus.IN_PROGRESS,
                        VisitStatus.ON_HOLD,
                    ]
                ),
                Visit.is_deleted.is_(False),
            )
            .scalar()
            or 0
        )
        return count > 0

    def service_delivery_point_supports_walk_in(
        self,
        service_delivery_point_id: int,
    ) -> bool:
        """
        Check whether a service delivery point supports walk-in visits.
        """
        sdp = self.get_service_delivery_point_by_id(service_delivery_point_id)
        return bool(sdp and sdp.supports_walk_in)

    def service_delivery_point_supports_appointments(
        self,
        service_delivery_point_id: int,
    ) -> bool:
        """
        Check whether a service delivery point supports appointment-linked visits.
        """
        sdp = self.get_service_delivery_point_by_id(service_delivery_point_id)
        return bool(sdp and sdp.supports_appointments)