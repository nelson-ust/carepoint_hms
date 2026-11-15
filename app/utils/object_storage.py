# app/utils/object_storage.py
from __future__ import annotations

"""
Connectivity-aware object-storage backend selection.

Policy (requested): **AWS S3 while online, local MinIO while offline.**

* Online  -> the cloud AWS S3 bucket (AWS_* settings).
* Offline -> the on-site MinIO server (MINIO_* settings), which is S3-compatible
  and runs on the hospital LAN, so uploads keep working with no internet.

Files written to MinIO while offline are recorded in a small local journal
(:func:`record_pending`) and copied up to AWS S3 when connectivity returns
(:func:`drain_pending_to_cloud`), so nothing written offline is lost once the
hospital is back online.

Every uploader already goes through ``s3_utils`` / ``S3Service``; both build
their boto3 client here, so the backend switch is centralised in one place.
"""

import json
import logging
import os
import threading
from typing import Any, Optional

import boto3
from botocore.config import Config

from app.core.config import settings

logger = logging.getLogger(__name__)

_FAST_FAIL = Config(
    signature_version="s3v4",
    connect_timeout=3,
    read_timeout=10,
    retries={"max_attempts": 2, "mode": "standard"},
    s3={"addressing_style": "path"},  # MinIO needs path-style addressing.
)

_journal_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Secret helpers
# ---------------------------------------------------------------------------

def _secret(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "get_secret_value"):
        return value.get_secret_value()
    return str(value)


def _minio_configured() -> bool:
    return bool(getattr(settings, "MINIO_ENDPOINT_URL", None))


def _aws_configured() -> bool:
    return bool(_secret(getattr(settings, "AWS_ACCESS_KEY_ID", None)))


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

def active_backend() -> str:
    """Return the storage backend to use right now: ``"s3"`` or ``"minio"``.

    Offline -> MinIO when it is configured. Online -> AWS S3 when it is
    configured. If only one backend is configured, that one is always used.
    """
    # Import here to avoid any import-time cycle.
    from app.services import connectivity_service
    from app.core import tenant_mode

    online = connectivity_service.is_online()
    backend = tenant_mode.storage_backend_for(tenant_mode.current_mode(), online)
    # Fall back if the chosen backend is not configured on this install.
    if backend == "minio" and not _minio_configured():
        return "s3"
    if backend == "s3" and not _aws_configured() and _minio_configured():
        return "minio"
    return backend


def _client_kwargs(backend: str) -> dict:
    if backend == "minio":
        return {
            "aws_access_key_id": _secret(getattr(settings, "MINIO_ACCESS_KEY_ID", None)),
            "aws_secret_access_key": _secret(getattr(settings, "MINIO_SECRET_ACCESS_KEY", None)),
            "region_name": getattr(settings, "MINIO_REGION", None) or "us-east-1",
            "endpoint_url": getattr(settings, "MINIO_ENDPOINT_URL", None),
        }
    # AWS S3 (cloud). AWS_ENDPOINT_URL stays supported for self-managed S3.
    return {
        "aws_access_key_id": _secret(getattr(settings, "AWS_ACCESS_KEY_ID", None)),
        "aws_secret_access_key": _secret(getattr(settings, "AWS_SECRET_ACCESS_KEY", None)),
        "region_name": getattr(settings, "AWS_DEFAULT_REGION", None) or "us-east-1",
        "endpoint_url": getattr(settings, "AWS_ENDPOINT_URL", None),
    }


def make_client(backend: Optional[str] = None):
    """Build a boto3 S3 client for the active (or given) backend, with
    fast-fail timeouts so a dead endpoint never hangs a request."""
    backend = backend or active_backend()
    return boto3.client("s3", config=_FAST_FAIL, **_client_kwargs(backend))


def object_base_url(bucket: str, object_name: str, backend: Optional[str] = None) -> str:
    """Canonical (non-presigned) URL for an object on the active backend."""
    backend = backend or active_backend()
    kw = _client_kwargs(backend)
    endpoint = kw.get("endpoint_url")
    if endpoint:  # MinIO / self-managed S3 -> path-style URL
        return f"{endpoint.rstrip('/')}/{bucket}/{object_name}"
    region = kw.get("region_name") or "us-east-1"
    return f"https://{bucket}.s3.{region}.amazonaws.com/{object_name}"


# ---------------------------------------------------------------------------
# Offline -> cloud reconciliation journal
# ---------------------------------------------------------------------------

def _journal_path() -> str:
    from app.utils.storage import uploads_base_dir

    return os.path.join(uploads_base_dir(), ".object_sync_queue.jsonl")


def record_pending(bucket: str, object_name: str) -> None:
    """Note an object written to MinIO while offline so it can be pushed to the
    cloud later. Best-effort: never raises into the caller's write path."""
    try:
        line = json.dumps({"bucket": bucket, "key": object_name})
        with _journal_lock:
            with open(_journal_path(), "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception as exc:  # pragma: no cover - journal is best-effort
        logger.warning("Could not record pending object sync (%s/%s): %s", bucket, object_name, exc)


def drain_pending_to_cloud(max_items: int = 500) -> dict:
    """Copy objects written to MinIO while offline up to AWS S3. Safe to call
    anytime; a no-op when online storage isn't configured or the journal is
    empty. Returns ``{synced, remaining, errors}``."""
    from app.services import connectivity_service

    if not connectivity_service.is_online() or not _aws_configured() or not _minio_configured():
        return {"synced": 0, "remaining": 0, "errors": 0, "skipped": True}

    path = _journal_path()
    if not os.path.exists(path):
        return {"synced": 0, "remaining": 0, "errors": 0}

    with _journal_lock:
        with open(path, "r", encoding="utf-8") as fh:
            lines = [ln.strip() for ln in fh if ln.strip()]

    minio = make_client("minio")
    s3 = make_client("s3")
    synced, errors, leftover = 0, 0, []
    for ln in lines[:max_items]:
        try:
            rec = json.loads(ln)
            bucket, key = rec["bucket"], rec["key"]
            obj = minio.get_object(Bucket=bucket, Key=key)
            body = obj["Body"].read()
            s3.put_object(Bucket=bucket, Key=key, Body=body,
                          ContentType=obj.get("ContentType", "application/octet-stream"))
            synced += 1
        except Exception as exc:  # keep for a later retry
            logger.warning("Object sync to cloud failed for %s: %s", ln, exc)
            errors += 1
            leftover.append(ln)
    leftover.extend(lines[max_items:])

    with _journal_lock:
        with open(path, "w", encoding="utf-8") as fh:
            for ln in leftover:
                fh.write(ln + "\n")

    return {"synced": synced, "remaining": len(leftover), "errors": errors}


def drain_pending_async() -> None:
    """Fire-and-forget reconciliation (used when connectivity is regained)."""
    def _run():
        try:
            result = drain_pending_to_cloud()
            if result.get("synced"):
                logger.info("Reconciled %s offline object(s) to cloud S3.", result["synced"])
        except Exception as exc:  # pragma: no cover
            logger.warning("Async object reconciliation failed: %s", exc)

    threading.Thread(target=_run, daemon=True).start()
