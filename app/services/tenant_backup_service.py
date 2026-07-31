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
            
            # Central policy: backups live in the TENANT's own bucket —
            # provision it on demand; never fall back to the platform bucket.
            from app.services.aws_s3_service import S3Service
            bucket_name = S3Service().ensure_tenant_bucket(master_db, tenant)
            if not bucket_name:
                logger.error(f"No S3 bucket resolved for tenant {self.tenant_code}. Backup cannot proceed.")
                raise BadRequestError(message="S3 storage is mandatory for backups but no tenant bucket could be provisioned.")

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
                    "filename": record.file_name,
                    "status": record.status,
                    "storage": record.storage_location
                }
            except Exception as e:
                self.tenant_db.rollback() 
                raise BadRequestError(message=f"Tenant backup failed: {str(e)}")

    def get_backup_dashboard_data(self) -> dict:
        """Dashboard statistics for the tenant, pulled from its own Database."""
        repo = DatabaseBackupRepository(self.tenant_db)
        try:
            backups = repo.get_all(limit=50)
        except Exception as exc:  # e.g. tenant DB missing the backup table
            logger.exception(
                "Backup dashboard query failed for tenant %s: %s", self.tenant_code, exc
            )
            self.tenant_db.rollback()
            retention_days = int(getattr(settings, "BACKUP_RETENTION_DAYS", 30))
            return {
                "summary": {
                    "health_status": "Unknown",
                    "health_description": (
                        "Backup history is unavailable for this hospital. If this "
                        "persists, run a tenant schema sync (init_db --sync-tenants)."
                    ),
                    "retention_policy": f"{retention_days} Days (Rolling)",
                    "storage_usage_gb": 0.0,
                    "last_backup_at": None,
                    "recovery_points_count": 0,
                },
                "backups": [],
            }
        
        # The repository writes "SUCCESS"; older/manual rows may say "COMPLETED".
        done = {"SUCCESS", "COMPLETED"}
        total_size = sum(b.size_bytes or 0 for b in backups if b.status in done)
        storage_gb = round(total_size / (1024**3), 4)

        last_backup = next((b for b in backups if b.status in done), None)

        failed_count = len([b for b in backups[:5] if b.status == "FAILED"])
        health = "Healthy"
        if failed_count > 0: health = "Degraded"
        if failed_count >= 3: health = "Unhealthy"

        if health == "Healthy":
            health_description = "Recent backups completed without failures."
        else:
            health_description = f"{failed_count} of the last 5 backup attempts failed."

        retention_days = int(getattr(settings, "BACKUP_RETENTION_DAYS", 30))

        return {
            "summary": {
                "health_status": health,
                "health_description": health_description,
                "retention_policy": f"{retention_days} Days (Rolling)",
                "storage_usage_gb": storage_gb,
                "last_backup_at": last_backup.completed_at if last_backup else None,
                "recovery_points_count": len([b for b in backups if b.status in done])
            },
            "backups": backups
        }

    def get_download_link(self, backup_id: int, *, expires_in: int = 3600) -> dict:
        """
        Produce a short-lived presigned URL for a completed backup artifact.
        """
        repo = DatabaseBackupRepository(self.tenant_db)
        record = self.tenant_db.query(DatabaseBackup).filter(DatabaseBackup.id == backup_id).first()
        if record is None:
            raise NotFoundError(message="Backup record not found.")
        if record.status not in ("SUCCESS", "COMPLETED"):
            raise BadRequestError(message=f"This backup is not downloadable (status: {record.status}).")
        if not record.s3_key:
            raise BadRequestError(message="No storage artifact is attached to this backup.")

        with get_master_db_context() as master_db:
            tenant = master_db.query(Tenant).filter(Tenant.code == self.tenant_code).first()
            from app.services.aws_s3_service import S3Service
            bucket_name = S3Service().ensure_tenant_bucket(master_db, tenant) or ""

        from app.services.aws_s3_service import S3Service

        url = S3Service().generate_presigned_url(bucket_name, record.s3_key, expires_in=expires_in)
        if not url:
            raise BadRequestError(
                message="Could not generate a download link — S3 storage is not configured."
            )
        return {
            "success": True,
            "download_url": url,
            "s3_url": url,
            "filename": record.file_name,
            "size_bytes": record.size_bytes,
            "expires_in": expires_in,
        }

    def apply_retention(self) -> dict:
        """Purge expired backups for this tenant."""
        with get_master_db_context() as master_db:
            tenant = master_db.query(Tenant).filter(Tenant.code == self.tenant_code).first()
            if not tenant:
                raise NotFoundError(message="Tenant not found.")
                
            from app.services.aws_s3_service import S3Service
            bucket_name = S3Service().ensure_tenant_bucket(master_db, tenant) or ""

            repo = DatabaseBackupRepository(self.tenant_db)
            result = repo.purge_expired_backups(bucket_name)
            self.tenant_db.commit()
            return result
