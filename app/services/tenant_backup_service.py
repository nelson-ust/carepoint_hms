"""
Carepoint HMS - Tenant-Aware Backup and Restore Service

This service orchestrates the lifecycle of database backups for individual hospital 
tenants. It handles physical data extraction (pg_dump), encryption-at-rest, 
S3 synchronization, and restoration.

Core Features:
- Tenant Isolation: Backups are performed using tenant-specific connection strings.
- Encryption: Optional Fernet-AES128 encryption before storage.
- Integrity: SHA-256 checksums captured for every backup artifact.
- Dashboard Metrics: Aggregation of health and storage usage for UI consumption.
- Retention: Automatic rolling expiration of old recovery points.

Dependencies:
- PostgreSQL command-line tools (pg_dump, pg_restore).
- AWS S3 for regional redundant storage.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.cryptography import decrypt_string, encrypt_bytes, decrypt_bytes
from app.core.database import get_master_db_context
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logger import get_logger
from app.models.all_models import DatabaseBackup, Tenant
from app.services.aws_s3_service import S3Service
from app.repositories.database_backup_repository import DatabaseBackupRepository


logger = get_logger(__name__)


# Default retention period if not specified in settings.
DEFAULT_RETENTION_DAYS = 30


class TenantBackupService:
    """
    Service layer for database backup and disaster recovery operations.
    """

    def __init__(self, db: Session, tenant_code: str) -> None:
        """
        Initialize the service.
        
        Args:
            db (Session): Active tenant database session.
            tenant_code (str): The unique identifier for the tenant hospital.
        """
        self.db = db
        self.tenant_code = tenant_code
        self.repo = DatabaseBackupRepository(db)
        self.retention_days = int(getattr(settings, "BACKUP_RETENTION_DAYS", DEFAULT_RETENTION_DAYS))
        self.encrypt_at_rest = bool(getattr(settings, "BACKUP_ENCRYPT_AT_REST", True))

    # ------------------------------------------------------------------
    # DATA RETRIEVAL (READ)
    # ------------------------------------------------------------------

    def list_backups(self, *, limit: int = 100) -> list[DatabaseBackup]:
        """List current backups for the active tenant."""
        return self.repo.get_all(limit=limit)

    def get_backup_dashboard_data(self) -> dict:
        """
        Calculates and aggregates all data needed for the Backups dashboard UI.
        
        This includes health status based on recent success rates, total 
        storage consumption, and the list of available recovery points.
        
        Returns:
            dict: { summary: BackupSummarySchema, backups: List[DatabaseBackup] }
        """
        backups = self.list_backups(limit=50)
        
        # Aggregate storage metrics across all completed backups
        total_size_bytes = sum(b.size_bytes or 0 for b in backups if b.status == "COMPLETED")
        storage_usage_gb = round(total_size_bytes / (1024**3), 2)
        recovery_points_count = len([b for b in backups if b.status == "COMPLETED"])
        
        # Identify the most recent successful restore point
        last_backup = next((b for b in backups if b.status == "COMPLETED"), None)
        last_backup_at = last_backup.backup_finished_at if last_backup else None
        
        # Health Logic: Check the reliability of the last 5 backup attempts
        recent_backups = backups[:5]
        failed_count = len([b for b in recent_backups if b.status == "FAILED"])
        
        health_status = "Healthy"
        health_description = "Backups are encrypted and synchronized with S3 regional storage."
        
        if failed_count > 0:
            health_status = "Degraded"
            health_description = f"Warning: {failed_count} of the last {len(recent_backups)} backups failed."
        if failed_count >= 3:
            health_status = "Unhealthy"
            health_description = "Critical: Recent backup attempts are failing consistently. Manual intervention required."

        return {
            "summary": {
                "health_status": health_status,
                "health_description": health_description,
                "last_backup_at": last_backup_at,
                "next_backup_scheduled_at": None, # Dynamic scheduler calculation would go here
                "retention_policy": f"{self.retention_days} Days (Rolling)",
                "storage_usage_gb": storage_usage_gb,
                "recovery_points_count": recovery_points_count
            },
            "backups": backups
        }

    def get_backup(self, backup_id: int) -> DatabaseBackup:
        """Retrieve a backup by ID or raise a 404."""
        record = self.repo.get_by_id(backup_id)
        if not record:
            raise NotFoundError(message="Backup record not found.")
        return record

    def prepare_download_file(
        self,
        backup_id: int,
    ) -> dict:
        """
        Prepares a backup for client download.
        
        If the file is encrypted, it is transparently decrypted in a temporary 
        directory before being served. Returns metadata needed for streaming.
        """
        record = self.get_backup(backup_id)

        if record.status != "COMPLETED":
            raise BadRequestError(message="Cannot download a backup that has not completed successfully.")

        s3_key = record.s3_key
        if not s3_key:
            raise BadRequestError(message="No S3 storage key found for this backup.")

        _, _, bucket_name = self._resolve_tenant()

        # Temporary paths for processing
        temp_dir = tempfile.gettempdir()
        downloaded_path = Path(temp_dir) / f"dl_{record.id}_{record.filename}"
        cleanup_paths: list[Path] = [downloaded_path]

        # Fetch the artifact from storage
        s3 = S3Service()
        if getattr(s3, "is_enabled", False) and bucket_name:
            s3.s3_client.download_file(bucket_name, s3_key, str(downloaded_path))
        else:
            # Development fallback for local:// storage
            local_src = self._resolve_local_path(record)
            if local_src and local_src.exists():
                import shutil
                shutil.copy2(str(local_src), str(downloaded_path))
            else:
                raise BadRequestError(message="Backup artifact could not be retrieved from S3 or local storage.")

        if not downloaded_path.exists():
            raise BadRequestError(message="Backup artifact missing from target path.")

        # Handle transparent decryption
        serve_path = downloaded_path
        if record.is_encrypted:
            decrypted_path = Path(str(downloaded_path) + ".dec")
            self._decrypt_file(downloaded_path, decrypted_path)
            serve_path = decrypted_path
            cleanup_paths.append(decrypted_path)

        # Cleanup original name for the end-user
        download_filename = record.filename
        if download_filename.endswith(".enc"):
            download_filename = download_filename[:-4]

        return {
            "file_path": str(serve_path),
            "filename": download_filename,
            "size_bytes": serve_path.stat().st_size,
            "checksum_sha256": record.checksum_sha256,
            "media_type": "application/octet-stream",
            "cleanup_paths": [str(p) for p in cleanup_paths],
        }

    @staticmethod
    def _resolve_local_path(record) -> Optional[Path]:
        """Resolves local filesystem paths for non-S3 environments."""
        s3_url = record.s3_url or ""
        if s3_url.startswith("local://"):
            return Path(s3_url[len("local://"):])
        return None

    # ------------------------------------------------------------------
    # BACKUP CREATION (WRITE)
    # ------------------------------------------------------------------

    def create_backup(
        self,
        *,
        triggered_by: str = "MANUAL",
        retention_days: Optional[int] = None,
    ) -> DatabaseBackup:
        """
        Executes a full database dump, encrypts the output, and uploads to S3.
        
        This process runs synchronously for the request but updates the database 
        record state to reflect PENDING -> COMPLETED/FAILED.
        """
        retention = int(retention_days if retention_days is not None else self.retention_days)
        tenant, db_url, bucket_name = self._resolve_tenant()

        # Initialize record
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dump_filename = f"backup_{self.tenant_code}_{timestamp}.dump"
        
        record = self.repo.create({
            "filename": dump_filename,
            "s3_key": f"backups/{dump_filename}",
            "status": "PENDING",
            "backup_type": "FULL",
            "pg_dump_format": "custom",
            "backup_started_at": datetime.now(timezone.utc),
            "triggered_by": triggered_by,
            "retention_until": datetime.now(timezone.utc) + timedelta(days=retention),
            "is_encrypted": False,
        })

        temp_dir = tempfile.gettempdir()
        dump_path = Path(temp_dir) / dump_filename
        encrypted_path: Optional[Path] = None
        upload_path: Path = dump_path

        try:
            # 1. Run physical dump
            self._run_pg_dump(db_url, dump_path)
            
            # 2. Capture integrity checksum of raw dump
            checksum = self._sha256_of_file(dump_path)
            size_bytes = dump_path.stat().st_size
            
            update_data = {
                "size_bytes": size_bytes,
                "checksum_sha256": checksum
            }

            # 3. Encrypt at rest if configured
            if self.encrypt_at_rest:
                encrypted_path = Path(str(dump_path) + ".enc")
                self._encrypt_file(dump_path, encrypted_path)
                upload_path = encrypted_path
                update_data["is_encrypted"] = True
                update_data["encryption_algo"] = "FERNET_AES128"
                update_data["size_bytes"] = encrypted_path.stat().st_size
                update_data["s3_key"] = f"backups/{encrypted_path.name}"
                update_data["filename"] = encrypted_path.name

            # 4. Upload artifact to storage
            s3_url = self._upload(upload_path, bucket_name, update_data.get("s3_key", record.s3_key))

            # 5. Finalize record metadata
            update_data.update({
                "s3_url": s3_url,
                "status": "COMPLETED",
                "backup_finished_at": datetime.now(timezone.utc),
                "pitr_timestamp": datetime.now(timezone.utc),
                "pitr_lsn": self._capture_lsn()
            })

            self.repo.update(record, update_data)
            self._notify(event="backup.completed", subject="Backup Successful", body=f"Backup {record.filename} for tenant {self.tenant_code} has completed successfully.")
            
        except Exception as exc:
            # Update record to FAILED state on any error
            self.repo.update(record, {"status": "FAILED", "error_message": str(exc)[:500], "backup_finished_at": datetime.now(timezone.utc)})
            self._notify(event="backup.failed", subject="Backup Failed", body=f"Critical: Database backup for tenant {self.tenant_code} failed: {exc}")
            raise
        finally:
            # Cleanup local temp files unless S3 is disabled
            s3 = S3Service()
            s3_enabled = getattr(s3, "is_enabled", False)
            for path in (dump_path, encrypted_path):
                if path and path.exists() and (s3_enabled or path != upload_path):
                    try:
                        path.unlink()
                    except OSError: pass

        return record

    # ------------------------------------------------------------------
    # DISASTER RECOVERY (RESTORE)
    # ------------------------------------------------------------------

    def restore_backup(
        self,
        backup_id: int,
        *,
        target_timestamp: Optional[datetime] = None,
    ) -> dict:
        """
        Restores the tenant database from a backup artifact.
        
        WARNING: This is a destructive operation that terminates all active 
        connections and overwrites the current database.
        """
        record = self.get_backup(backup_id)
        if record.status != "COMPLETED":
            raise BadRequestError(message="Cannot restore from an incomplete or failed backup.")

        _, db_url, bucket_name = self._resolve_tenant()
        temp_dir = tempfile.gettempdir()
        downloaded = Path(temp_dir) / record.filename
        decrypted_path: Optional[Path] = None

        try:
            # 1. Download artifact
            self._download(record.s3_key or f"backups/{record.filename}", bucket_name, downloaded)
            restore_source = downloaded
            
            # 2. Transparently decrypt if needed
            if record.is_encrypted:
                decrypted_path = Path(str(downloaded) + ".dec")
                self._decrypt_file(downloaded, decrypted_path)
                restore_source = decrypted_path

            # 3. Terminate active sessions to allow clean restore
            self._terminate_active_connections(db_url)
            
            # 4. Execute pg_restore
            self._run_pg_restore(db_url, restore_source)

            return {"success": True, "message": f"Database successfully restored from recovery point: {record.filename}."}
        finally:
            for path in (downloaded, decrypted_path):
                if path and path.exists():
                    try:
                        path.unlink()
                    except OSError: pass

    # ------------------------------------------------------------------
    # MAINTENANCE (RETENTION)
    # ------------------------------------------------------------------

    def apply_retention(self) -> dict:
        """
        Sweeps the database for recovery points that have passed their retention date.
        
        Expired backups are soft-deleted from the database and their physical 
        artifacts are removed from S3.
        """
        now = datetime.now(timezone.utc)
        candidates = self.db.query(DatabaseBackup).filter(
            DatabaseBackup.is_deleted.is_(False),
            DatabaseBackup.retention_until.isnot(None),
            DatabaseBackup.retention_until < now
        ).all()

        if not candidates:
            return {"expired": 0, "deleted_objects": 0}

        _, _, bucket_name = self._resolve_tenant()
        s3 = S3Service()
        deleted_objects = 0
        for record in candidates:
            # Best-effort deletion of the S3 artifact
            if record.s3_key and getattr(s3, "is_enabled", False):
                try:
                    s3.s3_client.delete_object(Bucket=bucket_name, Key=record.s3_key)
                    deleted_objects += 1
                except Exception: pass
            
            # Metadata update
            record.status = "EXPIRED"
            record.soft_delete()

        self.db.commit()
        return {"expired": len(candidates), "deleted_objects": deleted_objects}

    # ------------------------------------------------------------------
    # INFRASTRUCTURE HELPERS (PRIVATE)
    # ------------------------------------------------------------------

    def _resolve_tenant(self) -> tuple[Tenant, str, str]:
        """Resolves tenant credentials and bucket from the Master Database."""
        with get_master_db_context() as master_db:
            tenant = master_db.query(Tenant).filter(Tenant.code == self.tenant_code).first()
            if not tenant:
                raise NotFoundError(message="Tenant configuration not found.")
            db_url = decrypt_string(tenant.db_connection_string) if tenant.db_connection_string else ""
            bucket = tenant.aws_s3_bucket_name or getattr(settings, "AWS_S3_BUCKET_NAME", None) or ""
            return tenant, db_url, bucket

    def _run_pg_dump(self, db_url: str, dump_path: Path) -> None:
        """Executes the pg_dump system command."""
        cleaned = db_url.replace("+psycopg2", "")
        tool_path = self._get_pg_tool_path("pg_dump")
        
        proc = subprocess.run([tool_path, "-d", cleaned, "-F", "c", "-f", str(dump_path)], capture_output=True, text=True)
        if proc.returncode != 0:
            msg = proc.stderr[:500]
            if "version mismatch" in msg:
                # Provide a more actionable error for version mismatch
                server_ver = self._get_server_version()
                local_ver = self._get_tool_version(tool_path)
                msg = (
                    f"PostgreSQL Version Mismatch detected.\n"
                    f"Server Version: {server_ver}\n"
                    f"Local Tool Version: {local_ver}\n"
                    f"Action: Please install PostgreSQL {server_ver} tools on this machine "
                    f"or update your PG_DUMP_PATH environment variable."
                )
            raise BadRequestError(message=f"pg_dump failed: {msg}")

    def _run_pg_restore(self, db_url: str, dump_path: Path) -> None:
        """Executes the pg_restore system command."""
        cleaned = db_url.replace("+psycopg2", "")
        tool_path = self._get_pg_tool_path("pg_restore")
        
        proc = subprocess.run([tool_path, "-d", cleaned, "--clean", "--if-exists", "--no-owner", str(dump_path)], capture_output=True, text=True)
        if proc.returncode != 0:
            raise BadRequestError(message=f"pg_restore failed: {proc.stderr[:500]}")

    def _get_pg_tool_path(self, tool_name: str) -> str:
        """
        Resolves the path to a PostgreSQL tool, checking environment variables
        and common system locations (Homebrew, Linux, Windows, etc.).
        """
        # 1. Check environment variables
        env_var = f"{tool_name.upper()}_PATH"
        custom_path = os.environ.get(env_var)
        if custom_path and os.path.exists(custom_path):
            return custom_path

        # 2. Universal Version Search (High to Low)
        versions = [str(v) for v in range(18, 9, -1)]
        
        search_roots = [
            "/opt/homebrew/opt",      # macOS Apple Silicon
            "/usr/local/opt",         # macOS Intel
            "/usr/lib/postgresql",    # Linux (Ubuntu/Debian)
            "/usr/pgsql-",            # RHEL/CentOS
            "C:\\Program Files\\PostgreSQL", # Windows
        ]

        for root in search_roots:
            for v in versions:
                candidates = [
                    Path(root) / f"postgresql@{v}" / "bin" / tool_name,
                    Path(root) / v / "bin" / tool_name,
                    Path(root + v) / "bin" / tool_name,
                    Path(root) / v / "bin" / f"{tool_name}.exe",
                ]
                for candidate in candidates:
                    if candidate.exists():
                        return str(candidate)

        # 3. Fallback to shutil.which (Standard PATH)
        found = shutil.which(tool_name)
        return found if found else tool_name

    def _get_server_version(self) -> str:
        """Fetch the PostgreSQL server version from the current connection."""
        try:
            res = self.db.execute(text("SHOW server_version")).first()
            return res[0] if res else "Unknown"
        except Exception:
            return "Unknown"

    def _get_tool_version(self, tool_path: str) -> str:
        """Fetch the version of a local PostgreSQL tool."""
        try:
            res = subprocess.run([tool_path, "--version"], capture_output=True, text=True)
            return res.stdout.strip() if res.returncode == 0 else "Unknown"
        except Exception:
            return "Unknown"

    def _terminate_active_connections(self, db_url: str) -> None:
        """Terminates active PostgreSQL sessions to the target database."""
        try:
            db_name = db_url.rsplit("/", 1)[-1].split("?")[0]
            self.db.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :db AND pid <> pg_backend_pid()"), {"db": db_name})
        except Exception: pass

    def _capture_lsn(self) -> Optional[str]:
        """Captures the current WAL LSN location for bookkeeping."""
        try:
            row = self.db.execute(text("SELECT pg_current_wal_lsn()")).first()
            return str(row[0]) if row else None
        except Exception: return None

    @staticmethod
    def _sha256_of_file(path: Path) -> str:
        """Calculates SHA-256 checksum for file integrity."""
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _encrypt_file(src: Path, dst: Path) -> None:
        """Encrypts a file using Fernet (AES128)."""
        dst.write_bytes(encrypt_bytes(src.read_bytes()))

    @staticmethod
    def _decrypt_file(src: Path, dst: Path) -> None:
        """Decrypts a file using Fernet (AES128)."""
        dst.write_bytes(decrypt_bytes(src.read_bytes()))

    def _upload(self, src: Path, bucket: str, key: str) -> str:
        """Uploads an artifact to S3 or logs local path if S3 is disabled."""
        s3 = S3Service()
        if not getattr(s3, "is_enabled", False):
            return f"local://{src.resolve()}"
        with src.open("rb") as f:
            s3.s3_client.upload_fileobj(f, bucket, key)
        region = getattr(s3, "region", None) or getattr(settings, "AWS_DEFAULT_REGION", "us-east-1")
        return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

    def _download(self, key: str, bucket: str, dst: Path) -> None:
        """Downloads an artifact from S3."""
        s3 = S3Service()
        if getattr(s3, "is_enabled", False):
            s3.s3_client.download_file(bucket, key, str(dst))

    def _notify(self, *, event: str, subject: str, body: str) -> None:
        """Dispatches email/in-app notifications to tenant administrators."""
        try:
            from app.models.all_models import User, UserRoleAssociation, Role
            from app.services.notification_dispatcher import NotificationDispatcher
            admins = self.db.query(User).join(UserRoleAssociation).join(Role).filter(Role.code.in_(["TENANT_ADMIN", "ADMIN"]), User.is_deleted.is_(False)).all()
            if admins:
                NotificationDispatcher(self.db).dispatch(event=event, recipients=admins, subject=subject, body=body)
        except Exception: pass
