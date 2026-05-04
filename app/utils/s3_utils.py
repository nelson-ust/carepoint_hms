
# utils/s3_utils.py
from __future__ import annotations

"""
AWS S3 utilities for Carepoint HMS.

Purpose
-------
This module centralizes AWS S3 operations for the application, including:

- uploading file-like objects
- uploading FastAPI UploadFile objects
- generating presigned URLs
- downloading files from S3
- deleting files from S3
- extracting object keys from S3 URLs
- building safe S3 object keys

Design goals
------------
- keep all S3 operations in one reusable module
- support private S3 storage with presigned retrieval URLs
- provide helpers for PDFs, images, and generic files
- return structured metadata useful for database persistence

Expected configuration
----------------------
This module expects the following settings:

- S3_ENABLED
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_DEFAULT_REGION
- AWS_S3_BUCKET_NAME
"""

import hashlib
import logging
import mimetypes
import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Iterable, Optional
from urllib.parse import urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import UploadFile

from .validators import validate_file_extension

try:
    from app.core.config import settings
except Exception:  # pragma: no cover
    settings = None


logger = logging.getLogger(__name__)

DEFAULT_PRESIGNED_EXPIRATION = 3600
DEFAULT_IMAGE_PRESIGNED_EXPIRATION = 86400
DEFAULT_S3_ACL = "private"


def _require_s3_config() -> None:
    """
    Ensure S3 configuration is available.

    Raises:
        RuntimeError: If S3 is disabled or configuration is incomplete.
    """
    if settings is None:
        raise RuntimeError("Application settings are unavailable.")

    if not getattr(settings, "S3_ENABLED", False):
        raise RuntimeError("S3 storage is not enabled.")

    required_values = [
        getattr(settings, "AWS_ACCESS_KEY_ID", None),
        getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
        getattr(settings, "AWS_DEFAULT_REGION", None),
        getattr(settings, "AWS_S3_BUCKET_NAME", None),
    ]
    if not all(required_values):
        raise RuntimeError("AWS S3 configuration is incomplete.")


def _resolve_secret(value):
    """
    Resolve a possibly secret-wrapped config value into a plain string.
    """
    if value is None:
        return None
    if hasattr(value, "get_secret_value"):
        return value.get_secret_value()
    return value


def get_s3_client():
    """
    Create and return a boto3 S3 client.
    """
    _require_s3_config()

    return boto3.client(
        "s3",
        aws_access_key_id=_resolve_secret(settings.AWS_ACCESS_KEY_ID),
        aws_secret_access_key=_resolve_secret(settings.AWS_SECRET_ACCESS_KEY),
        region_name=settings.AWS_DEFAULT_REGION,
    )


def get_bucket_name() -> str:
    """
    Return the configured S3 bucket name.
    """
    _require_s3_config()
    return settings.AWS_S3_BUCKET_NAME


def sanitize_filename(filename: str) -> str:
    """
    Return a safe filename for S3 object naming.
    """
    filename = os.path.basename(filename).strip().replace(" ", "_")
    return "".join(ch for ch in filename if ch.isalnum() or ch in {"-", "_", "."})


def build_s3_object_key(
    *,
    folder: str,
    filename: str,
    prefix: Optional[str] = None,
    include_timestamp: bool = True,
) -> str:
    """
    Build a safe S3 object key.

    Example:
        reports/invoices/invoice_20260412_143000.pdf
    """
    safe_name = sanitize_filename(filename)
    stem = Path(safe_name).stem
    suffix = Path(safe_name).suffix

    name_parts: list[str] = []
    if prefix:
        name_parts.append(prefix.strip())

    name_parts.append(stem)

    if include_timestamp:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        name_parts.append(timestamp)

    final_name = "_".join(part for part in name_parts if part) + suffix
    folder = folder.strip("/").replace("\\", "/")
    return f"{folder}/{final_name}" if folder else final_name


def infer_content_type(filename: str, explicit_content_type: Optional[str] = None) -> str:
    """
    Resolve the MIME type for a file.
    """
    if explicit_content_type:
        return explicit_content_type

    content_type, _ = mimetypes.guess_type(filename)
    return content_type or "application/octet-stream"


def calculate_bytes_checksum(data: bytes, algorithm: str = "sha256") -> str:
    """
    Calculate a checksum from raw bytes.
    """
    hasher = hashlib.new(algorithm)
    hasher.update(data)
    return hasher.hexdigest()


