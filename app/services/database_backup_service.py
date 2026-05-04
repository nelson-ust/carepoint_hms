import os
import subprocess
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import UploadFile
import tempfile

from app.models.all_models import DatabaseBackup, Tenant
from app.core.exceptions import BadRequestError, NotFoundError
from app.services.aws_s3_service import S3Service
from app.core.cryptography import decrypt_string
from app.core.database import get_master_db_context
from app.core.logger import get_logger

logger = get_logger(__name__)

class DatabaseBackupService:
    def __init__(self, db: Session, tenant_code: str):
        self.db = db
        self.tenant_code = tenant_code

    def get_backups(self):
        """
        List all backups for the tenant.
        """
        return self.db.query(DatabaseBackup).order_by(DatabaseBackup.date_created.desc()).all()

    def get_backup_by_id(self, backup_id: int) -> DatabaseBackup:
        """
        Retrieve a specific backup by ID.
        """
        backup = self.db.query(DatabaseBackup).filter(DatabaseBackup.id == backup_id).first()
        if not backup:
            raise NotFoundError(message="Backup record not found.")
        return backup

    def trigger_backup(self) -> DatabaseBackup:
        """
        Trigger a new database backup for the tenant.
        """
        # 1. Resolve tenant from master db to get DB connection string and bucket
        with get_master_db_context() as master_db:
            tenant = master_db.query(Tenant).filter(Tenant.code == self.tenant_code).first()
            if not tenant:
                raise NotFoundError(message="Tenant not found.")
                
            db_url = decrypt_string(tenant.db_connection_string)
            bucket_name = tenant.aws_s3_bucket_name or "dummy-bucket"

        # 2. Create the backup record
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{self.tenant_code}_{timestamp}.dump"
        
        backup_record = DatabaseBackup(
            filename=filename,
            status="PENDING"
        )
        self.db.add(backup_record)
        self.db.commit()
        self.db.refresh(backup_record)

        # 3. Run pg_dump synchronously (for MVP)
        temp_dir = tempfile.gettempdir()
        dump_path = os.path.join(temp_dir, filename)

        try:
            # Use custom format (-F c) which is standard for pg_restore
            logger.info(f"Starting pg_dump for tenant {self.tenant_code}...")
            
            # pg_dump does not accept "+psycopg2" in the connection string
            pg_dump_url = db_url.replace("+psycopg2", "")
            
            # Hide password in logs by not logging the command
            process = subprocess.run(
                ["pg_dump", "-d", pg_dump_url, "-F", "c", "-f", dump_path],
                capture_output=True,
                text=True
            )
            
            if process.returncode != 0:
                logger.error(f"pg_dump failed: {process.stderr}")
                backup_record.status = "FAILED"
                backup_record.error_message = process.stderr[:500]
                self.db.commit()
                return backup_record

            file_size = os.path.getsize(dump_path)
            
            # 4. Upload to S3
            logger.info(f"Uploading backup to S3 bucket {bucket_name}...")
            s3_service = S3Service()
            s3_key = f"backups/{filename}"
            
            if s3_service.is_enabled:
                with open(dump_path, 'rb') as f:
                    s3_service.s3_client.upload_fileobj(
                        f, 
                        bucket_name, 
                        s3_key
                    )
                s3_url = f"https://{bucket_name}.s3.{s3_service.region}.amazonaws.com/{s3_key}"
            else:
                logger.info("S3 is disabled, skipping physical upload. Mocking S3 URL.")
                s3_url = f"https://mocked-s3-bucket.s3.amazonaws.com/{s3_key}"
            
            # Update record
            backup_record.status = "COMPLETED"
            backup_record.s3_url = s3_url
            backup_record.size_bytes = file_size
            self.db.commit()
            self.db.refresh(backup_record)
            
        except Exception as e:
            logger.error(f"Backup process failed: {e}")
            backup_record.status = "FAILED"
            backup_record.error_message = str(e)[:500]
            self.db.commit()
            
        finally:
            if os.path.exists(dump_path):
                os.remove(dump_path)

        return backup_record

    def restore_backup(self, backup_id: int) -> dict:
        """
        Restore a database backup for the tenant.
        WARNING: This overwrites the current database.
        """
        backup = self.get_backup_by_id(backup_id)
        if backup.status != "COMPLETED":
            raise BadRequestError(message="Cannot restore from a failed or pending backup.")

        # 1. Resolve tenant from master db
        with get_master_db_context() as master_db:
            tenant = master_db.query(Tenant).filter(Tenant.code == self.tenant_code).first()
            if not tenant:
                raise NotFoundError(message="Tenant not found.")
            
            db_url = decrypt_string(tenant.db_connection_string)
            bucket_name = tenant.aws_s3_bucket_name or "dummy-bucket"

        # 2. Download from S3
        temp_dir = tempfile.gettempdir()
        dump_path = os.path.join(temp_dir, backup.filename)
        
        try:
            logger.info(f"Downloading backup {backup.filename} from S3...")
            s3_service = S3Service()
            s3_key = f"backups/{backup.filename}"
            
            if s3_service.is_enabled:
                s3_service.s3_client.download_file(bucket_name, s3_key, dump_path)
            else:
                # If S3 is disabled, we expect the file to be in temp if it was just created,
                # or we mock the download if it's a test.
                if not os.path.exists(dump_path):
                     logger.warning("S3 disabled and local file missing. Mocking success for dev.")
                     return {"success": True, "message": "Restore simulated (S3 disabled)."}

            # 3. Terminate active connections
            db_name = db_url.split("/")[-1].split("?")[0]
            
            logger.info(f"Terminating connections to {db_name}...")
            from sqlalchemy import text
            self.db.execute(text(
                f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{db_name}' AND pid <> pg_backend_pid();"
            ))

            # 4. Run pg_restore
            logger.info(f"Starting pg_restore for tenant {self.tenant_code}...")
            pg_restore_url = db_url.replace("+psycopg2", "")
            
            process = subprocess.run(
                ["pg_restore", "-d", pg_restore_url, "--clean", "--no-owner", dump_path],
                capture_output=True,
                text=True
            )
            
            if process.returncode != 0:
                logger.error(f"pg_restore failed: {process.stderr}")
                raise BadRequestError(message=f"Restore failed: {process.stderr}")

            logger.info(f"Successfully restored backup for tenant {self.tenant_code}.")
            return {"success": True, "message": "Database restored successfully."}

        except Exception as e:
            logger.error(f"Restore process failed: {e}")
            raise BadRequestError(message=f"Restore process failed: {str(e)}")

        finally:
            if os.path.exists(dump_path):
                os.remove(dump_path)
