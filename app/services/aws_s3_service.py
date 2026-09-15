import hashlib
import os
import re
import secrets

import boto3
from botocore.config import Config
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
            region_name=settings.AWS_DEFAULT_REGION or "us-east-1",
            endpoint_url=settings.AWS_ENDPOINT_URL,
            # SigV4 is mandatory: botocore silently downgrades presigned URLs
            # to legacy SigV2 otherwise, which newer buckets reject with
            # "Please use AWS4-HMAC-SHA256" — images then never render.
            config=Config(signature_version="s3v4"),
        )
        self.region = settings.AWS_DEFAULT_REGION or "us-east-1"
        self.is_enabled = settings.S3_ENABLED
        #: Human-readable reason for the most recent failed operation.
        self.last_error: Optional[str] = None
        #: Cached deployment-scoped bucket-name suffix (see _account_suffix).
        self._account_suffix_cache: Optional[str] = None

    # S3 bucket names: 3-63 chars, lowercase letters/digits/hyphens, must
    # start and end alphanumeric. Reserve room for the "carepoint-hms-" prefix
    # (14), the "-<env>" segment and the "-<suffix>" segment.
    _BUCKET_PREFIX = "carepoint-hms-"

    @staticmethod
    def _slug(value: str) -> str:
        """Lowercase and reduce to the S3-legal character set."""
        slug = re.sub(r"[^a-z0-9-]+", "-", (value or "").lower())
        slug = re.sub(r"-{2,}", "-", slug).strip("-")
        return slug or "tenant"

    def _account_suffix(self) -> str:
        """A short, deployment-scoped suffix that makes tenant bucket names
        globally unique WITHOUT colliding with other AWS accounts.

        Derived (and cached) from the AWS account id via STS so it is stable
        across retries — critical for idempotency: re-provisioning the same
        tenant always resolves to the same bucket name. Falls back to a hash
        of the access key id, then to a fixed token, if STS is unavailable.
        """
        if self._account_suffix_cache:
            return self._account_suffix_cache
        seed = None
        try:
            sts = boto3.client(
                "sts",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID.get_secret_value() if settings.AWS_ACCESS_KEY_ID else None,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY.get_secret_value() if settings.AWS_SECRET_ACCESS_KEY else None,
                region_name=self.region,
                endpoint_url=settings.AWS_ENDPOINT_URL,
            )
            seed = sts.get_caller_identity().get("Account")
        except Exception as exc:  # STS not permitted / offline — fall back
            logger.info("STS get_caller_identity unavailable (%s); using key-derived bucket suffix.", exc)
        if not seed and settings.AWS_ACCESS_KEY_ID:
            seed = settings.AWS_ACCESS_KEY_ID.get_secret_value()
        seed = seed or "carepoint-hms"
        self._account_suffix_cache = hashlib.sha256(seed.encode()).hexdigest()[:8]
        return self._account_suffix_cache

    def _build_bucket_name(self, tenant_code: str, env: str, unique: str) -> str:
        """Assemble a legal bucket name, truncating the tenant slug so the
        whole name stays within the 63-character S3 limit."""
        tail = f"-{env}-{unique}"
        max_code = 63 - len(self._BUCKET_PREFIX) - len(tail)
        code = self._slug(tenant_code)[:max_code].strip("-") or "tenant"
        return f"{self._BUCKET_PREFIX}{code}{tail}"

    def _try_create_bucket(self, bucket_name: str) -> None:
        """Issue the raw create_bucket call for the active region."""
        if self.region == "us-east-1":
            self.s3_client.create_bucket(Bucket=bucket_name)
        else:
            self.s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": self.region},
            )

    def create_tenant_bucket(self, tenant_code: str) -> Optional[str]:
        """
        Provision an S3 bucket for a specific tenant.
        Returns the bucket name if successful, None otherwise.

        The name is ``carepoint-hms-<tenant>-<env>-<account-suffix>``. The
        account-scoped suffix guarantees global uniqueness across AWS accounts
        while staying stable across retries. In the rare event the name is
        still taken, we retry with random suffixes before giving up.
        """
        if not self.is_enabled:
            logger.info("S3 is disabled. Skipping bucket creation.")
            return None

        # S3 bucket names must be globally unique. Primary candidate uses the
        # deterministic account suffix; fallbacks use random tokens.
        env = "dev" if settings.is_development else "prod"
        candidates = [self._build_bucket_name(tenant_code, env, self._account_suffix())]
        for _ in range(3):
            candidates.append(
                self._build_bucket_name(tenant_code, env, secrets.token_hex(4))
            )

        last_taken: Optional[str] = None
        bucket_name = candidates[0]
        try:
            for idx, bucket_name in enumerate(candidates):
                try:
                    self._try_create_bucket(bucket_name)
                    logger.info(f"Successfully provisioned S3 bucket: {bucket_name}")
                    self.last_error = None
                    return bucket_name
                except ClientError as inner:
                    inner_code = (inner.response or {}).get("Error", {}).get("Code", "")
                    if inner_code == "BucketAlreadyOwnedByYou":
                        logger.info(f"S3 bucket {bucket_name} already owned by us — reusing.")
                        self.last_error = None
                        return bucket_name
                    if inner_code == "BucketAlreadyExists":
                        # Only the deterministic name is worth reporting; for the
                        # random fallbacks just keep trying the next candidate.
                        last_taken = bucket_name
                        logger.warning(
                            "S3 bucket name %s already taken by another account; "
                            "trying an alternative.", bucket_name,
                        )
                        continue
                    raise  # any other error: handle in the outer except
            # Exhausted all candidates on BucketAlreadyExists.
            self.last_error = (
                f"The bucket name '{last_taken or bucket_name}' is already taken by another "
                "AWS account (S3 names are global), and automatic alternatives were also "
                "unavailable. Set a distinct tenant code or configure a dedicated bucket."
            )
            logger.error(self.last_error)
            return None
        except ClientError as e:
            code = (e.response or {}).get("Error", {}).get("Code", "")
            message = (e.response or {}).get("Error", {}).get("Message", str(e))
            if code == "BucketAlreadyOwnedByYou":
                # Idempotent: the bucket exists in OUR account — that's success
                # (e.g. a previous attempt created it but persisting failed).
                logger.info(f"S3 bucket {bucket_name} already owned by us — reusing.")
                self.last_error = None
                return bucket_name
            if code == "BucketAlreadyExists":
                self.last_error = (
                    f"The bucket name '{bucket_name}' is already taken by another "
                    "AWS account (S3 names are global). Choose a different tenant code "
                    "or bucket naming scheme."
                )
            elif code in ("InvalidAccessKeyId", "SignatureDoesNotMatch"):
                self.last_error = (
                    f"AWS rejected the platform credentials ({code}). Check "
                    "AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY in the environment."
                )
            elif code == "AccessDenied":
                # IAM denies the CreateBucket ACTION before checking whether the
                # bucket exists — so probe for a manually-created bucket and
                # adopt it when it's reachable with these credentials.
                if self._bucket_usable(bucket_name):
                    logger.info(f"S3 bucket {bucket_name} exists and is accessible — adopting it.")
                    self.last_error = None
                    return bucket_name
                self.last_error = (
                    "AccessDenied — the platform IAM user lacks the s3:CreateBucket "
                    "permission. Either grant it, or create the bucket "
                    f"'{bucket_name}' manually in the AWS console AND allow this "
                    "IAM user object read/write on it, then retry."
                )
            else:
                self.last_error = f"{code or 'S3 error'}: {message}"
            logger.error(f"Failed to create S3 bucket {bucket_name}: {e}")
            return None
        except Exception as e:  # network/endpoint problems
            self.last_error = f"Could not reach S3: {e}"
            logger.error(f"Failed to create S3 bucket {bucket_name}: {e}")
            return None

    def ensure_tenant_bucket(self, master_db, tenant) -> Optional[str]:
        """
        Return the tenant's bucket, provisioning + persisting it on demand.

        Central policy: every tenant stores uploads in its OWN bucket; the
        platform (SaaS) bucket from the environment is never used for tenant
        data. Tenants created before bucket provisioning existed self-heal
        here on first upload.
        """
        if tenant is None:
            return None
        if tenant.aws_s3_bucket_name:
            return tenant.aws_s3_bucket_name
        if not self.is_enabled:
            return None
        bucket_name = self.create_tenant_bucket(tenant.code)
        if bucket_name:
            try:
                tenant.aws_s3_bucket_name = bucket_name
                master_db.add(tenant)
                master_db.commit()
                logger.info("Provisioned + persisted bucket %s for tenant %s", bucket_name, tenant.code)
            except Exception as exc:  # pragma: no cover - defensive
                master_db.rollback()
                logger.error("Bucket %s created but could not be persisted for %s: %s",
                             bucket_name, tenant.code, exc)
        return bucket_name

    def _bucket_usable(self, bucket_name: str) -> bool:
        """True when the bucket exists and these credentials can use it."""
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            return True
        except Exception:
            return False

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
                ExtraArgs={'ContentType': file_obj.content_type or "application/octet-stream"}
            )
            
            # Construct the public URL
            if settings.AWS_ENDPOINT_URL:
                # Local/MinIO format
                base_url = settings.AWS_ENDPOINT_URL.rstrip('/')
                url = f"{base_url}/{bucket_name}/{s3_key}"
            else:
                # Standard AWS S3 format
                url = f"https://{bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
                
            logger.info(f"Successfully uploaded file to Storage: {url}")
            return url
        except ClientError as e:
            code = (e.response or {}).get("Error", {}).get("Code", "")
            if code == "AccessDenied":
                self.last_error = (
                    f"AccessDenied — the platform IAM user lacks s3:PutObject on bucket '{bucket_name}'."
                )
            elif code in ("NoSuchBucket",):
                self.last_error = f"Bucket '{bucket_name}' does not exist. Re-provision the tenant's S3 bucket."
            else:
                self.last_error = f"{code or 'S3 error'}: {(e.response or {}).get('Error', {}).get('Message', str(e))}"
            logger.error(f"Failed to upload file to S3: {e}")
            raise RuntimeError(f"S3 upload failure: {self.last_error}")
        except Exception as e:
            self.last_error = f"Could not reach S3: {e}"
            logger.error(f"Failed to upload file to S3: {e}")
            raise RuntimeError(f"S3 upload failure: {self.last_error}")

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
