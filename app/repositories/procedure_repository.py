# app/repositories/procedure_repository.py
from __future__ import annotations

"""
Repository layer for clinical procedure orders.

Provides:
- ``ProcedureCatalogRepository`` — master catalog CRUD
- ``ProcedureOrderRepository``   — per-visit ordered procedures + lifecycle helpers
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.enums import OrderStatus
from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.all_models import ProcedureCatalog, ProcedureOrder, Visit


# ============================================================
# CATALOG
# ============================================================


class ProcedureCatalogRepository:
    """Persistence helpers for ``ProcedureCatalog``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, procedure_id: int) -> Optional[ProcedureCatalog]:
        return (
            self.db.query(ProcedureCatalog)
            .filter(
                ProcedureCatalog.id == procedure_id,
                ProcedureCatalog.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, procedure_id: int) -> ProcedureCatalog:
        p = self.get_by_id(procedure_id)
        if not p:
            raise NotFoundError(message="Procedure not found.", detail={"procedure_id": procedure_id})
        return p

    def get_by_code(self, code: str) -> Optional[ProcedureCatalog]:
        return (
            self.db.query(ProcedureCatalog)
            .filter(
                func.upper(ProcedureCatalog.code) == code.strip().upper(),
                ProcedureCatalog.is_deleted.is_(False),
            )
            .first()
        )

    def list_procedures(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> tuple[list[ProcedureCatalog], int]:
        query = self.db.query(ProcedureCatalog).filter(ProcedureCatalog.is_deleted.is_(False))
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(ProcedureCatalog.name).like(term),
                    func.lower(ProcedureCatalog.code).like(term),
                )
            )
        total = query.with_entities(func.count(ProcedureCatalog.id)).scalar() or 0
        items = query.order_by(ProcedureCatalog.name.asc()).offset(skip).limit(limit).all()
        return items, int(total)

    def create(self, **kwargs) -> ProcedureCatalog:
        if self.get_by_code(kwargs["code"]):
            raise AlreadyExistsError(
                message="A procedure with this code already exists.",
                detail={"code": kwargs["code"]},
            )
        p = ProcedureCatalog(**kwargs)
        self.db.add(p)
        self.db.flush()
        self.db.refresh(p)
        return p

    def update(self, p: ProcedureCatalog, **kwargs) -> ProcedureCatalog:
        for field, value in kwargs.items():
            if value is not None:
                setattr(p, field, value)
        self.db.add(p)
        self.db.flush()
        self.db.refresh(p)
        return p

    def soft_delete(self, p: ProcedureCatalog) -> ProcedureCatalog:
        p.is_deleted = True
        self.db.add(p)
        self.db.flush()
        return p


# ============================================================
# ORDER
# ============================================================


class ProcedureOrderRepository:
    """Persistence helpers for ``ProcedureOrder``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_visit(self, visit_id: int) -> Optional[Visit]:
        return (
            self.db.query(Visit)
            .filter(Visit.id == visit_id, Visit.is_deleted.is_(False))
            .first()
        )

    def get_by_id(self, order_id: int) -> Optional[ProcedureOrder]:
        return (
            self.db.query(ProcedureOrder)
            .filter(ProcedureOrder.id == order_id, ProcedureOrder.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, order_id: int) -> ProcedureOrder:
        o = self.get_by_id(order_id)
        if not o:
            raise NotFoundError(message="Procedure order not found.", detail={"order_id": order_id})
        return o

    def list_for_visit(
        self,
        visit_id: int,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ProcedureOrder], int]:
        query = self.db.query(ProcedureOrder).filter(
            ProcedureOrder.visit_id == visit_id,
            ProcedureOrder.is_deleted.is_(False),
        )
        total = query.with_entities(func.count(ProcedureOrder.id)).scalar() or 0
        items = (
            query.order_by(ProcedureOrder.id.desc()).offset(skip).limit(limit).all()
        )
        return items, int(total)

    def list_open(self, *, skip: int = 0, limit: int = 50) -> tuple[list[ProcedureOrder], int]:
        """Open orders (not COMPLETED / CANCELLED). Used by procedure-room worklists."""
        query = self.db.query(ProcedureOrder).filter(
            ProcedureOrder.is_deleted.is_(False),
            ProcedureOrder.status.in_(
                [OrderStatus.ORDERED, OrderStatus.IN_PROGRESS, OrderStatus.RESULT_READY]
            ),
        )
        total = query.with_entities(func.count(ProcedureOrder.id)).scalar() or 0
        items = (
            query.order_by(ProcedureOrder.ordered_at.asc()).offset(skip).limit(limit).all()
        )
        return items, int(total)

    def create(self, **kwargs) -> ProcedureOrder:
        kwargs.setdefault("ordered_at", datetime.now(timezone.utc))
        kwargs.setdefault("status", OrderStatus.ORDERED)
        o = ProcedureOrder(**kwargs)
        self.db.add(o)
        self.db.flush()
        self.db.refresh(o)
        return o

    def save(self, o: ProcedureOrder) -> ProcedureOrder:
        self.db.add(o)
        self.db.flush()
        self.db.refresh(o)
        return o
