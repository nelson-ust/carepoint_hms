"""
Tenant onboarding & administration schemas.

Tenants carry two contact channels:

* ``billing_email`` — used for SaaS-level financial communication
  (invoices, payment receipts, renewal reminders). Captured during
  onboarding.
* the tenant admin user's email — used for in-app/account-level
  notifications scoped to that user.

If ``billing_email`` is not supplied at onboarding, the registration
service falls back to ``admin_email`` so we always have a deliverable
target for invoice communication.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.subscription_schemas import TenantSubscriptionReadSchema


class TenantReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    db_connection_string: Optional[str] = None
    status: str

    domain_url: Optional[str] = None
    custom_domain: Optional[str] = None

    # Billing / financial-communication contact.
    billing_email: Optional[str] = None
    billing_phone: Optional[str] = None
    billing_contact_name: Optional[str] = None
    billing_address: Optional[str] = None
    tax_id: Optional[str] = None

    # We can include the active subscription info
    subscriptions: List[TenantSubscriptionReadSchema] = []


class TenantDomainReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    domain_name: str
    is_primary: bool


class TenantCreateSchema(BaseModel):
    name: str
    code: str
    domain_url: str
    custom_domain: Optional[str] = None
    db_name: Optional[str] = None


class TenantBillingContactSchema(BaseModel):
    """
    Standalone schema for updating just the SaaS-level billing contact
    (used by the ``/tenants/{id}/billing-contact`` PUT endpoint).
    """

    billing_email: Optional[EmailStr] = None
    billing_phone: Optional[str] = None
    billing_contact_name: Optional[str] = None
    billing_address: Optional[str] = None
    tax_id: Optional[str] = None


class TenantRegistrationSchema(BaseModel):
    # Tenant Info
    tenant_name: str
    tenant_code: str  # Slug used for subdomain
    domain_url: str

    # Billing / financial-communication contact.
    # ``billing_email`` defaults to ``admin_email`` when omitted, so the
    # tenant always has at least one deliverable address for invoices.
    billing_email: Optional[EmailStr] = Field(
        default=None,
        description=(
            "Dedicated email address used for invoices, payment receipts, "
            "and renewal alerts. Falls back to admin_email when omitted."
        ),
    )
    billing_phone: Optional[str] = None
    billing_contact_name: Optional[str] = None
    billing_address: Optional[str] = None
    tax_id: Optional[str] = None

    # Subscription Plan
    plan_code: str

    # Admin User Info
    admin_email: EmailStr
    admin_username: str
    admin_password: str
    admin_first_name: str
    admin_last_name: str


class TenantUpdateStatusSchema(BaseModel):
    status: str


class TenantListResponseSchema(BaseModel):
    total_count: int
    page: int
    page_size: int
    tenants: List[TenantReadSchema]
