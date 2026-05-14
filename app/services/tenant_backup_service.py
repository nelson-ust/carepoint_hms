# app/services/tenant_backup_service.py
from __future__ import annotations

"""
app.services.tenant_backup_service

Service layer for Tenant-specific database backups.
All metadata is tracked in the Master DB for centralized management.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.cryptography import decrypt_string
from app.core.database import get_master_db_context
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logger import get_logger
from app.models.all_models import Tenant, DatabaseBackup
from app.repositories.database_backup_repository import DatabaseBackupRepository

logger = get_logger(__name__)


class TenantBackupService:
    """
    Orchestrates backup and restore for individual hospital tenants.
    """

    def __init__(self, tenant_db: Session, tenant_code: str) -> None:
        self.tenant_db = tenant_db
        self.tenant_code = tenant_code

    def create_backup(self, *, triggered_by: str = "MANUAL", retention_days: Optional[int] = None) -> dict:
        """
        Runs a full backup for the tenant.
        """
        retention = retention_days or int(getattr(settings, "BACKUP_RETENTION_DAYS", 30))
        
        with get_master_db_context() as master_db:
            repo = DatabaseBackupRepository(master_db)
            tenant = master_db.query(Tenant).filter(Tenant.code == self.tenant_code).first()
            if not tenant:
                raise NotFoundError(message="Tenant not found.")
            
            db_url = decrypt_string(tenant.db_connection_string) if tenant.db_connection_string else ""
            
            # Resolve bucket: 1. Tenant specific, 2. Global fallback, 3. Error
            bucket_name = tenant.aws_s3_bucket_name or getattr(settings, "AWS_S3_BUCKET_NAME", "")
            if not bucket_name:
                logger.error(f"No S3 bucket resolved for tenant {self.tenant_code}. Backup cannot proceed.")
                raise BadRequestError(message="S3 storage is mandatory for backups but no bucket is configured.")

            logger.info(f"Starting backup for tenant {self.tenant_code} (Bucket: {bucket_name})")

            # 1. Initialize record in Tenant DB
            repo = DatabaseBackupRepository(self.tenant_db)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"backup_{self.tenant_code}_{timestamp}.dump"
            
            record = repo.create_pending_record(
                filename=filename,
                triggered_by=triggered_by,
                retention_days=retention
            )
            self.tenant_db.commit()

            try:
                # 2. Run physical extraction
                repo.run_physical_backup(
                    record=record,
                    db_url=db_url,
                    bucket_name=bucket_name,
                    encrypt_at_rest=bool(getattr(settings, "BACKUP_ENCRYPT_AT_REST", True))
                )
                self.tenant_db.commit()
                
                return {
                    "success": True,
                    "backup_id": record.id,
                    "filename": record.filename,
                    "status": record.status,
                    "storage": record.storage_location
                }
            except Exception as e:
                self.tenant_db.rollback() 
                raise BadRequestError(message=f"Tenant backup failed: {str(e)}")

    def get_backup_dashboard_data(self) -> dict:
        """Dashboard statistics for the tenant, pulled from its own Database."""
        repo = DatabaseBackupRepository(self.tenant_db)
        backups = repo.get_all(limit=50)
        
        total_size = sum(b.size_bytes or 0 for b in backups if b.status == "COMPLETED")
        storage_gb = round(total_size / (1024**3), 4)
        
        last_backup = next((b for b in backups if b.status == "COMPLETED"), None)
        
        failed_count = len([b for b in backups[:5] if b.status == "FAILED"])
        health = "Healthy"
        if failed_count > 0: health = "Degraded"
        if failed_count >= 3: health = "Unhealthy"

        return {
            "summary": {
                "health_status": health,
                "storage_usage_gb": storage_gb,
                "last_backup_at": last_backup.backup_finished_at if last_backup else None,
                "recovery_points_count": len([b for b in backups if b.status == "COMPLETED"])
            },
            "backups": backups
        }

    def apply_retention(self) -> dict:
        """Purge expired backups for this tenant."""
        with get_master_db_context() as master_db:
            tenant = master_db.query(Tenant).filter(Tenant.code == self.tenant_code).first()
            if not tenant:
                raise NotFoundError(message="Tenant not found.")
                
            bucket_name = tenant.aws_s3_bucket_name or getattr(settings, "AWS_S3_BUCKET_NAME", "")
            
            repo = DatabaseBackupRepository(self.tenant_db)
            result = repo.purge_expired_backups(bucket_name)
            self.tenant_db.commit()
            return result
