import os
import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile
from typing import Optional

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID.get_secret_value() if settings.AWS_ACCESS_KEY_ID else None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY.get_secret_value() if settings.AWS_SECRET_ACCESS_KEY else None,
            region_name=settings.AWS_DEFAULT_REGION or "us-east-1"
        )
        self.region = settings.AWS_DEFAULT_REGION or "us-east-1"
        self.is_enabled = settings.S3_ENABLED

    def create_tenant_bucket(self, tenant_code: str) -> Optional[str]:
        """
        Provision an S3 bucket for a specific tenant.
        Returns the bucket name if successful, None otherwise.
        """
        if not self.is_enabled:
            logger.info("S3 is disabled. Skipping bucket creation.")
            return None

        # S3 bucket names must be globally unique
        env = "dev" if settings.is_development else "prod"
        bucket_name = f"carepoint-hms-{tenant_code.lower()}-{env}"
        
        try:
            if self.region == "us-east-1":
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )
            
            # Optionally configure CORS or Bucket Policies here if needed
            logger.info(f"Successfully provisioned S3 bucket: {bucket_name}")
            return bucket_name
        except ClientError as e:
            logger.error(f"Failed to create S3 bucket {bucket_name}: {e}")
            return None

    def upload_file(self, bucket_name: str, file_obj: UploadFile, s3_key: str) -> str:
        """
        Upload a file to the tenant's bucket and return the URL.
        """
        if not self.is_enabled:
            raise RuntimeError("S3 storage is disabled but required for file uploads.")
            
        if not bucket_name:
            raise RuntimeError("S3 bucket name is missing. File storage requires a provisioned bucket.")
            
        try:
            # Reset file pointer to start just in case
            file_obj.file.seek(0)
            
            self.s3_client.upload_fileobj(
                file_obj.file, 
                bucket_name, 
                s3_key,
                ExtraArgs={'ContentType': file_obj.content_type}
            )
            
            # Construct the public URL
            url = f"https://{bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            logger.info(f"Successfully uploaded file to S3: {url}")
            return url
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise RuntimeError(f"S3 upload failure: {e}")

    def generate_presigned_url(self, bucket_name: str, s3_key: str, expires_in: int = 3600) -> Optional[str]:
        """
        Generates a presigned URL for secure temporary access to an S3 object.
        """
        if not self.is_enabled or not bucket_name:
            return None
            
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket_name, "Key": s3_key},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None
