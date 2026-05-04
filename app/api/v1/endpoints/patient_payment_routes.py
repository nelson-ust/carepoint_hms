"""
Patient-payment routes.

These endpoints sit on top of :class:`PatientPaymentService` and let the
front-end (or a cashier UI) settle invoices through any of the channels
the tenant has configured.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser
from app.core.enums import PaymentChannel, PaymentProvider, PaymentStatus
from app.services.patient_payment_service import PatientPaymentService


router = APIRouter(prefix="/patient-payments", tags=["Patient Payments"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AvailableMethodSchema(BaseModel):
    id: int
    channel: str
    provider: str
    display_name: str
    description: Optional[str] = None
    currency: str
    minimum_amount: Optional[float] = None
    maximum_amount: Optional[float] = None
    fee_percent: float = 0
    fee_flat: float = 0
    fee_borne_by_patient: bool = False
    is_default: bool = False


class PayInvoiceSchema(BaseModel):
    invoice_id: int
    amount: float = Field(..., gt=0)
    channel: PaymentChannel
    patient_id: Optional[int] = None
    provider: Optional[PaymentProvider] = None
    config_id: Optional[int] = None
    cashier_staff_id: Optional[int] = None
    callback_url: Optional[str] = None
    external_reference: Optional[str] = None
    note: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class PaymentReadSchema(BaseModel):
    id: int
    invoice_id: int
    payment_reference: str
    payment_method: Optional[str] = None
    payment_status: PaymentStatus
    amount: Decimal
    currency: str
    paid_at: Optional[datetime] = None
    transaction_metadata: Optional[dict[str, Any]] = None
    note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceSummarySchema(BaseModel):
    id: int
    invoice_no: str
    total_amount: Decimal
    amount_paid: Decimal
    balance_due: Decimal
    status: str

    model_config = ConfigDict(from_attributes=True)


class PayInvoiceResponseSchema(BaseModel):
    status: str
    payment: PaymentReadSchema
    invoice: InvoiceSummarySchema
    authorization_url: Optional[str] = None
    provider_reference: Optional[str] = None
    provider: Optional[str] = None
    card_balance_after: Optional[float] = None
    points_redeemed: Optional[float] = None
    points_balance_after: Optional[float] = None


class GatewayConfirmSchema(BaseModel):
    payment_reference: str
    succeeded: bool = True
    provider_payload: Optional[dict[str, Any]] = None


def _service(db: Annotated[Session, Depends(get_db)]) -> PatientPaymentService:
    return PatientPaymentService(db)


def _build_response(result: dict) -> dict:
    invoice = result["invoice"]
    payment = result["payment"]
    return {
        "status": result.get("status", "ok"),
        "payment": payment,
        "invoice": {
            "id": invoice.id,
            "invoice_no": invoice.invoice_no,
            "total_amount": invoice.total_amount,
            "amount_paid": invoice.amount_paid,
            "balance_due": invoice.balance_due,
            "status": str(getattr(invoice.status, "value", invoice.status)),
        },
        "authorization_url": result.get("authorization_url"),
        "provider_reference": result.get("provider_reference"),
        "provider": result.get("provider"),
        "card_balance_after": result.get("card_balance_after"),
        "points_redeemed": result.get("points_redeemed"),
        "points_balance_after": result.get("points_balance_after"),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "/methods",
    response_model=list[AvailableMethodSchema],
    summary="List active payment methods configured for the tenant",
)
def list_methods(
    _: CurrentActiveUser,
    service: Annotated[PatientPaymentService, Depends(_service)],
):
    return service.list_available_methods()


@router.post(
    "/pay",
    response_model=PayInvoiceResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Pay (or partially pay) an invoice using the chosen channel",
)
def pay_invoice(
    payload: PayInvoiceSchema,
    _: CurrentActiveUser,
    service: Annotated[PatientPaymentService, Depends(_service)],
):
    result = service.pay_invoice(
        invoice_id=payload.invoice_id,
        amount=Decimal(str(payload.amount)),
        channel=payload.channel,
        patient_id=payload.patient_id,
        provider=payload.provider,
        config_id=payload.config_id,
        cashier_staff_id=payload.cashier_staff_id,
        callback_url=payload.callback_url,
        external_reference=payload.external_reference,
        note=payload.note,
        metadata=payload.metadata,
    )
    return _build_response(result)


@router.post(
    "/confirm-gateway",
    response_model=PaymentReadSchema,
    summary="Mark a gateway-initiated payment as SUCCESSFUL or FAILED",
)
def confirm_gateway(
    payload: GatewayConfirmSchema,
    _: CurrentActiveUser,
    service: Annotated[PatientPaymentService, Depends(_service)],
):
    """
    Most providers will call back into our webhook endpoint, but this
    route is a useful manual / polling alternative — for example after
    redirecting the patient back to the tenant front-end with a
    ``reference`` query parameter.
    """
    return service.confirm_gateway_payment(
        payment_reference=payload.payment_reference,
        succeeded=payload.succeeded,
        provider_payload=payload.provider_payload,
    )
