# app/api/v1/endpoints/tenant_backup_routes.py
from __future__ import annotations

"""
app.api.v1.endpoints.tenant_backup_routes

API endpoints for Hospital Tenant backups.
"""

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.multitenancy import get_current_tenant
from app.schemas.database_backup_schemas import BackupListResponseSchema
from app.services.tenant_backup_service import TenantBackupService

router = APIRouter(tags=["Clinical - Tenant Backups"])


def get_tenant_backup_service(db: Annotated[Session, Depends(get_db)]) -> TenantBackupService:
    tenant = get_current_tenant()
    if not tenant:
        raise RuntimeError("Tenant context required.")
    return TenantBackupService(db, tenant.code)


@router.get(
    "/dashboard",
    response_model=BackupListResponseSchema,
    summary="Get tenant backup dashboard",
)
def get_dashboard(
    _: Annotated[bool, Depends(require_permission("BACKUP_READ"))],
    service: Annotated[TenantBackupService, Depends(get_tenant_backup_service)],
):
    """View health and history for hospital-specific backups."""
    return service.get_backup_dashboard_data()


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Trigger tenant backup",
)
def create_backup(
    _: Annotated[bool, Depends(require_permission("BACKUP_CREATE"))],
    service: Annotated[TenantBackupService, Depends(get_tenant_backup_service)],
    retention_days: Optional[int] = Query(None),
):
    """Manually start a backup of the hospital's clinical database."""
    return service.create_backup(triggered_by="MANUAL", retention_days=retention_days)


@router.post(
    "/retention/sweep",
    summary="Purge expired tenant backups",
)
def sweep_backups(
    _: Annotated[bool, Depends(require_permission("BACKUP_CREATE"))],
    service: Annotated[TenantBackupService, Depends(get_tenant_backup_service)],
):
    """Manually trigger the retention policy sweep for this tenant."""
    # Logic is implemented in TenantBackupService
    return service.apply_retention()
