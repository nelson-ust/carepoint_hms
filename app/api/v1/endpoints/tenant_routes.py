# app/api/v1/endpoints/tenant_routes.py
from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_master_db # We need a master db dependency
from app.core.dependencies import CurrentSaaSAdmin, CurrentSaaSSuperuser
from app.schemas.tenant_schemas import (
    TenantRegistrationSchema, 
    TenantReadSchema, 
    TenantListResponseSchema, 
    TenantUpdateStatusSchema
)
from app.services.tenant_service import TenantService
from typing import Optional

router = APIRouter(prefix="/tenants", tags=["SaaS - Tenants"])

def get_tenant_service(db: Annotated[Session, Depends(get_master_db)]) -> TenantService:
    return TenantService(db)

@router.post(
    "/register",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new tenant onboarding application",
)
def register_tenant(
    payload: TenantRegistrationSchema,
    service: Annotated[TenantService, Depends(get_tenant_service)],
):
    """
    Submit a new hospital onboarding application.

    What this endpoint does:

      * persists the tenant application in the master database with
        ``status=PENDING``,
      * captures the prospective admin's credentials (hashed) and
        billing contact for later use,
      * notifies all active SaaS administrators that an approval is
        required,
      * sends an acknowledgement email to the applicant
        (``admin_email``, plus ``billing_email`` when distinct).

    What this endpoint does **not** do:

      * it does NOT create the tenant database,
      * it does NOT run migrations or seed any data,
      * the applicant cannot sign in until a SaaS admin approves the
        registration via ``POST /api/v1/tenants/{tenant_id}/approve``.
    """
    tenant = service.register_tenant(payload)
    return {
        "success": True,
        "message": (
            "Tenant registration submitted successfully. An "
            "acknowledgement has been emailed to the admin contact, and "
            "your application is now pending SaaS-admin approval."
        ),
        "tenant_id": tenant.id,
        "tenant_code": tenant.code,
        "status": "PENDING",
    }


@router.post(
    "/{tenant_id}/approve",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Approve a pending registration and provision the tenant",
)
def approve_tenant(
    tenant_id: int,
    _: CurrentSaaSSuperuser,
    service: Annotated[TenantService, Depends(get_tenant_service)],
):
    """
    Approve a pending tenant application and provision its database.

    This is the **only** entry point that creates a tenant database.
    Steps performed by the underlying service:

      1. Create the physical PostgreSQL database for the tenant.
      2. Create tables and seed defaults (roles, permissions,
         departments, service points).
      3. Create the tenant admin user from the captured registration
         data.
      4. Bootstrap default :class:`TenantSetting`.
      5. Mark the tenant ``ACTIVE`` and the subscription ``ACTIVE``
         (TRIALING is preserved).
      6. Provision the tenant's S3 bucket (best-effort).
      7. Email the applicant that their tenant environment is now live.

    Idempotent: if the tenant is already provisioned the endpoint is a
    no-op and returns the current record.
    """
    tenant = service.provision_tenant(tenant_id)
    return {
        "success": True,
        "message": (
            f"Tenant '{tenant.name}' has been approved and provisioned. "
            f"The applicant has been notified by email."
        ),
        "tenant_id": tenant.id,
        "status": "ACTIVE",
        "is_provisioned": True,
    }

@router.get(
    "",
    response_model=TenantListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List all tenants",
)
def list_tenants(
    _: CurrentSaaSAdmin,
    service: Annotated[TenantService, Depends(get_tenant_service)],
    page: int = 1,
    page_size: int = 20,
    tenant_status: Optional[str] = None
):
    """
    List all registered tenants.
    """
    return service.get_tenants(page=page, page_size=page_size, status=tenant_status)

@router.get(
    "/{tenant_id}",
    response_model=TenantReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get tenant details",
)
def get_tenant(
    tenant_id: int,
    _: CurrentSaaSAdmin,
    service: Annotated[TenantService, Depends(get_tenant_service)],
):
    """
    Retrieve details of a specific hospital tenant.
    """
    return service.get_tenant(tenant_id)

@router.put(
    "/{tenant_id}/status",
    response_model=TenantReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update tenant status",
)
def update_tenant_status(
    tenant_id: int,
    payload: TenantUpdateStatusSchema,
    _: CurrentSaaSSuperuser,
    service: Annotated[TenantService, Depends(get_tenant_service)],
):
    """
    Suspend, activate, or reject a tenant.
    Requires SaaS Superuser access.
    """
    return service.update_tenant_status(tenant_id, new_status=payload.status)
