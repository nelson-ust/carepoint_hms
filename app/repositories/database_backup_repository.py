# app/repositories/database_backup_repository.py
from __future__ import annotations

"""
app.repositories.database_backup_repository

Advanced repository for Database Backup orchestration.
Handles physical extraction (pg_dump), encryption, and S3 synchronization.
"""

import hashlib
import os
import re
import subprocess
import tempfile
import shutil
import urllib.parse as up
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Any

from sqlalchemy import desc, func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.cryptography import decrypt_string, encrypt_bytes
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logger import get_logger
from app.models.all_models import DatabaseBackup, MasterDatabaseBackup
from app.services.aws_s3_service import S3Service

logger = get_logger(__name__)


class DatabaseBackupRepository:
    """
    Repository for managing database backups (Tenant or Master).
    """

    def __init__(self, db: Session, model=DatabaseBackup):
        self.db = db
        self.model = model

    def get_all(self, limit: int = 100, skip: int = 0) -> List[Any]:
        """Retrieve paginated backup records."""
        query = self.db.query(self.model).filter(self.model.is_deleted.is_(False))
        return query.order_by(desc(self.model.date_created)).offset(skip).limit(limit).all()

    def create_pending_record(self, filename: str, triggered_by: str, retention_days: int) -> Any:
        backup = self.model(
            file_name=filename,
            status="PENDING",
            started_at=datetime.now(timezone.utc),
            retention_until=datetime.now(timezone.utc) + timedelta(days=retention_days),
            retention_days=retention_days,
            triggered_by=triggered_by,
        )
        self.db.add(backup)
        self.db.flush()
        return backup

    def update(self, backup: DatabaseBackup, update_data: dict) -> DatabaseBackup:
        for key, value in update_data.items():
            if hasattr(backup, key):
                setattr(backup, key, value)
        self.db.add(backup)
        self.db.flush()
        return backup

    def run_physical_backup(
        self, 
        record: Any, 
        db_url: str, 
        bucket_name: str,
        encrypt_at_rest: bool = True
    ) -> Any:
        """
        Executes the physical extraction and upload sequence.
        """
        # Use /tmp for better Docker mounting consistency on Mac/Linux
        temp_dir = Path("/tmp")
        if not temp_dir.exists():
            temp_dir = Path(tempfile.gettempdir())
            
        dump_path = temp_dir / record.file_name
        encrypted_path: Optional[Path] = None
        upload_path: Path = dump_path

        try:
            # 1. Run pg_dump (with robust version handling)
            self._execute_pg_dump(db_url, dump_path)
            
            # 2. Integrity and Size
            checksum = self._sha256_of_file(dump_path)
            update_data = {
                "size_bytes": dump_path.stat().st_size,
                "checksum_sha256": checksum
            }

            # 3. Encryption
            if encrypt_at_rest:
                encrypted_path = dump_path.with_suffix(dump_path.suffix + ".enc")
                self._encrypt_file(dump_path, encrypted_path)
                upload_path = encrypted_path
                update_data.update({
                    "is_encrypted": True,
                    "encryption_algo": "FERNET_AES128",
                    "size_bytes": encrypted_path.stat().st_size,
                    "s3_key": f"backups/{encrypted_path.name}",
                    "file_name": encrypted_path.name
                })
            else:
                update_data["s3_key"] = f"backups/{record.file_name}"

            # 4. Storage Upload
            s3_url = self._upload(upload_path, bucket_name, update_data.get("s3_key", record.s3_key))

            # 5. Finalize
            update_data.update({
                "s3_url": s3_url,
                "status": "SUCCESS",
                "completed_at": datetime.now(timezone.utc),
                "duration_ms": int((datetime.now(timezone.utc) - record.started_at).total_seconds() * 1000),
                "storage_location": "S3" if s3_url.startswith("http") else "LOCAL"
            })

            return self.update(record, update_data)

        except Exception as exc:
            logger.error(f"Physical backup failed for {record.file_name}: {exc}")
            self.update(record, {
                "status": "FAILED",
                "error_message": str(exc)[:1000],
                "completed_at": datetime.now(timezone.utc)
            })
            raise
        finally:
            # Local Cleanup
            for p in (dump_path, encrypted_path):
                if p and p.exists():
                    try: p.unlink()
                    except OSError: pass

    def purge_expired_backups(self, bucket_name: str) -> dict:
        now = datetime.now(timezone.utc)
        expired = self.db.query(self.model).filter(
            self.model.is_deleted.is_(False),
            self.model.retention_until < now
        ).all()

        s3 = S3Service()
        deleted_count = 0
        for b in expired:
            if b.s3_key and getattr(s3, "is_enabled", False):
                try:
                    s3.s3_client.delete_object(Bucket=bucket_name, Key=b.s3_key)
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete S3 object {b.s3_key}: {e}")
            
            b.status = "EXPIRED"
            b.soft_delete()
        
        self.db.flush()
        return {"expired_records": len(expired), "s3_objects_deleted": deleted_count}

    # ------------------------------------------------------------------
    # INFRASTRUCTURE HELPERS
    # ------------------------------------------------------------------

    def _execute_pg_dump(self, db_url: str, dump_path: Path) -> None:
        """Executes pg_dump with automatic Docker fallback."""
        # Clean URL for pg_dump
        cleaned_url = re.sub(r"\+psycopg2|\+asyncpg", "", db_url)
        
        # Try native execution first
        env = os.environ.copy()
        parsed = up.urlparse(cleaned_url)
        if parsed.password:
            env["PGPASSWORD"] = up.unquote(parsed.password)
        
        # Extract sslmode from query for PGSSLMODE env var
        if parsed.query:
            from urllib.parse import parse_qs
            q = parse_qs(parsed.query)
            sslmode = q.get("sslmode", [None])[0]
            if sslmode:
                env["PGSSLMODE"] = sslmode
        
        # 1. Resolve the best pg_dump binary to use
        pg_dump_path = self._resolve_pg_dump_path()
        cmd = [pg_dump_path, "-d", cleaned_url, "-F", "c", "-f", str(dump_path), "--no-owner", "--no-privileges"]
        
        try:
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if proc.returncode == 0:
                return
            
            error_msg = proc.stderr.lower()
            
            # Docker fallback logic (only if enabled and running)
            allow_docker = getattr(settings, "BACKUP_ALLOW_DOCKER", False)
            if allow_docker and self._is_docker_running():
                if "version mismatch" in error_msg or "pg_dump version" in error_msg:
                    version_match = re.search(r"server version: (\d+)", error_msg)
                    image_tag = version_match.group(1) if version_match else "latest"
                    logger.warning(f"pg_dump version mismatch. Falling back to Docker postgres:{image_tag}.")
                    self._run_via_docker("pg_dump", cleaned_url, dump_path, image_tag=image_tag)
                    return
                
            # If we reach here, native failed and Docker is either not allowed or not running
            raise RuntimeError(f"Native pg_dump failed: {proc.stderr[:500]}")

        except FileNotFoundError:
            if getattr(settings, "BACKUP_ALLOW_DOCKER", False) and self._is_docker_running():
                logger.warning("pg_dump not found on host. Attempting Docker fallback.")
                self._run_via_docker("pg_dump", cleaned_url, dump_path, image_tag="latest")
                return
            raise RuntimeError("pg_dump not found on host and Docker fallback is disabled or unavailable.")

    def _resolve_pg_dump_path(self) -> str:
        """
        Smart discovery of pg_dump. 
        Checks environment variable, then common version-specific paths, then system PATH.
        """
        # 1. Explicit override
        env_path = getattr(settings, "PG_DUMP_PATH", None) or os.getenv("CAREPOINT_HMS_PG_DUMP_PATH")
        if env_path:
            return env_path

        # 2. Common Homebrew/Linux/Postgres.app version-specific paths
        # Prioritizing version 16 to match DigitalOcean.
        search_versions = ["16", "15", "14"]
        path_templates = [
            "/opt/homebrew/opt/postgresql@{version}/bin/pg_dump",
            "/usr/local/opt/postgresql@{version}/bin/pg_dump",
            "/Applications/Postgres.app/Contents/Versions/{version}/bin/pg_dump",
            "/usr/lib/postgresql/{version}/bin/pg_dump",
            "/usr/bin/pg_dump", # Default
        ]
        
        for version in search_versions:
            for template in path_templates:
                path = template.format(version=version)
                if os.path.exists(path):
                    # Verify version if possible
                    try:
                        v_proc = subprocess.run([path, "--version"], capture_output=True, text=True)
                        if f" {version}." in v_proc.stdout:
                            logger.info(f"Found compatible pg_dump {version} at {path}")
                            return path
                    except Exception:
                        pass
                    
                    # Fallback to just using it if it exists
                    if os.path.exists(path):
                        return path

        # 3. Default to system PATH
        return "pg_dump"

    def _is_docker_running(self) -> bool:
        """Checks if Docker CLI is installed and the daemon is responsive."""
        if not shutil.which("docker"):
            return False
        try:
            subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=2)
            return True
        except Exception:
            return False

    def _run_via_docker(self, tool_name: str, db_url: str, dump_path: Path, image_tag: str = "latest") -> None:
        """Runs pg_dump inside a Docker container with host networking support."""
        if not shutil.which("docker"):
            raise RuntimeError("Docker is not installed but is required for version-safe backups.")

        # Handle localhost/127.0.0.1 for Docker containers
        docker_url = db_url
        if "localhost" in db_url or "127.0.0.1" in db_url:
            docker_url = db_url.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
            logger.info("Adjusted DB URL for Docker host networking (localhost -> host.docker.internal).")

        host_dir = str(dump_path.parent)
        container_file = f"/tmp/{dump_path.name}"
        
        parsed = up.urlparse(db_url)
        password = up.unquote(parsed.password) if parsed.password else ""

        cmd = [
            "docker", "run", "--rm",
            "-e", f"PGPASSWORD={password}",
            "-v", f"{host_dir}:/tmp",
            "--add-host=host.docker.internal:host-gateway",
            f"postgres:{image_tag}",
            tool_name, "-d", docker_url, "-F", "c", "-f", container_file, "--no-owner", "--no-privileges"
        ]
        
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Docker backup failed: {proc.stderr[:1000]}")

    @staticmethod
    def _sha256_of_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _encrypt_file(src: Path, dst: Path) -> None:
        from app.core.cryptography import encrypt_bytes
        dst.write_bytes(encrypt_bytes(src.read_bytes()))

    def _upload(self, src: Path, bucket: str, key: str) -> str:
        s3 = S3Service()
        if not getattr(s3, "is_enabled", False) or not bucket:
            logger.error("S3 storage is mandatory but S3 is disabled or bucket is missing.")
            raise RuntimeError("S3 storage is required for backups but is not configured.")
            
        try:
            with src.open("rb") as f:
                s3.s3_client.upload_fileobj(f, bucket, key)
            logger.info(f"Successfully uploaded backup to S3: s3://{bucket}/{key}")
            
            # Canonical S3 URL
            return f"https://{bucket}.s3.{s3.region}.amazonaws.com/{key}"
        except Exception as e:
            logger.error(f"S3 upload failed: {e}. Backup remains at {src.resolve()}")
            raise RuntimeError(f"Failed to upload backup to S3: {e}")