def calculate_file_checksum(path: str | Path, algorithm: str = "sha256") -> str:
    """
    Calculate a checksum from a local file.
    """
    hasher = hashlib.new(algorithm)
    with open(path, "rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_s3_object_url(object_name: str, bucket_name: Optional[str] = None) -> str:
    """
    Build the canonical S3 object URL.

    Note:
        This is not the same as a presigned URL.
    """
    bucket = bucket_name or get_bucket_name()
    region = settings.AWS_DEFAULT_REGION
    return f"https://{bucket}.s3.{region}.amazonaws.com/{object_name}"


def upload_file_to_s3(
    file_obj: BinaryIO,
    bucket_name: str,
    object_name: str,
    *,
    content_type: Optional[str] = None,
    metadata: Optional[dict[str, str]] = None,
    acl: str = DEFAULT_S3_ACL,
) -> str:
    """
    Upload a file-like object to S3 and return the canonical S3 URL.

    Args:
        file_obj: File-like object opened in binary mode.
        bucket_name: S3 bucket name.
        object_name: Target S3 key.
        content_type: Optional MIME type.
        metadata: Optional object metadata.
        acl: S3 ACL.

    Returns:
        str: Canonical S3 object URL.
    """
    client = get_s3_client()

    extra_args = {
        "Metadata": metadata or {},
    }

    if content_type:
        extra_args["ContentType"] = content_type

    if acl:
        extra_args["ACL"] = acl

    try:
        client.upload_fileobj(file_obj, bucket_name, object_name, ExtraArgs=extra_args)
        return get_s3_object_url(object_name, bucket_name=bucket_name)
    except ClientError as exc:
        logger.error("Failed to upload file to S3: %s", exc)
        raise
    except BotoCoreError as exc:
        logger.error("BotoCore upload failure: %s", exc)
        raise


async def upload_uploadfile_to_s3(
    upload_file: UploadFile,
    *,
    folder: str,
    allowed_extensions: Optional[Iterable[str]] = None,
    prefix: Optional[str] = None,
    metadata: Optional[dict[str, str]] = None,
    generate_presigned_url_after_upload: bool = False,
    expiration: int = DEFAULT_PRESIGNED_EXPIRATION,
) -> dict[str, str | int | None]:
    """
    Upload a FastAPI UploadFile directly to S3.

    Returns:
        dict containing:
        - file_name
        - file_key
        - file_size
        - checksum
        - content_type
        - file_url
        - presigned_url
        - bucket_name
    """
    if allowed_extensions and not validate_file_extension(upload_file.filename, allowed_extensions):
        raise ValueError("Uploaded file type is not allowed.")

    bucket_name = get_bucket_name()
    original_name = sanitize_filename(upload_file.filename or "uploaded_file")
    object_name = build_s3_object_key(
        folder=folder,
        filename=original_name,
        prefix=prefix,
        include_timestamp=True,
    )

    file_bytes = await upload_file.read()
    content_type = infer_content_type(original_name, upload_file.content_type)
    checksum = calculate_bytes_checksum(file_bytes)
    file_size = len(file_bytes)

    file_url = upload_file_to_s3(
        BytesIO(file_bytes),
        bucket_name=bucket_name,
        object_name=object_name,
        content_type=content_type,
        metadata=metadata,
    )

    presigned_url = None
    if generate_presigned_url_after_upload:
        presigned_url = generate_presigned_url_file(
            object_name=object_name,
            expiration=expiration,
        )

    return {
        "bucket_name": bucket_name,
        "file_name": original_name,
        "file_key": object_name,
        "file_size": file_size,
        "checksum": checksum,
        "content_type": content_type,
        "file_url": file_url,
        "presigned_url": presigned_url,
        "storage_provider": "aws_s3",
    }


def upload_bytes_to_s3(
    *,
    data: bytes,
    object_name: str,
    file_name: str,
    bucket_name: Optional[str] = None,
    content_type: Optional[str] = None,
    metadata: Optional[dict[str, str]] = None,
    acl: str = DEFAULT_S3_ACL,
) -> dict[str, str | int]:
    """
    Upload raw bytes to S3 and return structured metadata.
    """
    bucket = bucket_name or get_bucket_name()
    resolved_content_type = infer_content_type(file_name, content_type)
    checksum = calculate_bytes_checksum(data)
    file_size = len(data)

    file_url = upload_file_to_s3(
        BytesIO(data),
        bucket_name=bucket,
        object_name=object_name,
        content_type=resolved_content_type,
        metadata=metadata,
        acl=acl,
    )

    return {
        "bucket_name": bucket,
        "file_name": sanitize_filename(file_name),
        "file_key": object_name,
        "file_size": file_size,
        "checksum": checksum,
        "content_type": resolved_content_type,
        "file_url": file_url,
        "storage_provider": "aws_s3",
    }


def generate_presigned_url_pdf(object_name: str, expiration: int = DEFAULT_PRESIGNED_EXPIRATION) -> str:
    """
    Generate a presigned download URL for a PDF file.

    The response is configured as an attachment so the PDF is downloaded.
    """
    client = get_s3_client()
    bucket_name = get_bucket_name()

    try:
        return client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": bucket_name,
                "Key": object_name,
                "ResponseContentDisposition": "attachment",
                "ResponseContentType": "application/pdf",
            },
            ExpiresIn=expiration,
        )
    except ClientError as exc:
        logger.error("Failed to generate presigned PDF URL: %s", exc)
        raise
    except BotoCoreError as exc:
        logger.error("BotoCore presigned PDF URL failure: %s", exc)
        raise


