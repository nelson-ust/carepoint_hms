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

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.subscription_schemas import TenantSubscriptionReadSchema



# Canonical deployment topologies a hospital can choose at registration.
VALID_DEPLOYMENT_MODELS = {"ON_PREMISE", "CLOUD_DEDICATED", "CLOUD_PLATFORM"}
_DEPLOYMENT_SYNONYMS = {
    "on_premise": "ON_PREMISE", "on-premise": "ON_PREMISE", "onpremise": "ON_PREMISE",
    "onprem": "ON_PREMISE", "on_prem": "ON_PREMISE", "on-prem": "ON_PREMISE",
    "premise": "ON_PREMISE", "local": "ON_PREMISE",
    "cloud_dedicated": "CLOUD_DEDICATED", "cloud-dedicated": "CLOUD_DEDICATED",
    "dedicated": "CLOUD_DEDICATED", "dedicated_cloud": "CLOUD_DEDICATED",
    "cloud_platform": "CLOUD_PLATFORM", "cloud-platform": "CLOUD_PLATFORM",
    "platform": "CLOUD_PLATFORM", "shared": "CLOUD_PLATFORM", "cloud": "CLOUD_PLATFORM",
    "saas": "CLOUD_PLATFORM",
}


def normalize_deployment_model(value, default: str = "CLOUD_PLATFORM") -> str:
    """Map any accepted spelling to one of VALID_DEPLOYMENT_MODELS."""
    if not value:
        return default
    key = str(value).strip().lower().replace(" ", "_")
    if key.upper() in VALID_DEPLOYMENT_MODELS:
        return key.upper()
    return _DEPLOYMENT_SYNONYMS.get(key, default)


def deployment_mode_for_model(model: str) -> str:
    """Runtime deployment_mode (cloud/onprem) implied by a deployment model."""
    return "onprem" if model == "ON_PREMISE" else "cloud"


class TenantReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    status: str
    is_provisioned: bool = False
    deployment_mode: Optional[str] = None
    deployment_model: Optional[str] = None
    provisioning_error: Optional[str] = None
    aws_s3_bucket_name: Optional[str] = None

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

    # Deployment topology the hospital prefers (on-premise / dedicated
    # cloud / platform-shared cloud). Defaults to the shared platform.
    deployment_model: Optional[str] = "CLOUD_PLATFORM"

    @field_validator("deployment_model")
    @classmethod
    def _norm_deployment_model(cls, v):
        return normalize_deployment_model(v)

    # Facility type chosen at registration. Gates which modules the tenant
    # receives once provisioned; only a SaaS admin can change it afterwards.
    facility_profile: Optional[str] = "HOSPITAL"

    @field_validator("facility_profile")
    @classmethod
    def _norm_facility_profile(cls, v):
        code = (v or "HOSPITAL").strip().upper()
        if code not in {"HOSPITAL", "DENTAL", "EYE", "PHARMACY"}:
            raise ValueError(f"Unknown facility type '{v}'.")
        return code

    @field_validator("tenant_code")
    @classmethod
    def _validate_tenant_code(cls, v):
        """
        Strict slug validation. ``tenant_code`` is used to build the tenant
        database name, SQL identifiers, and subdomain routing, so it must be a
        safe, predictable slug — never free text. This closes the identifier
        injection / malformed-identifier vector at the provisioning boundary.
        """
        import re

        code = (v or "").strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,38}", code):
            raise ValueError(
                "tenant_code must be 2-39 characters, start with a letter, and "
                "contain only lowercase letters, digits and underscores."
            )
        reserved = {
            "www", "api", "app", "admin", "saas", "carepointhms",
            "carepoint_hms", "localhost", "postgres", "public", "master",
            "template0", "template1",
        }
        if code in reserved:
            raise ValueError(f"tenant_code '{code}' is reserved and cannot be used.")
        return code

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


class TenantDropSchema(BaseModel):
    """Confirmation payload for permanently dropping a tenant from the platform.

    ``confirm_code`` must equal the tenant's own code (case-insensitive). This
    is a deliberate guard: a destructive drop (database + object storage +
    platform records) must never be triggerable by a stray click."""

    confirm_code: str = Field(
        ..., min_length=1,
        description="Must exactly match the target tenant's code to confirm the drop.",
    )


class TenantChangePlanSchema(BaseModel):
    plan_code: str
    # Billing cycle for the new subscription. Coerced to MONTHLY/YEARLY
    # by the service; defaults to MONTHLY when omitted.
    billing_interval: Optional[str] = "MONTHLY"


class ExtendSubscriptionSchema(BaseModel):
    """Extend a tenant's current subscription / trial by a duration, free."""
    days: int = Field(0, ge=0, le=3650)
    months: int = Field(0, ge=0, le=120)
    reason: Optional[str] = None


class GrantFreeSubscriptionSchema(BaseModel):
    """Grant a tenant a complimentary (free) subscription window."""
    days: int = Field(0, ge=0, le=3650)
    months: int = Field(0, ge=0, le=120)
    reason: Optional[str] = None
    # Optionally move the tenant onto a specific plan for the free window.
    plan_code: Optional[str] = None


class TenantListResponseSchema(BaseModel):
    total_count: int
    page: int
    page_size: int
    tenants: List[TenantReadSchema]
