# app/schemas/invoice_schema.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class InvoiceIssueFromBillingSchema(BaseModel):
    """Issue an invoice from an OPEN/DRAFT billing record."""

    billing_id: int
    payer_id: Optional[int] = None
    due_date: Optional[datetime] = None
    note: Optional[str] = None


class InvoiceItemReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_id: int
    billable_service_id: Optional[int] = None
    service_name: str
    service_code: Optional[str] = None
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    line_total: Decimal
    source_reference: Optional[str] = None
    created_at: Optional[datetime] = None


class InvoiceReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    visit_id: Optional[int] = None
    billing_id: Optional[int] = None
    payer_id: Optional[int] = None
    invoice_no: str
    status: str
    invoice_date: datetime
    due_date: Optional[datetime] = None
    subtotal_amount: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    balance_due: Decimal
    note: Optional[str] = None
    items: list[InvoiceItemReadSchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class InvoiceListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Invoices fetched successfully."
    items: list[InvoiceReadSchema]
    count: int
    meta: dict


class InvoiceActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    invoice: InvoiceReadSchema


class InvoiceVoidSchema(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)
