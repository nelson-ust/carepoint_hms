# app/schemas/billing_schemas.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ------- BILLABLE SERVICE -------

class BillableServiceCreateSchema(BaseModel):
    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    default_price: Decimal = Field(..., gt=Decimal("0"), description="Rate charged for this service; must be > 0.")
    account_id: int = Field(..., description="Chart-of-accounts account this service posts to.")
    description: Optional[str] = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "_")


class BillableServiceUpdateSchema(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    default_price: Optional[Decimal] = Field(None, gt=Decimal("0"))
    account_id: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class BillableServiceReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    category: Optional[str] = None
    default_price: Decimal
    account_id: Optional[int] = None
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def _resolve_account(cls, data):
        acct = getattr(data, "account", None)
        if acct is not None:
            try:
                data.account_code = acct.code
                data.account_name = acct.name
            except Exception:
                pass
        return data


class BillableServiceListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Billable services fetched successfully."
    items: list[BillableServiceReadSchema]
    count: int
    meta: dict


# ------- BILLING / BILLING ITEM -------

class BillingItemCreateSchema(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=255)
    service_code: Optional[str] = Field(None, max_length=100)
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    billable_service_id: Optional[int] = None
    source_reference: Optional[str] = Field(None, max_length=100)


class BillingCreateSchema(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    patient_insurance_id: Optional[int] = None
    notes: Optional[str] = None
    items: list[BillingItemCreateSchema] = Field(default_factory=list)


class BillingItemReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    billing_id: int
    billable_service_id: Optional[int] = None
    service_name: str
    service_code: Optional[str] = None
    category: Optional[str] = None
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    line_total: Decimal
    source_reference: Optional[str] = None
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    created_at: Optional[datetime] = None


class BillingReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    visit_id: Optional[int] = None
    patient_insurance_id: Optional[int] = None
    billing_no: str
    billing_date: datetime
    status: Optional[str] = None
    gross_amount: Decimal
    discount_amount: Decimal
    net_amount: Decimal
    notes: Optional[str] = None
    items: list[BillingItemReadSchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BillingListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Billings fetched successfully."
    items: list[BillingReadSchema]
    count: int
    meta: dict


class BillingActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    billing: BillingReadSchema


class BillableServiceActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    service: BillableServiceReadSchema


# ------- VISIT CHARGE SHEET + PARTIAL PAYMENTS -------

class VisitFinalizeSchema(BaseModel):
    """Optional metadata applied when finalizing a visit's invoice."""

    due_date: Optional[datetime] = None
    note: Optional[str] = None
    payer_id: Optional[int] = None


class VisitPaymentCreateSchema(BaseModel):
    amount: Decimal = Field(..., gt=Decimal("0"))
    payment_method: Optional[str] = Field(None, max_length=100)
    payment_reference: Optional[str] = Field(None, max_length=100)
    received_by_staff_id: Optional[int] = None
    membership_card_id: Optional[int] = Field(
        None, description="Required when payment_method is MEMBERSHIP_CARD."
    )
    note: Optional[str] = None


class BillingPaymentReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    billing_id: int
    amount: Decimal
    currency: str = "NGN"
    payment_method: Optional[str] = None
    payment_reference: str
    paid_at: Optional[datetime] = None
    note: Optional[str] = None
    transaction_metadata: Optional[dict] = None
    account_code: Optional[str] = None
    account_name: Optional[str] = None


class VisitInvoiceRefSchema(BaseModel):
    id: int
    invoice_no: str
    status: str
    total_amount: Decimal
    amount_paid: Decimal
    balance_due: Decimal


class VisitBillingSummarySchema(BaseModel):
    visit_id: int
    billing_id: Optional[int] = None
    billing_no: Optional[str] = None
    patient_id: Optional[int] = None
    status: Optional[str] = None
    currency: str = "NGN"
    total_charges: Decimal = Decimal("0")
    gross_amount: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    amount_paid: Decimal = Decimal("0")
    outstanding: Decimal = Decimal("0")
    unmapped_count: int = 0
    unaccounted_amount: Decimal = Decimal("0")
    items: list[BillingItemReadSchema] = Field(default_factory=list)
    payments: list[BillingPaymentReadSchema] = Field(default_factory=list)
    invoice: Optional[VisitInvoiceRefSchema] = None


# ------- BILLING MAPPING HEALTH -------

class UnmappedServiceSchema(BaseModel):
    id: int
    code: str
    name: str
    category: Optional[str] = None


class BillingMappingHealthSchema(BaseModel):
    success: bool = True
    total_services: int
    missing_account: int
    items: list[UnmappedServiceSchema] = Field(default_factory=list)
