# app/api/v1/endpoints/invoice_routes.py
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.invoice_schema import (
    InvoiceActionResponseSchema,
    InvoiceIssueFromBillingSchema,
    InvoiceListResponseSchema,
    InvoiceReadSchema,
    InvoiceVoidSchema,
)
from app.services.invoice_service import InvoiceService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/invoices", 
    tags=["Invoices"],
    dependencies=[Depends(require_plan_feature("billing"))]
)


def get_invoice_service(db: Annotated[Session, Depends(get_db)]) -> InvoiceService:
    return InvoiceService(db)


@router.get(
    "/",
    response_model=InvoiceListResponseSchema,
    summary="List invoices",
)
def list_invoices(
    _: Annotated[User, Depends(require_permission("BILLING_READ", "INVOICE_ISSUE"))],
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    patient_id: Optional[int] = Query(None),
    visit_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    items, total = service.list_invoices(
        skip=skip, limit=limit, patient_id=patient_id, visit_id=visit_id, status=status_filter,
    )
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Invoices fetched successfully.",
    )


@router.get(
    "/visits/{visit_id}",
    response_model=InvoiceListResponseSchema,
    summary="List invoices for a visit",
)
def list_for_visit(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("BILLING_READ"))],
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
):
    items = service.list_for_visit(visit_id)
    return paginate_response(
        items=items,
        total=len(items),
        skip=0,
        limit=len(items) or 1,
        message="Invoices fetched successfully.",
    )


@router.post(
    "/issue-from-billing",
    response_model=InvoiceActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Issue an invoice from a billing record",
)
def issue_from_billing(
    payload: InvoiceIssueFromBillingSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("INVOICE_ISSUE"))],
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
):
    invoice = service.issue_from_billing(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Invoice issued.", "invoice": invoice}


@router.get(
    "/{invoice_id}",
    response_model=InvoiceReadSchema,
    summary="Get an invoice",
)
def get_invoice(
    invoice_id: int,
    _: Annotated[User, Depends(require_permission("BILLING_READ"))],
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
):
    return service.get(invoice_id)


@router.post(
    "/{invoice_id}/void",
    response_model=InvoiceActionResponseSchema,
    summary="Void an invoice",
)
def void_invoice(
    invoice_id: int,
    payload: InvoiceVoidSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("INVOICE_VOID"))],
    service: Annotated[InvoiceService, Depends(get_invoice_service)],
):
    invoice = service.void_invoice(invoice_id, reason=payload.reason, actor_user_id=actor.id)
    return {"success": True, "message": "Invoice voided.", "invoice": invoice}
