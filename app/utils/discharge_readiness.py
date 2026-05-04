# app/utils/discharge_readiness.py
from __future__ import annotations

"""
Discharge / visit-close readiness checks.

A visit shouldn't be closed (and an admission shouldn't be discharged) while
clinical orders are still mid-flight or pharmacy items haven't been dispensed.
This module collects the checks in one place so:

- the discharge service can refuse a premature discharge,
- the visit-close path can fail loudly with an actionable error payload,
- a future "ready to discharge?" UI button can call the same logic.

Each check returns a structured dict so the caller can render exactly which
gates are still failing. ``check_visit_ready_to_close`` aggregates them into
a single (is_ready, blockers) tuple.
"""

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    OrderStatus,
    PrescriptionStatus,
    RadiologyOrderStatus,
    SurgicalCaseStatus,
)
from app.models.all_models import (
    LabOrder,
    Prescription,
    RadiologyOrder,
    SurgicalCase,
)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def open_lab_orders(db: Session, *, visit_id: int) -> list[dict[str, Any]]:
    """Return open lab orders for a visit."""
    rows = (
        db.query(LabOrder)
        .filter(
            LabOrder.visit_id == visit_id,
            LabOrder.is_deleted.is_(False),
            LabOrder.status.notin_(
                [OrderStatus.COMPLETED, OrderStatus.CANCELLED]
            ),
        )
        .all()
    )
    return [
        {"order_id": o.id, "order_no": o.order_no, "status": str(o.status)}
        for o in rows
    ]


def open_radiology_orders(db: Session, *, visit_id: int) -> list[dict[str, Any]]:
    """Return open radiology orders for a visit."""
    rows = (
        db.query(RadiologyOrder)
        .filter(
            RadiologyOrder.visit_id == visit_id,
            RadiologyOrder.is_deleted.is_(False),
            RadiologyOrder.status.notin_(
                [RadiologyOrderStatus.COMPLETED, RadiologyOrderStatus.CANCELLED]
            ),
        )
        .all()
    )
    return [
        {"order_id": o.id, "order_no": o.order_no, "status": str(o.status)}
        for o in rows
    ]


def undispensed_prescriptions(db: Session, *, visit_id: int) -> list[dict[str, Any]]:
    """Return prescriptions that aren't fully dispensed or cancelled."""
    rows = (
        db.query(Prescription)
        .filter(
            Prescription.visit_id == visit_id,
            Prescription.is_deleted.is_(False),
            Prescription.status.notin_(
                [PrescriptionStatus.DISPENSED, PrescriptionStatus.CANCELLED]
            ),
        )
        .all()
    )
    return [
        {
            "prescription_id": p.id,
            "prescription_no": p.prescription_no,
            "status": str(p.status),
        }
        for p in rows
    ]


def open_surgical_cases(db: Session, *, visit_id: int) -> list[dict[str, Any]]:
    """Return surgical cases that haven't reached a terminal state."""
    rows = (
        db.query(SurgicalCase)
        .filter(
            SurgicalCase.visit_id == visit_id,
            SurgicalCase.is_deleted.is_(False),
            SurgicalCase.status.notin_(
                [SurgicalCaseStatus.COMPLETED, SurgicalCaseStatus.CANCELLED]
            ),
        )
        .all()
    )
    return [
        {
            "case_id": c.id,
            "case_no": c.case_no,
            "status": str(c.status),
        }
        for c in rows
    ]


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


def check_visit_ready_to_close(
    db: Session,
    *,
    visit_id: int,
    require_no_open_lab: bool = True,
    require_no_open_radiology: bool = True,
    require_no_open_prescription: bool = True,
    require_no_open_surgery: bool = True,
) -> tuple[bool, dict[str, Any]]:
    """
    Aggregate readiness check.

    Returns ``(is_ready, blockers)``. ``blockers`` is a structured dict the
    caller can pass straight into a ``BadRequestError.detail`` payload.
    """
    blockers: dict[str, Any] = {}
    if require_no_open_lab:
        rows = open_lab_orders(db, visit_id=visit_id)
        if rows:
            blockers["open_lab_orders"] = rows
    if require_no_open_radiology:
        rows = open_radiology_orders(db, visit_id=visit_id)
        if rows:
            blockers["open_radiology_orders"] = rows
    if require_no_open_prescription:
        rows = undispensed_prescriptions(db, visit_id=visit_id)
        if rows:
            blockers["undispensed_prescriptions"] = rows
    if require_no_open_surgery:
        rows = open_surgical_cases(db, visit_id=visit_id)
        if rows:
            blockers["open_surgical_cases"] = rows
    return (len(blockers) == 0), blockers


def check_admission_ready_to_discharge(
    db: Session,
    *,
    visit_id: Optional[int],
    require_no_open_lab: bool = True,
    require_no_open_radiology: bool = True,
    require_no_open_prescription: bool = True,
    require_no_open_surgery: bool = True,
) -> tuple[bool, dict[str, Any]]:
    """
    Discharge-readiness wrapper. Mirrors :func:`check_visit_ready_to_close`
    but tolerates ``visit_id == None`` (some inpatient stays don't bind to a
    visit row); in that case the admission is always ready as far as the
    clinical-order gates are concerned.
    """
    if visit_id is None:
        return True, {}
    return check_visit_ready_to_close(
        db,
        visit_id=visit_id,
        require_no_open_lab=require_no_open_lab,
        require_no_open_radiology=require_no_open_radiology,
        require_no_open_prescription=require_no_open_prescription,
        require_no_open_surgery=require_no_open_surgery,
    )
