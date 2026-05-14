# app/api/v1/endpoints/payment_routes.py
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.payment_schema import (
    PaymentActionResponseSchema,
    PaymentListResponseSchema,
    PaymentReadSchema,
    PaymentReceiveSchema,
    PaymentRefundSchema,
)
from app.services.payment_service import PaymentService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/payments", 
    tags=["Payments"],
    dependencies=[Depends(require_plan_feature("billing"))]
)


def get_payment_service(db: Annotated[Session, Depends(get_db)]) -> PaymentService:
    return PaymentService(db)


# ============================================================
# READ
# ============================================================


@router.get(
    "/",
    response_model=PaymentListResponseSchema,
    summary="List payments",
)
def list_payments(
    _: Annotated[User, Depends(require_permission("BILLING_READ", "PAYMENT_RECEIVE"))],
    service: Annotated[PaymentService, Depends(get_payment_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    invoice_id: Optional[int] = Query(None),
    payment_method: Optional[str] = Query(None),
    payment_status: Optional[str] = Query(None),
):
    items, total = service.list_payments(
        skip=skip, limit=limit, invoice_id=invoice_id,
        payment_method=payment_method, payment_status=payment_status,
    )
    return paginate_response(
        items=items,
        total=total, skip=skip, limit=limit,
        message="Payments fetched successfully.",
    )


@router.get(
    "/invoices/{invoice_id}",
    response_model=PaymentListResponseSchema,
    summary="List payments for an invoice",
)
def list_for_invoice(
    invoice_id: int,
    _: Annotated[User, Depends(require_permission("BILLING_READ", "PAYMENT_RECEIVE"))],
    service: Annotated[PaymentService, Depends(get_payment_service)],
):
    items = service.list_for_invoice(invoice_id)
    return paginate_response(
        items=items,
        total=len(items), skip=0, limit=len(items) or 1,
        message="Payments fetched successfully.",
    )


@router.post(
    "/",
    response_model=PaymentActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Receive a payment against an invoice",
)
def receive_payment(
    payload: PaymentReceiveSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("PAYMENT_RECEIVE"))],
    service: Annotated[PaymentService, Depends(get_payment_service)],
):
    p = service.receive_payment(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Payment received.", "payment": p}


@router.post(
    "/refund",
    response_model=PaymentActionResponseSchema,
    summary="Refund a previous payment",
)
def refund_payment(
    payload: PaymentRefundSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("PAYMENT_REFUND"))],
    service: Annotated[PaymentService, Depends(get_payment_service)],
):
    p = service.refund_payment(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Payment refunded.", "payment": p}


@router.get(
    "/{payment_id}",
    response_model=PaymentReadSchema,
    summary="Get a payment",
)
def get_payment(
    payment_id: int,
    _: Annotated[User, Depends(require_permission("BILLING_READ", "PAYMENT_RECEIVE"))],
    service: Annotated[PaymentService, Depends(get_payment_service)],
):
    return service.get(payment_id)
