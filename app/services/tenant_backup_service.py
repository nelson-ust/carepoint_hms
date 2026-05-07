"""
Tenant-aware backup and restore.

Capabilities
------------
* Full pg_dump per tenant database, isolated from every other tenant.
* Optional Fernet-AES encryption of the dump file before it leaves the host.
* Optional SHA-256 checksum captured for integrity verification.
* Configurable retention policy with automatic expiration sweep.
* Point-in-time-recovery friendly metadata fields (``pitr_lsn``,
  ``pitr_timestamp``) that pair with PostgreSQL's WAL archiving when
  configured at the cluster level.
* Best-effort notifications to tenant admins on success / failure.

The implementation deliberately tolerates missing optional dependencies (S3,
notification helpers) so it remains useful in development environments.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
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


logger = get_logger(__name__)


# Default retention horizon (override via settings.BACKUP_RETENTION_DAYS).
DEFAULT_RETENTION_DAYS = 30


class TenantBackupService:
    """
    Tenant-aware backup orchestration. Operates inside the active tenant's
    database so the resulting :class:`DatabaseBackup` row stays in tenant
    scope.

    Args
    ----
    db:
        A tenant-scoped :class:`Session`.
    tenant_code:
        Used to resolve the master-DB record for tenant connection string,
        S3 bucket name, and admin recipients.
    """

    def __init__(self, db: Session, tenant_code: str) -> None:
        self.db = db
        self.tenant_code = tenant_code
        self.retention_days = int(getattr(settings, "BACKUP_RETENTION_DAYS", DEFAULT_RETENTION_DAYS))
        self.encrypt_at_rest = bool(getattr(settings, "BACKUP_ENCRYPT_AT_REST", True))

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def list_backups(self, *, limit: int = 100) -> list[DatabaseBackup]:
        return (
            self.db.query(DatabaseBackup)
            .filter(DatabaseBackup.is_deleted.is_(False))
            .order_by(DatabaseBackup.date_created.desc())
            .limit(limit)
            .all()
        )

    def get_backup(self, backup_id: int) -> DatabaseBackup:
        record = (
            self.db.query(DatabaseBackup)
            .filter(
                DatabaseBackup.id == backup_id,
                DatabaseBackup.is_deleted.is_(False),
            )
            .first()
        )
        if not record:
            raise NotFoundError(message="Backup record not found.")
        return record

    def prepare_download_file(
        self,
        backup_id: int,
    ) -> dict:
        """
        Download a backup artifact from S3 (or local storage), decrypt it
        when encrypted, and return the path to the ready-to-serve
        **decrypted** file.

        The caller is responsible for deleting the temp files listed in
        ``cleanup_paths`` once the response has been streamed.
        """
        record = self.get_backup(backup_id)

        if record.status != "COMPLETED":
            raise BadRequestError(
                message="Cannot download a backup that has not completed successfully."
            )

        s3_key = record.s3_key
        if not s3_key:
            raise BadRequestError(
                message="No S3 storage key found for this backup."
            )

        _, _, bucket_name = self._resolve_tenant()

        temp_dir = tempfile.gettempdir()
        downloaded_path = Path(temp_dir) / f"dl_{record.id}_{record.filename}"
        cleanup_paths: list[Path] = [downloaded_path]

        # ── Retrieve the artifact ────────────────────────────────────
        s3 = S3Service()
        if getattr(s3, "is_enabled", False) and bucket_name:
            logger.info(
                "Downloading backup %s from S3 bucket=%s key=%s",
                record.id, bucket_name, s3_key,
            )
            s3.s3_client.download_file(bucket_name, s3_key, str(downloaded_path))
        else:
            # Dev fallback: the s3_url may carry a local:// path from
            # when the backup was created with S3 disabled.
            local_src = self._resolve_local_path(record)
            if local_src and local_src.exists():
                logger.info(
                    "S3 disabled — copying local artifact %s", local_src,
                )
                import shutil
                shutil.copy2(str(local_src), str(downloaded_path))
            else:
                raise BadRequestError(
                    message=(
                        "Backup artifact could not be retrieved. "
                        "S3 is disabled and no local copy exists."
                    ),
                )

        if not downloaded_path.exists():
            raise BadRequestError(
                message="Backup artifact could not be retrieved from storage."
            )

        logger.info(
            "Backup %s downloaded (%d bytes, is_encrypted=%s)",
            record.id, downloaded_path.stat().st_size, record.is_encrypted,
        )

        # ── Decrypt if the backup was encrypted at rest ──────────────
        serve_path = downloaded_path
        if record.is_encrypted:
            decrypted_path = Path(str(downloaded_path) + ".dec")
            logger.info("Decrypting backup %s -> %s", downloaded_path.name, decrypted_path.name)
            try:
                self._decrypt_file(downloaded_path, decrypted_path)
            except Exception as exc:
                logger.error("Decryption failed for backup %s: %s", record.id, exc)
                raise BadRequestError(
                    message=f"Failed to decrypt backup: {exc}"
                )
            serve_path = decrypted_path
            cleanup_paths.append(decrypted_path)
            logger.info(
                "Decrypted backup %s (%d bytes)",
                record.id, decrypted_path.stat().st_size,
            )

        # Derive a human-friendly download filename.  If the stored name
        # ends with ".enc" strip it so the admin gets a clean ".dump".
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
        """
        Extract a usable filesystem path from a ``local://`` s3_url
        stored when S3 was disabled during backup creation.
        """
        s3_url = record.s3_url or ""
        if s3_url.startswith("local://"):
            candidate = Path(s3_url[len("local://"):])
            return candidate
        return None

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def create_backup(
        self,
        *,
        triggered_by: str = "MANUAL",
        retention_days: Optional[int] = None,
    ) -> DatabaseBackup:
        """
        Run pg_dump against the tenant database, optionally encrypt the
        artifact, upload it to S3, and persist a metadata row.
        """
        retention = int(retention_days if retention_days is not None else self.retention_days)
        tenant, db_url, bucket_name = self._resolve_tenant()

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dump_filename = f"backup_{self.tenant_code}_{timestamp}.dump"
        s3_key = f"backups/{dump_filename}"

        record = DatabaseBackup(
            filename=dump_filename,
            s3_key=s3_key,
            status="PENDING",
            backup_type="FULL",
            pg_dump_format="custom",
            backup_started_at=datetime.now(timezone.utc),
            triggered_by=triggered_by,
            retention_until=datetime.now(timezone.utc) + timedelta(days=retention),
            is_encrypted=False,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        temp_dir = tempfile.gettempdir()
        dump_path = Path(temp_dir) / dump_filename
        encrypted_path: Optional[Path] = None
        upload_path: Path = dump_path  # default; updated if encryption runs

        try:
            self._run_pg_dump(db_url, dump_path)

            checksum = self._sha256_of_file(dump_path)
            size_bytes = dump_path.stat().st_size

            upload_path = dump_path
            upload_filename = dump_filename

            if self.encrypt_at_rest:
                encrypted_path = Path(str(dump_path) + ".enc")
                self._encrypt_file(dump_path, encrypted_path)
                upload_path = encrypted_path
                upload_filename = encrypted_path.name
                record.is_encrypted = True
                record.encryption_algo = "FERNET_AES128"
                size_bytes = encrypted_path.stat().st_size
                record.s3_key = f"backups/{upload_filename}"
                record.filename = upload_filename

            s3_url = self._upload(upload_path, bucket_name, record.s3_key)

            record.s3_url = s3_url
            record.size_bytes = size_bytes
            record.checksum_sha256 = checksum
            record.status = "COMPLETED"
            record.backup_finished_at = datetime.now(timezone.utc)
            record.pitr_timestamp = record.backup_finished_at
            record.pitr_lsn = self._capture_lsn()

            self.db.commit()
            self.db.refresh(record)

            self._notify(
                event="backup.completed",
                subject="Backup completed",
                body=(
                    f"Backup {record.filename} completed for tenant {self.tenant_code}. "
                    f"Size: {size_bytes} bytes."
                ),
            )
        except Exception as exc:
            record.status = "FAILED"
            record.error_message = str(exc)[:500]
            record.backup_finished_at = datetime.now(timezone.utc)
            self.db.commit()
            self._notify(
                event="backup.failed",
                subject="Backup failed",
                body=f"Backup for tenant {self.tenant_code} failed: {exc}",
            )
            raise
        finally:
            # When S3 is enabled the artifact lives in the bucket, so we
            # clean up all local temp files.  When S3 is *disabled* the
            # uploaded file (``upload_path``) is the only copy — we must
            # keep it so ``prepare_download_file`` can serve it later.
            s3 = S3Service()
            s3_enabled = getattr(s3, "is_enabled", False)

            for path in (dump_path, encrypted_path):
                if path is None or not path.exists():
                    continue
                # Keep the file that was "uploaded" locally when S3 is off.
                if not s3_enabled and path == upload_path:
                    continue
                try:
                    path.unlink()
                except OSError:
                    pass

        return record

    # ------------------------------------------------------------------
    # RESTORE
    # ------------------------------------------------------------------

    def restore_backup(
        self,
        backup_id: int,
        *,
        target_timestamp: Optional[datetime] = None,
    ) -> dict:
        """
        Restore a tenant database from a stored backup.

        ``target_timestamp`` is honored for PITR-style metadata only; full
        WAL replay requires the cluster to be configured with ``wal_level =
        replica`` and an archive command. The metadata is captured for
        observability in either case.
        """
        record = self.get_backup(backup_id)
        if record.status != "COMPLETED":
            raise BadRequestError(message="Cannot restore from a backup that did not complete.")

        tenant, db_url, bucket_name = self._resolve_tenant()

        temp_dir = tempfile.gettempdir()
        downloaded = Path(temp_dir) / record.filename
        decrypted_path: Optional[Path] = None

        try:
            self._download(record.s3_key or f"backups/{record.filename}", bucket_name, downloaded)

            if not downloaded.exists():
                raise BadRequestError(message="Backup artifact missing locally; download failed.")

            restore_source = downloaded
            if record.is_encrypted:
                decrypted_path = Path(str(downloaded) + ".dec")
                self._decrypt_file(downloaded, decrypted_path)
                restore_source = decrypted_path

            if record.checksum_sha256:
                actual = self._sha256_of_file(downloaded if not decrypted_path else decrypted_path)
                if record.is_encrypted:
                    # Checksum captured BEFORE encryption.
                    actual = self._sha256_of_file(decrypted_path)
                if actual != record.checksum_sha256:
                    raise BadRequestError(
                        message=(
                            "Backup integrity check failed: stored sha256 does not "
                            "match the downloaded artifact."
                        ),
                    )

            self._terminate_active_connections(db_url)
            self._run_pg_restore(db_url, restore_source)

            return {
                "success": True,
                "message": f"Database restored from backup {record.filename}.",
                "pitr_target": target_timestamp.isoformat() if target_timestamp else None,
            }
        finally:
            for path in (downloaded, decrypted_path):
                if path is not None and path.exists():
                    try:
                        path.unlink()
                    except OSError:
                        pass

    # ------------------------------------------------------------------
    # RETENTION
    # ------------------------------------------------------------------

    def apply_retention(self) -> dict:
        """
        Mark or hard-delete backups whose ``retention_until`` has elapsed.

        Storage objects in S3 are best-effort deleted; bookkeeping is
        always updated.
        """
        now = datetime.now(timezone.utc)
        candidates = (
            self.db.query(DatabaseBackup)
            .filter(
                DatabaseBackup.is_deleted.is_(False),
                DatabaseBackup.retention_until.isnot(None),
                DatabaseBackup.retention_until < now,
            )
            .all()
        )

        if not candidates:
            return {"expired": 0, "deleted_objects": 0}

        _, _, bucket_name = self._resolve_tenant()
        s3 = S3Service()

        deleted_objects = 0
        for record in candidates:
            if record.s3_key and getattr(s3, "is_enabled", False):
                try:
                    s3.s3_client.delete_object(Bucket=bucket_name, Key=record.s3_key)
                    deleted_objects += 1
                except Exception as exc:
                    logger.warning(
                        "Retention sweep: failed to delete %s/%s: %s",
                        bucket_name,
                        record.s3_key,
                        exc,
                    )
            record.status = "EXPIRED"
            record.soft_delete()

        self.db.commit()
        return {"expired": len(candidates), "deleted_objects": deleted_objects}

    # ------------------------------------------------------------------
    # INTERNAL: postgres
    # ------------------------------------------------------------------

    def _resolve_tenant(self) -> tuple[Tenant, str, str]:
        with get_master_db_context() as master_db:
            tenant = master_db.query(Tenant).filter(Tenant.code == self.tenant_code).first()
            if not tenant:
                raise NotFoundError(message="Tenant not found.")
            db_url = decrypt_string(tenant.db_connection_string) if tenant.db_connection_string else ""
            if not db_url:
                raise BadRequestError(message="Tenant database connection string is missing.")
            bucket = tenant.aws_s3_bucket_name or getattr(settings, "AWS_S3_BUCKET_NAME", None) or ""
            return tenant, db_url, bucket

    def _run_pg_dump(self, db_url: str, dump_path: Path) -> None:
        cleaned = db_url.replace("+psycopg2", "")
        logger.info("pg_dump start tenant=%s -> %s", self.tenant_code, dump_path.name)
        proc = subprocess.run(
            ["pg_dump", "-d", cleaned, "-F", "c", "-f", str(dump_path)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise BadRequestError(message=f"pg_dump failed: {proc.stderr[:500]}")

    def _run_pg_restore(self, db_url: str, dump_path: Path) -> None:
        cleaned = db_url.replace("+psycopg2", "")
        logger.info("pg_restore start tenant=%s <- %s", self.tenant_code, dump_path.name)
        proc = subprocess.run(
            [
                "pg_restore",
                "-d", cleaned,
                "--clean",
                "--if-exists",
                "--no-owner",
                str(dump_path),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise BadRequestError(message=f"pg_restore failed: {proc.stderr[:500]}")

    def _terminate_active_connections(self, db_url: str) -> None:
        """Terminate other backends connected to the target DB before restore."""
        try:
            db_name = db_url.rsplit("/", 1)[-1].split("?")[0]
            self.db.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :db AND pid <> pg_backend_pid()"
                ),
                {"db": db_name},
            )
        except Exception as exc:
            logger.warning("Could not terminate active connections: %s", exc)

    def _capture_lsn(self) -> Optional[str]:
        """
        Capture the current write-ahead-log location, useful for PITR
        bookkeeping. Falls back to ``None`` if the role lacks privileges.
        """
        try:
            row = self.db.execute(text("SELECT pg_current_wal_lsn()")).first()
            return str(row[0]) if row else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # INTERNAL: encryption + integrity
    # ------------------------------------------------------------------

    @staticmethod
    def _sha256_of_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _encrypt_file(src: Path, dst: Path) -> None:
        data = src.read_bytes()
        dst.write_bytes(encrypt_bytes(data))

    @staticmethod
    def _decrypt_file(src: Path, dst: Path) -> None:
        data = src.read_bytes()
        dst.write_bytes(decrypt_bytes(data))

    # ------------------------------------------------------------------
    # INTERNAL: storage
    # ------------------------------------------------------------------

    def _upload(self, src: Path, bucket: str, key: str) -> str:
        s3 = S3Service()
        if not getattr(s3, "is_enabled", False):
            return f"local://{src.resolve()}"
        with src.open("rb") as f:
            s3.s3_client.upload_fileobj(f, bucket, key)
        region = getattr(s3, "region", None) or getattr(settings, "AWS_DEFAULT_REGION", "us-east-1")
        return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

    def _download(self, key: str, bucket: str, dst: Path) -> None:
        s3 = S3Service()
        if not getattr(s3, "is_enabled", False):
            # In dev environments callers may have left a local copy.
            return
        s3.s3_client.download_file(bucket, key, str(dst))

    # ------------------------------------------------------------------
    # INTERNAL: notifications (best-effort)
    # ------------------------------------------------------------------

    def _notify(self, *, event: str, subject: str, body: str) -> None:
        try:
            from app.core.enums import NotificationEvent
            from app.models.all_models import User, UserRoleAssociation, Role
            from app.services.notification_dispatcher import NotificationDispatcher
        except Exception:
            return

        try:
            admins = (
                self.db.query(User)
                .join(UserRoleAssociation, UserRoleAssociation.user_id == User.id)
                .join(Role, Role.id == UserRoleAssociation.role_id)
                .filter(
                    Role.code.in_(["TENANT_ADMIN", "ADMIN"]),
                    User.is_deleted.is_(False),
                )
                .all()
            )
            if not admins:
                return
            dispatcher = NotificationDispatcher(self.db)
            dispatcher.dispatch(
                event=event,
                recipients=admins,
                subject=subject,
                body=body,
            )
        except Exception as exc:
            logger.warning("Backup notification dispatch skipped: %s", exc)
