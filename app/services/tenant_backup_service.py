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
from cryptography.fernet import InvalidToken

from app.core.cryptography import decrypt_bytes, decrypt_string
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
                # The repository already marked the record FAILED (with the
                # error message) before re-raising. Persist that so the row does
                # not get stuck in PENDING at 0 B. Only roll back — then re-mark
                # FAILED on a fresh transaction — if the commit itself fails.
                try:
                    self.tenant_db.commit()
                except Exception:
                    self.tenant_db.rollback()
                    try:
                        DatabaseBackupRepository(self.tenant_db).mark_failed(
                            record.id, str(e)
                        )
                        self.tenant_db.commit()
                    except Exception:
                        self.tenant_db.rollback()
                raise BadRequestError(message=f"Tenant backup failed: {str(e)}")

    def get_backup_dashboard_data(self) -> dict:
        """Dashboard statistics for the tenant, pulled from its own Database."""
        repo = DatabaseBackupRepository(self.tenant_db)
        try:
            # Flip any stuck PENDING rows (interrupted before upload) to FAILED so
            # the registry never shows a perpetual 0-byte PENDING.
            try:
                reconciled = repo.reconcile_stale_pending(
                    older_than_minutes=int(getattr(settings, "BACKUP_PENDING_TIMEOUT_MIN", 15))
                )
                if reconciled:
                    self.tenant_db.commit()
            except Exception:
                self.tenant_db.rollback()
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

    def delete_backup(self, backup_id: int) -> dict:
        """Remove a recovery point: soft-delete the record and best-effort
        delete its S3 object. Intended for clearing FAILED / stale-PENDING or
        otherwise unwanted backups from the registry."""
        with get_master_db_context() as master_db:
            tenant = master_db.query(Tenant).filter(Tenant.code == self.tenant_code).first()
            bucket_name = ""
            if tenant is not None:
                try:
                    from app.services.aws_s3_service import S3Service
                    bucket_name = S3Service().ensure_tenant_bucket(master_db, tenant) or ""
                except Exception as exc:
                    logger.warning("Could not resolve bucket for delete on %s: %s", self.tenant_code, exc)

        repo = DatabaseBackupRepository(self.tenant_db)
        repo.delete_record(backup_id, bucket_name=bucket_name or None)
        self.tenant_db.commit()
        return {"success": True, "backup_id": backup_id, "message": "Recovery point deleted."}

    def get_backup_artifact(self, backup_id: int) -> dict:
        """
        Return a completed backup DECRYPTED and ready to restore.

        Backups are Fernet-encrypted at rest in S3. Handing the operator the
        raw object (as a presigned URL did) yields an opaque ``.dump.enc``
        blob that ``pg_restore`` cannot read — which is exactly why the
        downloaded file looked invalid. Here we fetch the object, decrypt it
        when needed, and return the plaintext custom-format dump under its
        true ``.dump`` name.

        NOTE: Fernet is not a streaming cipher, so the artifact is decrypted
        in memory. That is appropriate for per-tenant clinical databases; if
        tenant dumps ever grow large enough to matter, switch to a chunked
        envelope format (e.g. AES-GCM over streamed S3 ranges).
        """
        record = (
            self.tenant_db.query(DatabaseBackup)
            .filter(DatabaseBackup.id == backup_id)
            .first()
        )
        if record is None:
            raise NotFoundError(message="Backup record not found.")
        if record.status not in ("SUCCESS", "COMPLETED"):
            raise BadRequestError(
                message=f"This backup is not downloadable (status: {record.status})."
            )
        if not record.s3_key:
            raise BadRequestError(message="No storage artifact is attached to this backup.")

        from app.services.aws_s3_service import S3Service

        with get_master_db_context() as master_db:
            tenant = master_db.query(Tenant).filter(Tenant.code == self.tenant_code).first()
            bucket_name = S3Service().ensure_tenant_bucket(master_db, tenant) or ""

        raw = S3Service().get_object_bytes(bucket_name, record.s3_key)
        if raw is None:
            raise BadRequestError(
                message="Could not retrieve the backup artifact from storage."
            )

        if record.is_encrypted:
            try:
                content = decrypt_bytes(raw)
            except InvalidToken as exc:
                logger.error("Backup %s could not be decrypted: %s", record.id, exc)
                raise BadRequestError(
                    message=(
                        "This backup could not be decrypted with the current platform "
                        "key. It may have been created under a different "
                        "DATABASE_ENCRYPTION_KEY."
                    )
                )
        else:
            content = raw

        # Present the restorable dump under its real name — never the .enc wrapper.
        download_name = record.file_name or f"backup_{self.tenant_code}.dump"
        if download_name.endswith(".enc"):
            download_name = download_name[: -len(".enc")]

        return {
            "filename": download_name,
            "content": content,
            "size_bytes": len(content),
            "media_type": "application/octet-stream",
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

    def restore_backup(
        self,
        backup_id: int,
        *,
        confirm_tenant_code: str,
        safety_backup: bool = True,
        drop_existing: bool = True,
    ) -> dict:
        """
        Restore this hospital's database from a completed backup.

        This OVERWRITES the live tenant database, so it is gated three ways:
        a dedicated BACKUP_RESTORE permission (enforced at the route), an
        explicit confirmation where the caller re-types the workspace code,
        and — by default — a fresh pre-restore safety snapshot so the current
        state is recoverable if the restore is a mistake. The physical restore
        decrypts the artifact, verifies its checksum, then applies it
        per-statement (``--exit-on-error``) so a large schema does not exhaust
        the server lock table; the safety snapshot is the recovery path if a
        restore aborts partway.
        """
        expected = (self.tenant_code or "").strip().upper()
        if (confirm_tenant_code or "").strip().upper() != expected:
            raise BadRequestError(
                message="Restore not confirmed: the workspace code you typed does not match this hospital."
            )

        record = (
            self.tenant_db.query(DatabaseBackup)
            .filter(DatabaseBackup.id == backup_id)
            .first()
        )
        if record is None:
            raise NotFoundError(message="Backup record not found.")
        if record.status not in ("SUCCESS", "COMPLETED"):
            raise BadRequestError(
                message=f"This backup is not restorable (status: {record.status})."
            )
        if not record.s3_key:
            raise BadRequestError(message="No storage artifact is attached to this backup.")

        # Snapshot the current state first so a mistaken restore is recoverable.
        safety_backup_id = None
        if safety_backup:
            try:
                snapshot = self.create_backup(triggered_by="PRE_RESTORE")
                safety_backup_id = snapshot.get("backup_id")
            except Exception as exc:  # noqa: BLE001 - surfaced to the operator
                logger.error(
                    "Pre-restore safety backup failed for %s: %s", self.tenant_code, exc
                )
                raise BadRequestError(
                    message=(
                        "Could not take a pre-restore safety snapshot, so the restore was "
                        "aborted. Resolve the storage/backup issue and retry, or disable the "
                        "safety snapshot to force the restore."
                    )
                )

        from app.services.aws_s3_service import S3Service

        with get_master_db_context() as master_db:
            tenant = master_db.query(Tenant).filter(Tenant.code == self.tenant_code).first()
            if not tenant:
                raise NotFoundError(message="Tenant not found.")
            db_url = decrypt_string(tenant.db_connection_string) if tenant.db_connection_string else ""
            bucket_name = S3Service().ensure_tenant_bucket(master_db, tenant) or ""

        if not db_url:
            raise BadRequestError(
                message="No database connection is configured for this hospital."
            )

        repo = DatabaseBackupRepository(self.tenant_db)
        started = datetime.now(timezone.utc)
        try:
            repo.run_physical_restore(
                record, db_url, bucket_name, drop_existing=drop_existing
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator
            logger.error("Restore failed for tenant %s: %s", self.tenant_code, exc)
            raise BadRequestError(message=f"Restore failed: {exc}")

        duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

        download_name = record.file_name or ""
        if download_name.endswith(".enc"):
            download_name = download_name[: -len(".enc")]

        logger.warning(
            "Tenant %s restored from backup %s (%s) in %sms (safety snapshot: %s).",
            self.tenant_code,
            record.id,
            download_name,
            duration_ms,
            safety_backup_id,
        )
        return {
            "success": True,
            "backup_id": record.id,
            "filename": download_name,
            "restored_at": datetime.now(timezone.utc),
            "duration_ms": duration_ms,
            "safety_backup_id": safety_backup_id,
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
