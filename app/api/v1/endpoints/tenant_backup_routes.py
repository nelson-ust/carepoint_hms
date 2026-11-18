# app/api/v1/endpoints/tenant_backup_routes.py
from __future__ import annotations

"""
app.api.v1.endpoints.tenant_backup_routes

API endpoints for Hospital Tenant backups.
"""

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.exceptions import BadRequestError
from app.core.multitenancy import get_current_tenant
from app.schemas.database_backup_schemas import BackupListResponseSchema
from app.services.tenant_backup_service import TenantBackupService

router = APIRouter(tags=["Clinical - Tenant Backups"])


def get_tenant_backup_service(db: Annotated[Session, Depends(get_db)]) -> TenantBackupService:
    tenant = get_current_tenant()
    if not tenant:
        # A clean 400 (with CORS headers) instead of an unhandled RuntimeError
        # 500 that the browser would surface as an opaque network failure.
        raise BadRequestError(
            message="No hospital context resolved for this request. Sign in to a tenant workspace and retry."
        )
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


@router.get(
    "/{backup_id}/download",
    summary="Download a decrypted, restorable backup artifact",
)
def download_backup(
    backup_id: int,
    _: Annotated[bool, Depends(require_permission("BACKUP_READ"))],
    service: Annotated[TenantBackupService, Depends(get_tenant_backup_service)],
):
    """
    Stream a completed recovery point back to the operator, decrypted and
    ready to restore with ``pg_restore``. Backups are encrypted at rest, so
    the app decrypts the artifact server-side and returns the plaintext
    custom-format dump under its real ``.dump`` filename.
    """
    artifact = service.get_backup_artifact(backup_id)
    filename = artifact["filename"]
    return Response(
        content=artifact["content"],
        media_type=artifact["media_type"],
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Backup-Filename": filename,
        },
    )


@router.delete(
    "/{backup_id}",
    summary="Delete a recovery point",
)
def delete_backup(
    backup_id: int,
    _: Annotated[bool, Depends(require_permission("BACKUP_CREATE"))],
    service: Annotated[TenantBackupService, Depends(get_tenant_backup_service)],
):
    """Remove a recovery point from the registry (and its stored artifact).

    Use this to clear failed or interrupted backups. Completed points can be
    removed too; the underlying object is best-effort deleted from storage.
    """
    return service.delete_backup(backup_id)


class RestoreRequestSchema(BaseModel):
    """Payload for a destructive database restore."""
    confirm_tenant_code: str = Field(
        ...,
        description="The operator must re-type the hospital's workspace code to confirm.",
    )
    safety_backup: bool = Field(
        True,
        description="Take a fresh pre-restore snapshot before overwriting (recommended).",
    )
    drop_existing: bool = Field(
        True,
        description="Drop existing objects before restoring (clean restore).",
    )


@router.post(
    "/{backup_id}/restore",
    summary="Restore the hospital database from a backup",
)
def restore_backup(
    backup_id: int,
    payload: RestoreRequestSchema,
    _: Annotated[bool, Depends(require_permission("BACKUP_RESTORE"))],
    service: Annotated[TenantBackupService, Depends(get_tenant_backup_service)],
):
    """
    Restore the hospital's database from a completed recovery point. This
    OVERWRITES live data, so it requires the BACKUP_RESTORE permission and a
    typed confirmation of the workspace code, and by default takes a
    pre-restore safety snapshot first.
    """
    return service.restore_backup(
        backup_id,
        confirm_tenant_code=payload.confirm_tenant_code,
        safety_backup=payload.safety_backup,
        drop_existing=payload.drop_existing,
    )
