from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentSaaSAdmin
from app.schemas.saas_usage_schemas import TenantUsageReadSchema
from app.services.tenant_usage_service import TenantUsageService

router = APIRouter(prefix="/saas/usage", tags=["SaaS Admin - Usage Tracking"])

@router.get(
    "/{tenant_id}",
    response_model=TenantUsageReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get Tenant Usage Metrics",
)
def get_tenant_usage(
    tenant_id: int,
    _: CurrentSaaSAdmin,
    db: Annotated[Session, Depends(get_db)]
):
    """
    Retrieve current usage metrics for a specific tenant.
    Accessible only to SaaS Admins.
    """
    return TenantUsageService.get_or_create_usage(db, tenant_id)

@router.post(
    "/{tenant_id}/sync",
    response_model=TenantUsageReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Sync Tenant Metrics",
)
def sync_tenant_metrics(
    tenant_id: int,
    _: CurrentSaaSAdmin,
):
    """
    Force a sync of usage metrics for a tenant by connecting to their database.
    Accessible only to SaaS Admins.
    """
    return TenantUsageService.sync_tenant_metrics(tenant_id)
