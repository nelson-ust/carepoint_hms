# app/api/v1/endpoints/pharmacy_routes.py
from __future__ import annotations

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.services.pharmacy_service import PharmacyService
from app.services.pharmacy_sales_service import PharmacySalesService

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


def get_sales_service(db: Annotated[Session, Depends(get_db)]) -> PharmacySalesService:
    return PharmacySalesService(db)


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


# ---------------------------------------------------------------------------
# Retail / OTC point-of-sale (standalone pharmaceutical store)
# ---------------------------------------------------------------------------

_SELL_PERM = require_permission("PHARMACY_SELL", "PRESCRIPTION_DISPENSE", "PHARMACY_STOCK_MANAGE")


class SaleItemIn(BaseModel):
    stock_item_id: int
    quantity: float = Field(..., gt=0)
    unit_price: Optional[float] = None


class SaleCreateSchema(BaseModel):
    store_id: int
    items: list[SaleItemIn] = Field(..., min_length=1)
    patient_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    sold_by_staff_id: Optional[int] = None
    payment_method: str = "CASH"
    discount_amount: float = 0
    tax_amount: float = 0
    amount_paid: Optional[float] = None
    on_account: bool = False
    note: Optional[str] = None


class SaleVoidSchema(BaseModel):
    reason: Optional[str] = None
    staff_id: Optional[int] = None


def _serialize_sale(sale) -> dict:
    return {
        "id": sale.id,
        "sale_no": sale.sale_no,
        "store_id": sale.store_id,
        "patient_id": sale.patient_id,
        "customer_name": sale.customer_name,
        "customer_phone": sale.customer_phone,
        "sold_by_staff_id": sale.sold_by_staff_id,
        "status": sale.status,
        "subtotal": float(sale.subtotal or 0),
        "discount_amount": float(sale.discount_amount or 0),
        "tax_amount": float(sale.tax_amount or 0),
        "total_amount": float(sale.total_amount or 0),
        "amount_paid": float(sale.amount_paid or 0),
        "outstanding": float(round((sale.total_amount or 0) - (sale.amount_paid or 0), 2)),
        "change_due": float(sale.change_due or 0),
        "payment_method": sale.payment_method,
        "note": sale.note,
        "sold_at": sale.sold_at.isoformat() if sale.sold_at else None,
        "voided_at": sale.voided_at.isoformat() if sale.voided_at else None,
        "void_reason": sale.void_reason,
        "items": [
            {
                "id": it.id,
                "stock_item_id": it.stock_item_id,
                "item_name": it.item_name,
                "quantity": float(it.quantity or 0),
                "unit_price": float(it.unit_price or 0),
                "line_total": float(it.line_total or 0),
            }
            for it in (sale.items or [])
        ],
    }


@router.post("/sales", summary="Record a retail / OTC sale")
def create_sale(
    payload: SaleCreateSchema,
    _: Annotated[User, Depends(_SELL_PERM)],
    service: Annotated[PharmacySalesService, Depends(get_sales_service)],
):
    sale = service.create_sale(payload.model_dump())
    return {"success": True, "message": f"Sale {sale.sale_no} completed.", "sale": _serialize_sale(sale)}


@router.get("/store/dashboard", summary="Pharmacy store dashboard")
def store_dashboard(
    service: Annotated[PharmacySalesService, Depends(get_sales_service)],
    store_id: Optional[int] = Query(None),
):
    return {"success": True, **service.store_dashboard(store_id=store_id)}


@router.get("/sales/summary", summary="Today's retail sales summary")
def sales_summary(
    _: Annotated[User, Depends(_SELL_PERM)],
    service: Annotated[PharmacySalesService, Depends(get_sales_service)],
    store_id: Optional[int] = Query(None),
):
    return {"success": True, **service.summary(store_id=store_id)}


@router.get("/sales", summary="List retail sales")
def list_sales(
    _: Annotated[User, Depends(_SELL_PERM)],
    service: Annotated[PharmacySalesService, Depends(get_sales_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    store_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    rows, total = service.list_sales(
        skip=skip, limit=limit, store_id=store_id, status=status, date_from=date_from, date_to=date_to,
    )
    return {
        "success": True,
        "items": [_serialize_sale(s) for s in rows],
        "count": len(rows),
        "meta": {"total": total, "skip": skip, "limit": limit},
    }


@router.get("/sales/{sale_id}", summary="Get a retail sale (receipt)")
def get_sale(
    sale_id: int,
    _: Annotated[User, Depends(_SELL_PERM)],
    service: Annotated[PharmacySalesService, Depends(get_sales_service)],
):
    return {"success": True, "sale": _serialize_sale(service.get_sale(sale_id))}


@router.post("/sales/{sale_id}/void", summary="Void a sale (returns stock)")
def void_sale(
    sale_id: int,
    payload: SaleVoidSchema,
    _: Annotated[User, Depends(_SELL_PERM)],
    service: Annotated[PharmacySalesService, Depends(get_sales_service)],
):
    sale = service.void_sale(sale_id, reason=payload.reason, staff_id=payload.staff_id)
    return {"success": True, "message": f"Sale {sale.sale_no} voided.", "sale": _serialize_sale(sale)}


class SaleSettleSchema(BaseModel):
    amount: float
    payment_method: str = "CASH"
    staff_id: Optional[int] = None


@router.post("/sales/{sale_id}/settle", summary="Record a customer payment on a credit sale")
def settle_sale(
    sale_id: int,
    payload: SaleSettleSchema,
    _: Annotated[User, Depends(_SELL_PERM)],
    service: Annotated[PharmacySalesService, Depends(get_sales_service)],
):
    sale = service.settle_sale(
        sale_id, amount=payload.amount, payment_method=payload.payment_method, staff_id=payload.staff_id
    )
    return {"success": True, "message": f"Payment recorded for {sale.sale_no}.", "sale": _serialize_sale(sale)}


@router.get("/credit/outstanding", summary="Credit sales with an outstanding balance")
def outstanding_credit(
    _: Annotated[User, Depends(_SELL_PERM)],
    service: Annotated[PharmacySalesService, Depends(get_sales_service)],
    store_id: Optional[int] = Query(None),
):
    return {"success": True, "items": service.list_outstanding(store_id=store_id)}
