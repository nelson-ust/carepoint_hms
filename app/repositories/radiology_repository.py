# app/repositories/radiology_repository.py
from __future__ import annotations

"""
Repository layer for the Radiology / RIS module.

Five repositories cover the entity tree:
- ``RadiologyCatalogRepository``     — RadiologyProcedureCatalog
- ``RadiologyOrderRepository``       — order header + items
- ``RadiologyExamRepository``        — execution rows
- ``RadiologyImageRepository``       — DICOM/PACS metadata
- ``RadiologyReportRepository``      — radiologist reading
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.core.enums import (
    RadiologyExamStatus,
    RadiologyOrderStatus,
    RadiologyReportStatus,
)
from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.all_models import (
    RadiologyExam,
    RadiologyImage,
    RadiologyOrder,
    RadiologyOrderItem,
    RadiologyProcedureCatalog,
    RadiologyReport,
    Visit,
)
from app.utils.helpers import generate_uuid_str


# ============================================================
# CATALOG
# ============================================================


class RadiologyCatalogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, procedure_id: int) -> Optional[RadiologyProcedureCatalog]:
        return (
            self.db.query(RadiologyProcedureCatalog)
            .filter(
                RadiologyProcedureCatalog.id == procedure_id,
                RadiologyProcedureCatalog.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, procedure_id: int) -> RadiologyProcedureCatalog:
        p = self.get_by_id(procedure_id)
        if not p:
            raise NotFoundError(message="Radiology procedure not found.", detail={"procedure_id": procedure_id})
        return p

    def get_by_code(self, code: str) -> Optional[RadiologyProcedureCatalog]:
        return (
            self.db.query(RadiologyProcedureCatalog)
            .filter(
                func.upper(RadiologyProcedureCatalog.code) == code.strip().upper(),
                RadiologyProcedureCatalog.is_deleted.is_(False),
            )
            .first()
        )

    def list_procedures(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        modality: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[RadiologyProcedureCatalog], int]:
        query = self.db.query(RadiologyProcedureCatalog).filter(
            RadiologyProcedureCatalog.is_deleted.is_(False)
        )
        if modality:
            query = query.filter(
                func.upper(RadiologyProcedureCatalog.modality) == modality.strip().upper()
            )
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(RadiologyProcedureCatalog.name).like(term),
                    func.lower(RadiologyProcedureCatalog.code).like(term),
                )
            )
        total = query.with_entities(func.count(RadiologyProcedureCatalog.id)).scalar() or 0
        items = (
            query.order_by(RadiologyProcedureCatalog.name.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def create(self, **kwargs) -> RadiologyProcedureCatalog:
        if self.get_by_code(kwargs["code"]):
            raise AlreadyExistsError(
                message="A radiology procedure with this code already exists.",
                detail={"code": kwargs["code"]},
            )
        p = RadiologyProcedureCatalog(**kwargs)
        self.db.add(p)
        self.db.flush()
        self.db.refresh(p)
        return p

    def update(self, p: RadiologyProcedureCatalog, **kwargs) -> RadiologyProcedureCatalog:
        for field, value in kwargs.items():
            if value is not None:
                setattr(p, field, value)
        self.db.add(p)
        self.db.flush()
        self.db.refresh(p)
        return p

    def soft_delete(self, p: RadiologyProcedureCatalog) -> RadiologyProcedureCatalog:
        p.is_deleted = True
        self.db.add(p)
        self.db.flush()
        return p


# ============================================================
# ORDER
# ============================================================


class RadiologyOrderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_visit(self, visit_id: int) -> Optional[Visit]:
        return (
            self.db.query(Visit)
            .filter(Visit.id == visit_id, Visit.is_deleted.is_(False))
            .first()
        )

    def get_by_id(self, order_id: int) -> Optional[RadiologyOrder]:
        return (
            self.db.query(RadiologyOrder)
            .options(selectinload(RadiologyOrder.items))
            .filter(RadiologyOrder.id == order_id, RadiologyOrder.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, order_id: int) -> RadiologyOrder:
        o = self.get_by_id(order_id)
        if not o:
            raise NotFoundError(message="Radiology order not found.", detail={"order_id": order_id})
        return o

    def get_item_by_id(self, item_id: int) -> Optional[RadiologyOrderItem]:
        return (
            self.db.query(RadiologyOrderItem)
            .filter(
                RadiologyOrderItem.id == item_id,
                RadiologyOrderItem.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_item_by_id(self, item_id: int) -> RadiologyOrderItem:
        i = self.get_item_by_id(item_id)
        if not i:
            raise NotFoundError(message="Radiology order item not found.", detail={"item_id": item_id})
        return i

    def list_for_visit(
        self, visit_id: int, *, skip: int = 0, limit: int = 50
    ) -> tuple[list[RadiologyOrder], int]:
        query = (
            self.db.query(RadiologyOrder)
            .options(selectinload(RadiologyOrder.items))
            .filter(
                RadiologyOrder.visit_id == visit_id,
                RadiologyOrder.is_deleted.is_(False),
            )
        )
        total = query.with_entities(func.count(RadiologyOrder.id)).scalar() or 0
        items = query.order_by(RadiologyOrder.id.desc()).offset(skip).limit(limit).all()
        return items, int(total)

    def list_worklist(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        statuses: Optional[list[RadiologyOrderStatus]] = None,
    ) -> tuple[list[RadiologyOrder], int]:
        query = (
            self.db.query(RadiologyOrder)
            .options(selectinload(RadiologyOrder.items))
            .filter(RadiologyOrder.is_deleted.is_(False))
        )
        if statuses:
            query = query.filter(RadiologyOrder.status.in_(statuses))
        else:
            query = query.filter(
                RadiologyOrder.status.notin_(
                    [RadiologyOrderStatus.COMPLETED, RadiologyOrderStatus.CANCELLED]
                )
            )
        total = query.with_entities(func.count(RadiologyOrder.id)).scalar() or 0
        items = (
            query.order_by(RadiologyOrder.ordered_at.asc()).offset(skip).limit(limit).all()
        )
        return items, int(total)

    def generate_order_no(self) -> str:
        return f"RAD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create_order(self, **kwargs) -> RadiologyOrder:
        kwargs.setdefault("order_no", self.generate_order_no())
        kwargs.setdefault("ordered_at", datetime.now(timezone.utc))
        kwargs.setdefault("status", RadiologyOrderStatus.ORDERED)
        o = RadiologyOrder(**kwargs)
        self.db.add(o)
        self.db.flush()
        self.db.refresh(o)
        return o

    def add_item(self, **kwargs) -> RadiologyOrderItem:
        kwargs.setdefault("status", RadiologyOrderStatus.ORDERED)
        item = RadiologyOrderItem(**kwargs)
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def items_for_order(self, order_id: int) -> list[RadiologyOrderItem]:
        return (
            self.db.query(RadiologyOrderItem)
            .filter(
                RadiologyOrderItem.radiology_order_id == order_id,
                RadiologyOrderItem.is_deleted.is_(False),
            )
            .all()
        )

    def save(self, o: RadiologyOrder) -> RadiologyOrder:
        self.db.add(o)
        self.db.flush()
        self.db.refresh(o)
        return o

    def save_item(self, i: RadiologyOrderItem) -> RadiologyOrderItem:
        self.db.add(i)
        self.db.flush()
        self.db.refresh(i)
        return i

    def recompute_order_status(self, order: RadiologyOrder) -> RadiologyOrder:
        """Roll order status forward to the most-advanced common item state."""
        items = self.items_for_order(order.id)
        if not items:
            return order
        statuses = {i.status for i in items}
        if all(s == RadiologyOrderStatus.CANCELLED for s in statuses):
            order.status = RadiologyOrderStatus.CANCELLED
        elif all(
            s in {RadiologyOrderStatus.COMPLETED, RadiologyOrderStatus.CANCELLED}
            for s in statuses
        ):
            order.status = RadiologyOrderStatus.COMPLETED
        elif any(s == RadiologyOrderStatus.RELEASED for s in statuses):
            order.status = RadiologyOrderStatus.RELEASED
        elif any(s == RadiologyOrderStatus.REPORTED for s in statuses):
            order.status = RadiologyOrderStatus.REPORTED
        elif any(s == RadiologyOrderStatus.PERFORMED for s in statuses):
            order.status = RadiologyOrderStatus.PERFORMED
        elif any(s == RadiologyOrderStatus.IN_PROGRESS for s in statuses):
            order.status = RadiologyOrderStatus.IN_PROGRESS
        elif any(s == RadiologyOrderStatus.SCHEDULED for s in statuses):
            order.status = RadiologyOrderStatus.SCHEDULED
        else:
            order.status = RadiologyOrderStatus.ORDERED
        self.db.add(order)
        self.db.flush()
        self.db.refresh(order)
        return order


# ============================================================
# EXAM
# ============================================================


class RadiologyExamRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, exam_id: int) -> Optional[RadiologyExam]:
        return (
            self.db.query(RadiologyExam)
            .filter(RadiologyExam.id == exam_id, RadiologyExam.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, exam_id: int) -> RadiologyExam:
        e = self.get_by_id(exam_id)
        if not e:
            raise NotFoundError(message="Radiology exam not found.", detail={"exam_id": exam_id})
        return e

    def get_for_order_item(self, order_item_id: int) -> Optional[RadiologyExam]:
        return (
            self.db.query(RadiologyExam)
            .filter(
                RadiologyExam.order_item_id == order_item_id,
                RadiologyExam.is_deleted.is_(False),
            )
            .first()
        )

    def generate_accession_number(self) -> str:
        return f"ACC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create(self, **kwargs) -> RadiologyExam:
        kwargs.setdefault("accession_number", self.generate_accession_number())
        kwargs.setdefault("status", RadiologyExamStatus.SCHEDULED)
        e = RadiologyExam(**kwargs)
        self.db.add(e)
        self.db.flush()
        self.db.refresh(e)
        return e

    def save(self, e: RadiologyExam) -> RadiologyExam:
        self.db.add(e)
        self.db.flush()
        self.db.refresh(e)
        return e


# ============================================================
# IMAGE
# ============================================================


class RadiologyImageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_required_by_id(self, image_id: int) -> RadiologyImage:
        i = (
            self.db.query(RadiologyImage)
            .filter(RadiologyImage.id == image_id, RadiologyImage.is_deleted.is_(False))
            .first()
        )
        if not i:
            raise NotFoundError(message="Radiology image not found.", detail={"image_id": image_id})
        return i

    def list_for_exam(self, exam_id: int) -> list[RadiologyImage]:
        return (
            self.db.query(RadiologyImage)
            .filter(RadiologyImage.exam_id == exam_id, RadiologyImage.is_deleted.is_(False))
            .order_by(RadiologyImage.id.asc())
            .all()
        )

    def create(self, **kwargs) -> RadiologyImage:
        i = RadiologyImage(**kwargs)
        self.db.add(i)
        self.db.flush()
        self.db.refresh(i)
        return i


# ============================================================
# REPORT
# ============================================================


class RadiologyReportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, report_id: int) -> Optional[RadiologyReport]:
        return (
            self.db.query(RadiologyReport)
            .filter(RadiologyReport.id == report_id, RadiologyReport.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, report_id: int) -> RadiologyReport:
        r = self.get_by_id(report_id)
        if not r:
            raise NotFoundError(message="Radiology report not found.", detail={"report_id": report_id})
        return r

    def get_for_exam(self, exam_id: int) -> Optional[RadiologyReport]:
        return (
            self.db.query(RadiologyReport)
            .filter(RadiologyReport.exam_id == exam_id, RadiologyReport.is_deleted.is_(False))
            .first()
        )

    def create(self, **kwargs) -> RadiologyReport:
        kwargs.setdefault("status", RadiologyReportStatus.DRAFT)
        kwargs.setdefault("drafted_at", datetime.now(timezone.utc))
        r = RadiologyReport(**kwargs)
        self.db.add(r)
        self.db.flush()
        self.db.refresh(r)
        return r

    def save(self, r: RadiologyReport) -> RadiologyReport:
        self.db.add(r)
        self.db.flush()
        self.db.refresh(r)
        return r
