"""
Tenant database backup endpoints.

Backed by :class:`TenantBackupService`, which adds encryption-at-rest,
SHA-256 integrity, retention enforcement, PITR-friendly metadata, and
admin-facing notifications.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.multitenancy import get_current_tenant
from app.schemas.database_backup_schemas import DatabaseBackupReadSchema
from app.services.tenant_backup_service import TenantBackupService


router = APIRouter(prefix="/backups", tags=["Tenant - Database Backups"])


class RestoreRequestSchema(BaseModel):
    target_timestamp: Optional[datetime] = None


def get_backup_service(db: Annotated[Session, Depends(get_db)]) -> TenantBackupService:
    tenant = get_current_tenant()
    if tenant is None:
        # Defensive: middleware should have set this; raise via service.
        raise RuntimeError("Tenant context is required for backup operations.")
    return TenantBackupService(db, tenant.code)


@router.get(
    "",
    response_model=list[DatabaseBackupReadSchema],
    status_code=status.HTTP_200_OK,
    summary="List database backups",
)
def list_backups(
    _: Annotated[bool, Depends(require_permission("BACKUP_READ"))],
    service: Annotated[TenantBackupService, Depends(get_backup_service)],
):
    return service.list_backups()


@router.post(
    "",
    response_model=DatabaseBackupReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger an encrypted database backup",
)
def create_backup(
    _: Annotated[bool, Depends(require_permission("BACKUP_CREATE"))],
    service: Annotated[TenantBackupService, Depends(get_backup_service)],
    retention_days: Optional[int] = None,
):
    return service.create_backup(triggered_by="MANUAL", retention_days=retention_days)


@router.get(
    "/{backup_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download a decrypted backup file",
    description=(
        "Downloads the backup artifact as a decrypted binary file. "
        "If the backup was encrypted at rest, it is transparently "
        "decrypted before being streamed to the client. The response "
        "includes a Content-Disposition header with the original "
        "filename and an X-Checksum-SHA256 header for integrity "
        "verification."
    ),
    responses={
        200: {
            "content": {"application/octet-stream": {}},
            "description": "The decrypted backup file.",
        },
    },
)
def download_backup(
    backup_id: int,
    _: Annotated[bool, Depends(require_permission("BACKUP_READ"))],
    service: Annotated[TenantBackupService, Depends(get_backup_service)],
):
    result = service.prepare_download_file(backup_id)

    headers = {}
    if result.get("checksum_sha256"):
        headers["X-Checksum-SHA256"] = result["checksum_sha256"]

    response = FileResponse(
        path=result["file_path"],
        filename=result["filename"],
        media_type=result["media_type"],
        headers=headers,
        background=_make_cleanup_task(result.get("cleanup_paths", [])),
    )
    return response


def _make_cleanup_task(paths: list[str]):
    """Return a Starlette ``BackgroundTask`` that deletes temp files."""
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
    summary="Restore from a backup",
)
def restore_backup(
    backup_id: int,
    payload: RestoreRequestSchema,
    _: Annotated[bool, Depends(require_permission("BACKUP_RESTORE"))],
    service: Annotated[TenantBackupService, Depends(get_backup_service)],
):
    return service.restore_backup(backup_id, target_timestamp=payload.target_timestamp)


@router.post(
    "/retention/sweep",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Apply the configured retention policy",
)
def apply_retention(
    _: Annotated[bool, Depends(require_permission("BACKUP_CREATE"))],
    service: Annotated[TenantBackupService, Depends(get_backup_service)],
):
    return service.apply_retention()
