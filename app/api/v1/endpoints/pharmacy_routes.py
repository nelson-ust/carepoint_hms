# app/api/v1/endpoints/pharmacy_routes.py
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.services.pharmacy_service import PharmacyService

router = APIRouter(
    prefix="/pharmacy",
    tags=["Pharmacy Workstation"],
    dependencies=[Depends(require_plan_feature("pharmacy"))]
)


def get_pharmacy_service(db: Annotated[Session, Depends(get_db)]) -> PharmacyService:
    return PharmacyService(db)


def _serialize_prescription(p) -> dict:
    return {
        "id": p.id,
        "visit_id": p.visit_id,
        "consultation_id": p.consultation_id,
        "prescribed_by_staff_id": p.prescribed_by_staff_id,
        "prescription_no": p.prescription_no,
        "status": str(p.status),
        "note": p.note,
        "prescribed_at": p.prescribed_at,
        "items": [
            {
                "id": i.id,
                "drug_id": i.drug_id,
                "dosage": i.dosage,
                "frequency": i.frequency,
                "duration": i.duration,
                "route": i.route,
                "quantity_prescribed": i.quantity_prescribed,
                "quantity_dispensed": i.quantity_dispensed,
                "instructions": i.instructions,
            }
            for i in (p.items or [])
            if not getattr(i, "is_deleted", False)
        ],
    }


def _serialize_stock(i) -> dict:
    return {
        "id": i.id,
        "store_id": i.store_id,
        "drug_id": i.drug_id,
        "item_name": i.item_name,
        "sku": i.sku,
        "quantity_on_hand": i.quantity_on_hand,
        "reorder_level": i.reorder_level,
        "expiry_date": i.expiry_date,
        "batch_no": i.batch_no,
    }


@router.get(
    "/worklist",
    summary="Pharmacy worklist (open prescriptions)",
)
def get_worklist(
    _: Annotated[User, Depends(require_permission("PRESCRIPTION_DISPENSE"))],
    service: Annotated[PharmacyService, Depends(get_pharmacy_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    items, total = service.worklist(skip=skip, limit=limit)
    return {
        "success": True,
        "message": "Pharmacy worklist fetched successfully.",
        "items": [_serialize_prescription(p) for p in items],
        "count": len(items),
        "meta": {"total": total, "skip": skip, "limit": limit},
    }


@router.get(
    "/stock-alerts",
    summary="Pharmacy stock alerts (low stock + expiring soon)",
)
def get_stock_alerts(
    _: Annotated[User, Depends(require_permission("PHARMACY_STOCK_MANAGE", "INVENTORY_READ"))],
    service: Annotated[PharmacyService, Depends(get_pharmacy_service)],
    store_id: Optional[int] = Query(None),
    expiring_within_days: int = Query(30, ge=0, le=365),
):
    data = service.stock_alerts(store_id=store_id, expiring_within_days=expiring_within_days)
    return {
        "success": True,
        "message": "Pharmacy stock alerts fetched successfully.",
        "low_stock": [_serialize_stock(i) for i in data["low_stock"]],
        "expiring_soon": [_serialize_stock(i) for i in data["expiring_soon"]],
    }
