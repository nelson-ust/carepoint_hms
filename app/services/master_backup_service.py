# app/services/master_backup_service.py
from __future__ import annotations

"""
app.services.master_backup_service

Service layer for SaaS Master Database backup orchestration.
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.core.logger import get_logger
from app.models.all_models import MasterDatabaseBackup
from app.repositories.database_backup_repository import DatabaseBackupRepository

logger = get_logger(__name__)


class MasterBackupService:
    """
    Orchestrator for Master Database backups.
    """

    def __init__(self, master_db: Session) -> None:
        self.db = master_db
        self.repo = DatabaseBackupRepository(master_db, model=MasterDatabaseBackup)
        self.bucket_name = getattr(settings, "AWS_S3_MASTER_BUCKET_NAME", None) or \
                          getattr(settings, "AWS_S3_BUCKET_NAME", "carepoint-master-backups")

    def run_master_backup(self, triggered_by: str = "MANUAL") -> dict:
        """Triggers a full backup of the Master database."""
        db_url = getattr(settings, "MASTER_DATABASE_URL", None) or getattr(settings, "DATABASE_URL", "")
        if not db_url:
            raise BadRequestError(message="MASTER_DATABASE_URL not configured.")

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"master_backup_{timestamp}.dump"
        
        record = self.repo.create_pending_record(
            filename=filename,
            triggered_by=triggered_by,
            retention_days=int(getattr(settings, "MASTER_BACKUP_RETENTION_DAYS", 90))
        )
        self.db.commit()

        try:
            self.repo.run_physical_backup(
                record=record,
                db_url=db_url,
                bucket_name=self.bucket_name,
                encrypt_at_rest=True
            )
            self.db.commit()
            return {"success": True, "backup_id": record.id, "status": record.status}
        except Exception as e:
            self.db.commit()
            raise BadRequestError(message=f"Master backup failed: {str(e)}")

    def list_master_backups(self, limit: int = 20):
        return self.repo.get_all(limit=limit)

    def apply_retention(self) -> dict:
        """Purge expired master backups."""
        result = self.repo.purge_expired_backups(self.bucket_name)
        self.db.commit()
        return result
