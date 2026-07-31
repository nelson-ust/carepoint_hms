# app/services/procedure_service.py
from __future__ import annotations

"""
Service layer for clinical procedure orders.

Composes:
- :class:`ProcedureCatalogRepository` / :class:`ProcedureOrderRepository`
- :mod:`app.utils.charge_capture` — captures one BillingItem per ordered procedure
- :mod:`app.utils.security_event_util` — audit trail

Lifecycle (per order):
    DRAFT -> ORDERED -> IN_PROGRESS -> COMPLETED
                                    \\-> CANCELLED
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import OrderStatus, VisitStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import ProcedureCatalog, ProcedureOrder
from app.repositories.procedure_repository import (
    ProcedureCatalogRepository,
    ProcedureOrderRepository,
)
from app.schemas.procedure_schema import (
    ProcedureCatalogCreateSchema,
    ProcedureCatalogUpdateSchema,
    ProcedureOrderCreateSchema,
    ProcedureOrderTransitionSchema,
)
from app.utils.charge_capture import (
    add_charge,
    resolve_billable_service,
    get_or_create_open_billing,
)
from app.utils.security_event_util import record_security_event


# ============================================================
# CATALOG SERVICE
# ============================================================


class ProcedureCatalogService:
    """CRUD over the procedure master catalog."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ProcedureCatalogRepository(db)

    def list_procedures(self, *, skip=0, limit=50, search=None):
        return self.repository.list_procedures(skip=skip, limit=limit, search=search)

    def get(self, procedure_id: int) -> ProcedureCatalog:
        return self.repository.get_required_by_id(procedure_id)

    def create(self, payload: ProcedureCatalogCreateSchema) -> ProcedureCatalog:
        p = self.repository.create(**payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(p.id)

    def update(self, procedure_id: int, payload: ProcedureCatalogUpdateSchema) -> ProcedureCatalog:
        p = self.repository.get_required_by_id(procedure_id)
        updated = self.repository.update(p, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def soft_delete(self, procedure_id: int) -> ProcedureCatalog:
        p = self.repository.get_required_by_id(procedure_id)
        p = self.repository.soft_delete(p)
        self.db.commit()
        return p


# ============================================================
# ORDER SERVICE
# ============================================================


class ProcedureOrderService:
    """Service for procedure-order lifecycle."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ProcedureOrderRepository(db)
        self.catalog_repository = ProcedureCatalogRepository(db)

    # ------- READS -------

    def get(self, order_id: int) -> ProcedureOrder:
        return self.repository.get_required_by_id(order_id)

    def list_for_visit(self, visit_id: int, *, skip=0, limit=50):
        return self.repository.list_for_visit(visit_id, skip=skip, limit=limit)

    def list_open(self, *, skip=0, limit=50):
        return self.repository.list_open(skip=skip, limit=limit)

    # ------- ORDER -------

    def order_procedure(
        self,
        payload: ProcedureOrderCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ProcedureOrder:
        """Order a procedure for a visit and capture a billing line idempotently."""
        visit = self.repository.get_visit(payload.visit_id)
        if visit is None:
            raise NotFoundError(message="Visit not found.", detail={"visit_id": payload.visit_id})
        if visit.status in {VisitStatus.COMPLETED, VisitStatus.CANCELLED}:
            raise BadRequestError(
                message="Cannot order procedures on a closed visit.",
                detail={"visit_status": str(visit.status)},
            )

        catalog = self.catalog_repository.get_required_by_id(payload.procedure_catalog_id)

        order = self.repository.create(
            visit_id=visit.id,
            consultation_id=payload.consultation_id,
            procedure_catalog_id=catalog.id,
            ordered_by_staff_id=payload.ordered_by_staff_id,
            notes=payload.notes,
        )

        # Charge capture — one BillingItem per ordered procedure, idempotent on
        # source_reference = "PROCEDURE_ORDER:{id}". Re-emits are safe.
        if payload.auto_capture_charge:
            billing = get_or_create_open_billing(self.db, visit=visit)
            unit_price = Decimal(catalog.default_price or 0)
            billable = resolve_billable_service(
                self.db,
                code=f"PROC-{catalog.code}",
                name=f"Procedure: {catalog.name}",
                default_price=unit_price,
                category="PROCEDURE",
                domain="PROCEDURE",
            )
            add_charge(
                self.db,
                billing=billing,
                service_name=f"Procedure: {catalog.name}",
                service_code=f"PROC-{catalog.code}",
                unit_price=unit_price,
                quantity=Decimal("1"),
                billable_service_id=billable.id,
                source_reference=f"PROCEDURE_ORDER:{order.id}",
            )

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="PROCEDURE_ORDERED",
            severity="INFO",
            event_detail=f"Procedure {catalog.code} ordered for visit {visit.id}.",
            event_metadata={"order_id": order.id, "visit_id": visit.id, "procedure_code": catalog.code},
        )
        self.db.commit()
        return self.repository.get_required_by_id(order.id)

    # ------- LIFECYCLE TRANSITIONS -------

    def start_procedure(
        self,
        order_id: int,
        payload: ProcedureOrderTransitionSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ProcedureOrder:
        """Move ORDERED → IN_PROGRESS."""
        order = self.repository.get_required_by_id(order_id)
        if order.status != OrderStatus.ORDERED:
            raise BadRequestError(
                message="Only ORDERED procedures can be started.",
                detail={"status": str(order.status)},
            )
        order.status = OrderStatus.IN_PROGRESS
        if payload.performed_by_staff_id is not None:
            order.performed_by_staff_id = payload.performed_by_staff_id
        self.repository.save(order)
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="PROCEDURE_STARTED",
            severity="INFO",
            event_detail=f"Procedure order {order.id} started.",
            event_metadata={"order_id": order.id},
        )
        self.db.commit()
        return self.repository.get_required_by_id(order.id)

    def complete_procedure(
        self,
        order_id: int,
        payload: ProcedureOrderTransitionSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ProcedureOrder:
        """Move IN_PROGRESS → COMPLETED with findings captured."""
        order = self.repository.get_required_by_id(order_id)
        if order.status not in {OrderStatus.IN_PROGRESS, OrderStatus.ORDERED}:
            raise BadRequestError(
                message="Only ORDERED or IN_PROGRESS procedures can be completed.",
                detail={"status": str(order.status)},
            )
        order.status = OrderStatus.COMPLETED
        order.performed_at = datetime.now(timezone.utc)
        if payload.performed_by_staff_id is not None:
            order.performed_by_staff_id = payload.performed_by_staff_id
        if payload.findings:
            order.findings = payload.findings
        if payload.note:
            order.notes = ((order.notes or "") + ("\n\n" if order.notes else "") + payload.note).strip()
        self.repository.save(order)
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="PROCEDURE_COMPLETED",
            severity="INFO",
            event_detail=f"Procedure order {order.id} completed.",
            event_metadata={"order_id": order.id},
        )
        self.db.commit()
        return self.repository.get_required_by_id(order.id)

    def cancel_procedure(
        self,
        order_id: int,
        payload: ProcedureOrderTransitionSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ProcedureOrder:
        """Cancel a not-yet-completed order."""
        order = self.repository.get_required_by_id(order_id)
        if order.status in {OrderStatus.COMPLETED, OrderStatus.CANCELLED}:
            raise BadRequestError(
                message="Order is already in a terminal state.",
                detail={"status": str(order.status)},
            )
        order.status = OrderStatus.CANCELLED
        if payload.note:
            order.notes = ((order.notes or "") + ("\n\n" if order.notes else "") + f"[CANCELLED] {payload.note}").strip()
        self.repository.save(order)
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="PROCEDURE_CANCELLED",
            severity="WARNING",
            event_detail=f"Procedure order {order.id} cancelled.",
            event_metadata={"order_id": order.id, "reason": payload.note},
        )
        self.db.commit()
        return self.repository.get_required_by_id(order.id)
