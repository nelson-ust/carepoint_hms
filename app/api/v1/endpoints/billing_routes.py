# app/api/v1/endpoints/billing_routes.py
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.billing_schemas import (
    BillableServiceActionResponseSchema,
    BillableServiceCreateSchema,
    BillableServiceListResponseSchema,
    BillableServiceReadSchema,
    BillableServiceUpdateSchema,
    BillingActionResponseSchema,
    BillingCreateSchema,
    BillingItemCreateSchema,
    BillingListResponseSchema,
    BillingReadSchema,
)
from app.services.billing_service import BillableServiceService, BillingService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/billing", 
    tags=["Billing"],
    dependencies=[Depends(require_plan_feature("billing"))]
)


def get_billable_service_service(db: Annotated[Session, Depends(get_db)]) -> BillableServiceService:
    return BillableServiceService(db)


def get_billing_service(db: Annotated[Session, Depends(get_db)]) -> BillingService:
    return BillingService(db)


def _serialize_service(s) -> dict:
    return {
        "id": s.id,
        "code": s.code,
        "name": s.name,
        "category": s.category,
        "default_price": s.default_price,
        "description": s.description,
        "created_at": getattr(s, "date_created", None),
        "updated_at": getattr(s, "date_updated", None),
    }


def _serialize_billing_item(i) -> dict:
    return {
        "id": i.id,
        "billing_id": i.billing_id,
        "billable_service_id": i.billable_service_id,
        "service_name": i.service_name,
        "service_code": i.service_code,
        "quantity": i.quantity,
        "unit_price": i.unit_price,
        "discount_amount": i.discount_amount,
        "line_total": i.line_total,
        "source_reference": i.source_reference,
        "created_at": getattr(i, "date_created", None),
    }


def _serialize_billing(b) -> dict:
    return {
        "id": b.id,
        "patient_id": b.patient_id,
        "visit_id": b.visit_id,
        "patient_insurance_id": b.patient_insurance_id,
        "billing_no": b.billing_no,
        "billing_date": b.billing_date,
        "status": b.status,
        "gross_amount": b.gross_amount,
        "discount_amount": b.discount_amount,
        "net_amount": b.net_amount,
        "notes": b.notes,
        "items": [_serialize_billing_item(i) for i in (b.items or []) if not getattr(i, "is_deleted", False)],
        "created_at": getattr(b, "date_created", None),
        "updated_at": getattr(b, "date_updated", None),
    }


# --- BILLABLE SERVICES ---

@router.get(
    "/services",
    response_model=BillableServiceListResponseSchema,
    summary="List billable services",
)
def list_services(
    _: Annotated[User, Depends(require_permission("BILLING_READ", "BILLING_CREATE"))],
    service: Annotated[BillableServiceService, Depends(get_billable_service_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    items, total = service.list(skip=skip, limit=limit, search=search, category=category)
    return paginate_response(
        items=[_serialize_service(s) for s in items],
        total=total, skip=skip, limit=limit,
        message="Billable services fetched successfully.",
    )


@router.post(
    "/services",
    response_model=BillableServiceActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a billable service",
)
def create_billable_service(
    payload: BillableServiceCreateSchema,
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[BillableServiceService, Depends(get_billable_service_service)],
):
    s = service.create(payload)
    return {"success": True, "message": "Billable service created.", "service": _serialize_service(s)}


@router.put(
    "/services/{sid}",
    response_model=BillableServiceActionResponseSchema,
    summary="Update a billable service",
)
def update_billable_service(
    sid: int,
    payload: BillableServiceUpdateSchema,
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[BillableServiceService, Depends(get_billable_service_service)],
):
    s = service.update(sid, payload)
    return {"success": True, "message": "Billable service updated.", "service": _serialize_service(s)}


@router.delete(
    "/services/{sid}",
    summary="Soft-delete a billable service",
)
def delete_billable_service(
    sid: int,
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[BillableServiceService, Depends(get_billable_service_service)],
):
    s = service.soft_delete(sid)
    return {"success": True, "message": "Billable service deactivated.", "service_id": s.id}


# --- BILLINGS ---

@router.get(
    "/",
    response_model=BillingListResponseSchema,
    summary="List billings",
)
def list_billings(
    _: Annotated[User, Depends(require_permission("BILLING_READ"))],
    service: Annotated[BillingService, Depends(get_billing_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    patient_id: Optional[int] = Query(None),
    visit_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    items, total = service.list_billings(
        skip=skip, limit=limit, patient_id=patient_id, visit_id=visit_id, status=status_filter,
    )
    return paginate_response(
        items=[_serialize_billing(b) for b in items],
        total=total, skip=skip, limit=limit,
        message="Billings fetched successfully.",
    )


@router.get(
    "/visits/{visit_id}",
    response_model=BillingListResponseSchema,
    summary="List billings for a visit",
)
def list_for_visit(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("BILLING_READ"))],
    service: Annotated[BillingService, Depends(get_billing_service)],
):
    items = service.list_for_visit(visit_id)
    return paginate_response(
        items=[_serialize_billing(b) for b in items],
        total=len(items), skip=0, limit=len(items) or 1,
        message="Billings fetched successfully.",
    )


@router.post(
    "/",
    response_model=BillingActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a billing",
)
def create_billing(
    payload: BillingCreateSchema,
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[BillingService, Depends(get_billing_service)],
):
    b = service.create_billing(payload)
    return {"success": True, "message": "Billing created.", "billing": _serialize_billing(b)}


@router.get(
    "/{billing_id}",
    response_model=BillingReadSchema,
    summary="Get a billing",
)
def get_billing(
    billing_id: int,
    _: Annotated[User, Depends(require_permission("BILLING_READ"))],
    service: Annotated[BillingService, Depends(get_billing_service)],
):
    return _serialize_billing(service.get(billing_id))


@router.post(
    "/{billing_id}/items",
    response_model=BillingActionResponseSchema,
    summary="Add a charge line to a billing",
)
def add_item(
    billing_id: int,
    payload: BillingItemCreateSchema,
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[BillingService, Depends(get_billing_service)],
):
    b = service.add_item(billing_id, payload)
    return {"success": True, "message": "Item added to billing.", "billing": _serialize_billing(b)}


@router.post(
    "/{billing_id}/cancel",
    response_model=BillingActionResponseSchema,
    summary="Cancel a billing",
)
def cancel_billing(
    billing_id: int,
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[BillingService, Depends(get_billing_service)],
    reason: Optional[str] = Query(None, max_length=500),
):
    b = service.cancel_billing(billing_id, reason=reason)
    return {"success": True, "message": "Billing cancelled.", "billing": _serialize_billing(b)}
