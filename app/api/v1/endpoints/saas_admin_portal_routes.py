from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_master_db
from app.core.dependencies import CurrentSaaSSuperuser
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/saas/admin", tags=["SaaS - Admin Portal"])

@router.get("/health", response_model=dict)
def get_system_health(
    db: Annotated[Session, Depends(get_master_db)],
    _: CurrentSaaSSuperuser
):
    """
    Get the health status of core infrastructure (SaaS Superuser only).
    """
    return TenantService(db).get_system_health()

@router.post("/migrations/sync", response_model=dict)
def sync_tenant_migrations(
    db: Annotated[Session, Depends(get_master_db)],
    _: CurrentSaaSSuperuser
):
    """
    Trigger database schema synchronization for all provisioned tenants.
    """
    return TenantService(db).run_migrations_all_tenants()
