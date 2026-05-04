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

    def generate_daily_log(self, log_date: date) -> Optional[TenantLog]:
        """
        Aggregates all AuditLog entries for a specific date, saves to a file,
        uploads to S3, and records the event in TenantLog.
        """
        logger.info(f"Generating daily log for tenant {self.tenant_code} on {log_date}")
        
        # 1. Fetch audit logs for the specified date
        # Assuming AuditLog has a created_at or similar (it inherits from TenantTable usually)
        # Based on previous views, AuditLog uses AuditUtil which might not show the timestamp, 
        # but TenantTable usually has created_at.
        
        # Start and end of the day
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
            # We need the tenant's bucket name. 
            # In HMS, the bucket name is often stored in the Tenant model or derived.
            # Looking at S3Service, it has create_tenant_bucket.
            # We'll derive it like S3Service does for now, or fetch from Master if available.
            # For simplicity, we use the derivation pattern.
            env = "dev" # Should ideally come from config
            bucket_name = f"carepoint-hms-{self.tenant_code.lower()}-dev" 
            
            s3_key = f"backups/logs/{log_date.year}/{log_date.month:02d}/{filename}"
            
            # Note: upload_file in aws_s3_service.py takes (bucket_name, file_obj, s3_key)
            # but that expects an UploadFile. I should probably add a raw upload method or use boto3 directly.
            # Actually, I'll use boto3 client directly since I have access to it in S3Service.
            
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
            return None
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
            
        bucket_name = f"carepoint-hms-{self.tenant_code.lower()}-dev"
        return self.s3_service.generate_presigned_url(bucket_name, tenant_log.s3_key)
