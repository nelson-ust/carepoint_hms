import json
import os
import tempfile
from datetime import date, datetime, timezone
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.models.all_models import AuditLog, TenantLog, Tenant
from app.services.aws_s3_service import S3Service

logger = get_logger(__name__)

class TenantLogService:
    def __init__(self, db: Session, tenant_code: str):
        self.db = db
        self.tenant_code = tenant_code
        self.s3_service = S3Service()

    def _get_tenant_bucket(self) -> str:
        """Fetch the bucket name for the current tenant from the Master DB."""
        from app.core.database import get_master_db_context
        from app.models.all_models import Tenant
        
        with get_master_db_context() as master_db:
            tenant = master_db.query(Tenant).filter(Tenant.code == self.tenant_code).first()
            # Tenant bucket only — provisioned on demand.
            bucket = self.s3_service.ensure_tenant_bucket(master_db, tenant)
            if not bucket:
                raise RuntimeError(f"S3 bucket not provisioned for tenant {self.tenant_code}")
            return bucket

    def generate_daily_log(self, log_date: date) -> Optional[TenantLog]:
        """
        Aggregates all AuditLog entries for a specific date, saves to a file,
        uploads to S3, and records the event in TenantLog.
        """
        logger.info(f"Generating daily log for tenant {self.tenant_code} on {log_date}")
        
        # 1. Fetch audit logs for the specified date
        start_dt = datetime.combine(log_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(log_date, datetime.max.time()).replace(tzinfo=timezone.utc)

        query = select(AuditLog).where(
            and_(
                AuditLog.created_at >= start_dt,
                AuditLog.created_at <= end_dt
            )
        )
        logs = self.db.execute(query).scalars().all()

        if not logs:
            logger.info(f"No logs found for tenant {self.tenant_code} on {log_date}")
            return None

        # 2. Format logs as JSON
        log_data = []
        for log in logs:
            log_data.append({
                "id": log.id,
                "actor_user_id": log.actor_user_id,
                "action": log.action,
                "entity_name": log.entity_name,
                "entity_id": log.entity_id,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "before_data": log.before_data,
                "after_data": log.after_data,
                "extra_metadata": log.extra_metadata,
                "request_id": log.request_id,
                "ip_address": log.ip_address
            })

        filename = f"logs_{self.tenant_code}_{log_date.isoformat()}.json"
        
        # 3. Write to temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tmp:
            json.dump(log_data, tmp, indent=2)
            tmp_path = tmp.name

        try:
            # 4. Upload to S3
            bucket_name = self._get_tenant_bucket()
            s3_key = f"backups/logs/{log_date.year}/{log_date.month:02d}/{filename}"
            
            if not self.s3_service.is_enabled:
                raise RuntimeError("S3 is disabled but required for log archiving.")
                
            with open(tmp_path, "rb") as f:
                self.s3_service.s3_client.upload_fileobj(f, bucket_name, s3_key)
            
            file_size = os.path.getsize(tmp_path)

            # 5. Record in TenantLog
            tenant_log = TenantLog(
                filename=filename,
                s3_key=s3_key,
                log_date=log_date,
                file_size_bytes=file_size,
                status="COMPLETED"
            )
            self.db.add(tenant_log)
            self.db.commit()
            self.db.refresh(tenant_log)
            
            logger.info(f"Successfully archived daily logs for {self.tenant_code} to S3: {s3_key}")
            return tenant_log

        except Exception as e:
            logger.error(f"Failed to archive logs for tenant {self.tenant_code}: {e}")
            self.db.rollback()
            raise # Re-raise to signal failure
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def get_logs(self) -> List[TenantLog]:
        """Returns list of archived logs for the tenant."""
        return self.db.execute(select(TenantLog).order_by(TenantLog.log_date.desc())).scalars().all()

    def get_download_url(self, log_id: int) -> Optional[str]:
        """Generates a presigned URL for a specific log archive."""
        tenant_log = self.db.get(TenantLog, log_id)
        if not tenant_log:
            return None
            
        bucket_name = self._get_tenant_bucket()
        return self.s3_service.generate_presigned_url(bucket_name, tenant_log.s3_key)