def generate_presigned_url_image(object_name: str, expiration: int = DEFAULT_IMAGE_PRESIGNED_EXPIRATION) -> str:
    """
    Generate a presigned inline URL for an image file.

    The response is configured as inline so it can render in the browser.
    """
    client = get_s3_client()
    bucket_name = get_bucket_name()

    content_type = infer_content_type(object_name)
    try:
        return client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": bucket_name,
                "Key": object_name,
                "ResponseContentDisposition": "inline",
                "ResponseContentType": content_type,
            },
            ExpiresIn=expiration,
        )
    except ClientError as exc:
        logger.error("Failed to generate presigned image URL: %s", exc)
        raise
    except BotoCoreError as exc:
        logger.error("BotoCore presigned image URL failure: %s", exc)
        raise


def generate_presigned_url_file(
    object_name: str,
    expiration: int = DEFAULT_PRESIGNED_EXPIRATION,
    response_content_disposition: str = "attachment",
    response_content_type: Optional[str] = None,
) -> str:
    """
    Generate a generic presigned URL for a file.

    Args:
        object_name: S3 object key.
        expiration: Expiry in seconds.
        response_content_disposition: Usually 'attachment' or 'inline'.
        response_content_type: Optional MIME type override.

    Returns:
        str: Presigned URL.
    """
    client = get_s3_client()
    bucket_name = get_bucket_name()

    params = {
        "Bucket": bucket_name,
        "Key": object_name,
        "ResponseContentDisposition": response_content_disposition,
    }

    if response_content_type:
        params["ResponseContentType"] = response_content_type

    try:
        return client.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=expiration,
        )
    except ClientError as exc:
        logger.error("Failed to generate presigned file URL: %s", exc)
        raise
    except BotoCoreError as exc:
        logger.error("BotoCore presigned file URL failure: %s", exc)
        raise


def extract_s3_key(s3_url: str) -> str:
    """
    Extract the S3 object key from a full S3 URL.
    """
    parsed = urlparse(s3_url)
    return parsed.path.lstrip("/")


def download_file_from_s3(object_name: str, local_path: str) -> None:
    """
    Download an S3 object to a local file.

    Args:
        object_name: S3 object key.
        local_path: Local path where the file should be saved.
    """
    bucket_name = get_bucket_name()
    client = get_s3_client()

    try:
        client.download_file(Bucket=bucket_name, Key=object_name, Filename=local_path)
    except ClientError as exc:
        logger.error("Failed to download %s from S3: %s", object_name, exc)
        raise
    except BotoCoreError as exc:
        logger.error("BotoCore download failure for %s: %s", object_name, exc)
        raise


def delete_file_from_s3(object_name: str) -> bool:
    """
    Delete an object from S3.

    Args:
        object_name: S3 object key.

    Returns:
        bool: True if the delete request was successfully submitted.
    """
    bucket_name = get_bucket_name()
    client = get_s3_client()

    try:
        client.delete_object(Bucket=bucket_name, Key=object_name)
        return True
    except ClientError as exc:
        logger.error("Failed to delete %s from S3: %s", object_name, exc)
        raise
    except BotoCoreError as exc:
        logger.error("BotoCore delete failure for %s: %s", object_name, exc)
        raise