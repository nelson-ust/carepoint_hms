"""
Tenant payment-method configuration endpoints.

Each tenant uses these endpoints to declare which payment channels they
accept and to wire up online gateway credentials. Credentials submitted
here are encrypted at rest by :class:`TenantPaymentMethodService`; only
the gateway adapter ever sees them in plaintext, in memory, at the
moment of use.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser
from app.core.enums import PaymentChannel, PaymentProvider
from app.services.tenant_payment_method_service import TenantPaymentMethodService


router = APIRouter(
    prefix="/tenant-payment-methods",
    tags=["Tenant - Payment Methods"],
)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def _service(db: Annotated[Session, Depends(get_db)]) -> TenantPaymentMethodService:
    """Provide a TenantPaymentMethodService bound to the request's DB session."""
    return TenantPaymentMethodService(db)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PaymentMethodCredentialsSchema(BaseModel):
    secret_key: Optional[str] = None
    public_key: Optional[str] = None
    webhook_secret: Optional[str] = None
    api_token: Optional[str] = None
    merchant_id: Optional[str] = None


class PaymentMethodCreateSchema(BaseModel):
    channel: PaymentChannel
    provider: PaymentProvider = PaymentProvider.MANUAL
    display_name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None
    currency: str = "NGN"
    is_active: bool = True
    is_default: bool = False
    accepts_patient_payments: bool = True
    accepts_subscription_payments: bool = False
    minimum_amount: Optional[float] = Field(default=None, ge=0)
    maximum_amount: Optional[float] = Field(default=None, ge=0)
    fee_percent: float = Field(default=0, ge=0, le=100)
    fee_flat: float = Field(default=0, ge=0)
    fee_borne_by_patient: bool = False
    api_base_url: Optional[str] = None
    callback_url: Optional[str] = None
    webhook_url: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None
    sandbox_mode: bool = False
    credentials: Optional[PaymentMethodCredentialsSchema] = None


class PaymentMethodUpdateSchema(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    currency: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    accepts_patient_payments: Optional[bool] = None
    accepts_subscription_payments: Optional[bool] = None
    minimum_amount: Optional[float] = None
    maximum_amount: Optional[float] = None
    fee_percent: Optional[float] = None
    fee_flat: Optional[float] = None
    fee_borne_by_patient: Optional[bool] = None
    api_base_url: Optional[str] = None
    callback_url: Optional[str] = None
    webhook_url: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None
    sandbox_mode: Optional[bool] = None
    credentials: Optional[PaymentMethodCredentialsSchema] = None


class PaymentMethodReadSchema(BaseModel):
    id: int
    channel: PaymentChannel
    provider: PaymentProvider
    display_name: str
    description: Optional[str] = None
    currency: str
    is_active: bool
    is_default: bool
    accepts_patient_payments: bool
    accepts_subscription_payments: bool
    minimum_amount: Optional[float] = None
    maximum_amount: Optional[float] = None
    fee_percent: float = 0
    fee_flat: float = 0
    fee_borne_by_patient: bool = False
    api_base_url: Optional[str] = None
    callback_url: Optional[str] = None
    webhook_url: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None
    sandbox_mode: bool = False
    last_used_at: Optional[datetime] = None
    last_test_at: Optional[datetime] = None
    last_test_status: Optional[str] = None
    last_test_error: Optional[str] = None

    # Credential presence flags only — never the plaintext.
    has_secret_key: bool = False
    has_public_key: bool = False
    has_webhook_secret: bool = False
    has_api_token: bool = False
    has_merchant_id: bool = False

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[PaymentMethodReadSchema],
    summary="List the tenant's payment methods",
)
def list_payment_methods(
    _: AdminUser,
    service: Annotated[TenantPaymentMethodService, Depends(_service)],
    only_active: bool = False,
):
    return service.list_configs(only_active=only_active)


@router.post(
    "",
    response_model=PaymentMethodReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Configure a new payment method",
)
def create_payment_method(
    payload: PaymentMethodCreateSchema,
    _: AdminUser,
    service: Annotated[TenantPaymentMethodService, Depends(_service)],
):
    creds = payload.credentials.model_dump(exclude_none=True) if payload.credentials else None
    return service.create(
        channel=payload.channel,
        provider=payload.provider,
        display_name=payload.display_name,
        description=payload.description,
        currency=payload.currency,
        is_active=payload.is_active,
        is_default=payload.is_default,
        accepts_patient_payments=payload.accepts_patient_payments,
        accepts_subscription_payments=payload.accepts_subscription_payments,
        minimum_amount=payload.minimum_amount,
        maximum_amount=payload.maximum_amount,
        fee_percent=payload.fee_percent,
        fee_flat=payload.fee_flat,
        fee_borne_by_patient=payload.fee_borne_by_patient,
        api_base_url=payload.api_base_url,
        callback_url=payload.callback_url,
        webhook_url=payload.webhook_url,
        metadata_json=payload.metadata_json,
        sandbox_mode=payload.sandbox_mode,
        credentials=creds,
    )


@router.put(
    "/{config_id}",
    response_model=PaymentMethodReadSchema,
    summary="Update a payment-method configuration",
)
def update_payment_method(
    config_id: int,
    payload: PaymentMethodUpdateSchema,
    _: AdminUser,
    service: Annotated[TenantPaymentMethodService, Depends(_service)],
):
    creds = payload.credentials.model_dump(exclude_none=True) if payload.credentials else None
    return service.update(
        config_id,
        display_name=payload.display_name,
        description=payload.description,
        currency=payload.currency,
        is_active=payload.is_active,
        is_default=payload.is_default,
        accepts_patient_payments=payload.accepts_patient_payments,
        accepts_subscription_payments=payload.accepts_subscription_payments,
        minimum_amount=payload.minimum_amount,
        maximum_amount=payload.maximum_amount,
        fee_percent=payload.fee_percent,
        fee_flat=payload.fee_flat,
        fee_borne_by_patient=payload.fee_borne_by_patient,
        api_base_url=payload.api_base_url,
        callback_url=payload.callback_url,
        webhook_url=payload.webhook_url,
        metadata_json=payload.metadata_json,
        sandbox_mode=payload.sandbox_mode,
        credentials=creds,
    )


@router.delete(
    "/{config_id}",
    status_code=status.HTTP_200_OK,
    summary="Soft-delete a payment-method configuration",
)
def delete_payment_method(
    config_id: int,
    _: AdminUser,
    service: Annotated[TenantPaymentMethodService, Depends(_service)],
):
    service.delete(config_id)
    return {"success": True}


@router.post(
    "/{config_id}/test",
    summary="Run a credential-completeness test for a configuration",
)
def test_payment_method(
    config_id: int,
    _: AdminUser,
    service: Annotated[TenantPaymentMethodService, Depends(_service)],
):
    return service.test_config(config_id)
