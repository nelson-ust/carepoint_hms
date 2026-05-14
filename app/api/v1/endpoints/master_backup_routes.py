# app/api/v1/endpoints/master_backup_routes.py
from __future__ import annotations

"""
app.api.v1.endpoints.master_backup_routes

API endpoints for Master Database (SaaS-wide) backups.
"""

from typing import Annotated, List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_master_db
from app.core.dependencies import require_permission
from app.schemas.database_backup_schemas import DatabaseBackupReadSchema
from app.services.master_backup_service import MasterBackupService

router = APIRouter(tags=["SaaS Admin - Master Backups"])


def get_master_backup_service(db: Annotated[Session, Depends(get_master_db)]) -> MasterBackupService:
    return MasterBackupService(db)


@router.get(
    "/history",
    response_model=List[DatabaseBackupReadSchema],
    summary="Get master backup history",
)
def get_history(
    _: Annotated[bool, Depends(require_permission("SaaS_ADMIN"))],
    service: Annotated[MasterBackupService, Depends(get_master_backup_service)],
):
    """View historical backups of the central SaaS Master database."""
    return service.list_master_backups()


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Trigger master backup",
)
def create_master_backup(
    _: Annotated[bool, Depends(require_permission("SaaS_ADMIN"))],
    service: Annotated[MasterBackupService, Depends(get_master_backup_service)],
):
    """Start a backup of the central registry and tenant management metadata."""
    return service.run_master_backup(triggered_by="MANUAL")
