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

from app.schemas.pharmacy_schema import (
    PharmacyWorklistResponseSchema,
    PharmacyStockAlertsResponseSchema,
)

router = APIRouter(
    prefix="/pharmacy",
    tags=["Pharmacy Workstation"],
    dependencies=[Depends(require_plan_feature("pharmacy"))]
)


def get_pharmacy_service(db: Annotated[Session, Depends(get_db)]) -> PharmacyService:
    return PharmacyService(db)


@router.get(
    "/worklist",
    response_model=PharmacyWorklistResponseSchema,
    summary="Pharmacy worklist (open prescriptions)",
)
def get_worklist(
    _: Annotated[User, Depends(require_permission("PRESCRIPTION_DISPENSE"))],
    service: Annotated[PharmacyService, Depends(get_pharmacy_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
):
    items, total = service.worklist(skip=skip, limit=limit)
    return {
        "success": True,
        "message": "Pharmacy worklist fetched successfully.",
        "items": items,
        "count": len(items),
        "meta": {"total": total, "skip": skip, "limit": limit},
    }


@router.get(
    "/stock-alerts",
    response_model=PharmacyStockAlertsResponseSchema,
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
        "low_stock": data["low_stock"],
        "expiring_soon": data["expiring_soon"],
    }
