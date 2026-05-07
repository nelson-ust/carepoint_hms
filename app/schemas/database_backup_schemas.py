"""
Schemas for tenant database backups.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DatabaseBackupReadSchema(BaseModel):
    id: int
    filename: str
    s3_url: Optional[str] = None
    s3_key: Optional[str] = None
    size_bytes: Optional[int] = None
    status: str
    error_message: Optional[str] = None

    # Encryption / integrity
    is_encrypted: bool = False
    encryption_algo: Optional[str] = None
    checksum_sha256: Optional[str] = None

    # Backup taxonomy / PITR
    backup_type: str = "FULL"
    pg_dump_format: str = "custom"
    backup_started_at: Optional[datetime] = None
    backup_finished_at: Optional[datetime] = None
    pitr_lsn: Optional[str] = None
    pitr_timestamp: Optional[datetime] = None

    # Retention
    retention_until: Optional[datetime] = None
    triggered_by: str = "MANUAL"

    date_created: datetime

    model_config = ConfigDict(from_attributes=True)


class BackupDownloadMetadataSchema(BaseModel):
    """
    Metadata returned alongside the streamed backup file via response
    headers.  This schema documents the shape; the actual endpoint
    returns a binary ``FileResponse``.
    """
    filename: str
    size_bytes: int
    checksum_sha256: Optional[str] = None
