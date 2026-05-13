"""
Carepoint HMS - Database Backup API Endpoints

This module exposes endpoints for managing tenant database backups. 
It supports dashboard statistics retrieval, manual backup triggering, 
file downloads with transparent decryption, and database restoration.

Access Control:
- BACKUP_READ: Required for listing and downloading backups.
- BACKUP_CREATE: Required for manual backup triggers and retention sweeps.
- BACKUP_RESTORE: Required for destructive database restoration.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.multitenancy import get_current_tenant
from app.schemas.database_backup_schemas import DatabaseBackupReadSchema, BackupListResponseSchema
from app.services.tenant_backup_service import TenantBackupService


router = APIRouter(prefix="/backups", tags=["Tenant - Database Backups"])


class RestoreRequestSchema(BaseModel):
    """Schema for database restoration requests."""
    target_timestamp: Optional[datetime] = Field(None, description="Optional PITR target timestamp")


def get_backup_service(db: Annotated[Session, Depends(get_db)]) -> TenantBackupService:
    """
    Dependency injector for TenantBackupService.
    
    Ensures that the service is initialized with the correct tenant context 
    resolved from the middleware.
    """
    tenant = get_current_tenant()
    if tenant is None:
        raise RuntimeError("Tenant context is required for backup operations.")
    return TenantBackupService(db, tenant.code)


@router.get(
    "",
    response_model=BackupListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Get backup dashboard data",
)
def get_backup_dashboard(
    _: Annotated[bool, Depends(require_permission("BACKUP_READ"))],
    service: Annotated[TenantBackupService, Depends(get_backup_service)],
):
    """
    Returns the unified dashboard data for the active hospital tenant.
    
    Includes:
    - Overall health summary (Healthy/Degraded/Unhealthy).
    - Storage usage statistics.
    - History of recovery points.
    """
    return service.get_backup_dashboard_data()


@router.post(
    "",
    response_model=DatabaseBackupReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger a new database backup",
)
def create_backup(
    _: Annotated[bool, Depends(require_permission("BACKUP_CREATE"))],
    service: Annotated[TenantBackupService, Depends(get_backup_service)],
    retention_days: Optional[int] = None,
):
    """
    Triggers an immediate, encrypted database backup.
    
    The artifact is extracted using pg_dump, optionally encrypted using 
    Fernet-AES, and uploaded to the tenant's regional S3 bucket.
    """
    return service.create_backup(triggered_by="MANUAL", retention_days=retention_days)


@router.get(
    "/{backup_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download a decrypted backup file",
    description=(
        "Downloads the backup artifact as a decrypted binary file. "
        "If the backup was encrypted at rest, it is transparently "
        "decrypted before being streamed to the client."
    ),
)
def download_backup(
    backup_id: int,
    _: Annotated[bool, Depends(require_permission("BACKUP_READ"))],
    service: Annotated[TenantBackupService, Depends(get_backup_service)],
):
    """
    Handles the retrieval and transparent decryption of a backup artifact.
    
    Returns a FileResponse that streams the binary data. Background tasks 
    ensure that decrypted temporary files are cleaned up after the stream ends.
    """
    result = service.prepare_download_file(backup_id)

    headers = {}
    if result.get("checksum_sha256"):
        headers["X-Checksum-SHA256"] = result["checksum_sha256"]

    # FileResponse handles streaming with background cleanup
    response = FileResponse(
        path=result["file_path"],
        filename=result["filename"],
        media_type=result["media_type"],
        headers=headers,
        background=_make_cleanup_task(result.get("cleanup_paths", [])),
    )
    return response


def _make_cleanup_task(paths: list[str]):
    """
    Creates a Starlette BackgroundTask to delete temporary processing files.
    """
    from starlette.background import BackgroundTask

    def _cleanup() -> None:
        for p in paths:
            try:
                if os.path.exists(p):
                    os.unlink(p)
            except OSError:
                pass

    return BackgroundTask(_cleanup)


@router.post(
    "/{backup_id}/restore",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Restore database from backup",
)
def restore_backup(
    backup_id: int,
    payload: RestoreRequestSchema,
    _: Annotated[bool, Depends(require_permission("BACKUP_RESTORE"))],
    service: Annotated[TenantBackupService, Depends(get_backup_service)],
):
    """
    Overwrites the current tenant database with the data from a backup.
    
    WARNING: This terminates all active database sessions to allow a 
    clean restore.
    """
    return service.restore_backup(backup_id, target_timestamp=payload.target_timestamp)


@router.post(
    "/retention/sweep",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Apply retention policy (Sweep)",
)
def apply_retention(
    _: Annotated[bool, Depends(require_permission("BACKUP_CREATE"))],
    service: Annotated[TenantBackupService, Depends(get_backup_service)],
):
    """
    Triggers an administrative sweep to find and expire backups that have 
    surpassed their retention period.
    """
    return service.apply_retention()
