# app/api/v1/endpoints/tenant_routes.py
from typing import Annotated
from fastapi import APIRouter, Depends, status, BackgroundTasks
import threading
from sqlalchemy.orm import Session

from app.core.database import get_master_db # We need a master db dependency
from app.core.dependencies import CurrentSaaSAdmin, CurrentSaaSSuperuser
from app.schemas.tenant_schemas import (
    TenantRegistrationSchema, 
    TenantReadSchema, 
    TenantListResponseSchema, 
    TenantUpdateStatusSchema,
    TenantChangePlanSchema
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
    Approve a pending tenant application and provision its database asynchronously.

    This endpoint performs the following workflow:
      1. Verifies the tenant exists and is not already provisioned.
      2. Dispatches the heavy database creation and migration logic onto a
         detached daemon thread. This ensures the API immediately responds
         and prevents the HTTP database session from timing out.
      3. Returns a 'PROVISIONING' status to the client, indicating that the 
         setup is actively running behind the scenes.

    The actual execution happens in `provision_tenant_background_task` which uses
    its own dedicated database connection.
    """
    # 1. Fetch the tenant from the master database to verify existence
    tenant = service.get_tenant(tenant_id)
    
    # 2. Idempotency Check: Prevent queuing multiple provisioning tasks 
    # if the tenant is already fully set up.
    if tenant.is_provisioned:
        return {
            "success": True,
            "message": f"Tenant '{tenant.name}' is already provisioned.",
            "tenant_id": tenant.id,
            "status": tenant.status.value if hasattr(tenant.status, 'value') else tenant.status,
            "is_provisioned": True,
        }

    # 3. Import the background worker function dynamically to avoid circular dependencies
    from app.services.tenant_service import provision_tenant_background_task
    
    # 4. Schedule the provisioning task in a completely detached thread.
    # We use threading.Thread instead of FastAPI's BackgroundTasks because 
    # BackgroundTasks keeps the request's dependencies (including the DB session) 
    # open until the task completes. A long provisioning process would cause the 
    # DB connection to time out, resulting in an OperationalError on teardown.
    threading.Thread(
        target=provision_tenant_background_task,
        args=(tenant_id,),
        daemon=True
    ).start()

    # 5. Return an immediate acknowledgment so the UI doesn't hang.
    return {
        "success": True,
        "message": (
            f"Tenant '{tenant.name}' has been approved. Database provisioning "
            f"is running in the background. The applicant will be notified by email once complete."
        ),
        "tenant_id": tenant.id,
        "status": "PROVISIONING",
        "is_provisioned": False,
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


@router.post(
    "/{tenant_id}/change-plan",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Change a tenant's subscription plan",
)
def change_tenant_plan(
    tenant_id: int,
    payload: TenantChangePlanSchema,
    _: CurrentSaaSSuperuser,
    service: Annotated[TenantService, Depends(get_tenant_service)],
):
    """
    Switch a tenant to a different subscription plan.
    Requires SaaS Superuser access.
    """
    subscription = service.change_subscription_plan(tenant_id, payload.plan_code)
    return {
        "success": True,
        "message": f"Tenant plan successfully changed to '{payload.plan_code}'.",
        "subscription_id": subscription.id,
        "plan_id": subscription.plan_id,
        "status": subscription.status,
    }
