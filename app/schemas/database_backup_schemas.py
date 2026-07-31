"""
Carepoint HMS - Database Backup Schemas

This module defines the Pydantic models used for data validation and serialization 
within the tenant database backup system. It supports listing backups, providing 
dashboard summaries, and managing download metadata.

Design Goals:
- Strict typing for all backup metadata.
- Support for dashboard statistics (health, storage usage).
- Compatibility with SQLAlchemy ORM models via from_attributes=True.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class DatabaseBackupReadSchema(BaseModel):
    """
    Schema for reading database backup details.

    Includes comprehensive metadata for retention, integrity, and PITR support.

    NOTE: the ORM model (``DatabaseBackup``) predates this schema and uses
    different attribute names (``file_name``, ``format``, ``started_at``,
    ``completed_at``) and the status value ``SUCCESS`` instead of
    ``COMPLETED``. The validation aliases below bridge that gap so ORM rows
    serialize cleanly while the JSON contract exposed to the frontend
    (``filename``, ``pg_dump_format``, ``backup_started_at``,
    ``backup_finished_at``, ``COMPLETED``) stays unchanged.
    """
    id: int = Field(..., description="Unique identifier for the backup record")
    filename: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("filename", "file_name"),
        description="The name of the backup file stored in S3 or local storage",
    )
    s3_url: Optional[str] = Field(None, description="The full URL to the backup artifact")
    s3_key: Optional[str] = Field(None, description="The S3 bucket key for the artifact")
    size_bytes: Optional[int] = Field(None, description="Size of the backup artifact in bytes")
    status: str = Field("PENDING", description="Current status: PENDING, COMPLETED, FAILED, EXPIRED")
    storage_location: str = Field("LOCAL", description="Where the backup is stored: LOCAL, S3")
    error_message: Optional[str] = Field(None, description="Error details if the backup failed")

    # Encryption / integrity
    is_encrypted: bool = Field(False, description="Whether the artifact is encrypted at rest")
    encryption_algo: Optional[str] = Field(None, description="Algorithm used for encryption (e.g., FERNET_AES128)")
    checksum_sha256: Optional[str] = Field(None, description="SHA-256 checksum of the unencrypted file")

    # Backup taxonomy / PITR
    backup_type: str = Field("FULL", description="Type of backup: FULL, INCREMENTAL, WAL")
    pg_dump_format: str = Field(
        "custom",
        validation_alias=AliasChoices("pg_dump_format", "format"),
        description="Format used by pg_dump (custom is recommended)",
    )
    backup_started_at: Optional[datetime] = Field(
        None,
        validation_alias=AliasChoices("backup_started_at", "started_at"),
        description="Timestamp when the backup process started",
    )
    backup_finished_at: Optional[datetime] = Field(
        None,
        validation_alias=AliasChoices("backup_finished_at", "completed_at"),
        description="Timestamp when the backup process finished",
    )
    pitr_lsn: Optional[str] = Field(None, description="PostgreSQL LSN for point-in-time recovery")
    pitr_timestamp: Optional[datetime] = Field(None, description="PostgreSQL timestamp for point-in-time recovery")

    # Retention
    retention_until: Optional[datetime] = Field(None, description="Date when this backup is eligible for automatic deletion")
    triggered_by: str = Field("MANUAL", description="How the backup was triggered: MANUAL, SCHEDULED")

    date_created: datetime = Field(..., description="Record creation timestamp")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator(
        "status", "storage_location", "backup_type", "pg_dump_format", "triggered_by",
        mode="before",
    )
    @classmethod
    def _default_when_null(cls, value, info):
        """Legacy rows may hold NULLs where the schema expects a string."""
        if value is None:
            return {
                "status": "PENDING",
                "storage_location": "LOCAL",
                "backup_type": "FULL",
                "pg_dump_format": "custom",
                "triggered_by": "MANUAL",
            }[info.field_name]
        return value

    @field_validator("status")
    @classmethod
    def _normalize_status(cls, value: str) -> str:
        """The repository historically wrote ``SUCCESS``; the API contract is ``COMPLETED``."""
        return "COMPLETED" if str(value).upper() == "SUCCESS" else str(value).upper()


class BackupSummarySchema(BaseModel):
    """
    High-level summary statistics for the database backup dashboard.
    
    Used to drive the 'Health', 'Storage Usage', and 'Retention Policy' cards in the UI.
    """
    health_status: str = Field(..., description="Overall health: Healthy, Degraded, or Unhealthy")
    health_description: str = Field(..., description="Contextual message explaining the health status")
    last_backup_at: Optional[datetime] = Field(None, description="Timestamp of the most recent successful backup")
    next_backup_scheduled_at: Optional[datetime] = Field(None, description="Timestamp of the next automated backup")
    retention_policy: str = Field(..., description="Human-readable retention policy description")
    storage_usage_gb: float = Field(..., description="Total storage consumed by successful backups in Gigabytes")
    recovery_points_count: int = Field(..., description="Total number of valid recovery points available")


class BackupListResponseSchema(BaseModel):
    """
    Unified response model for the backups dashboard.
    
    Combines the global summary metrics with the historical list of recovery points.
    """
    summary: BackupSummarySchema = Field(..., description="Aggregated backup metrics")
    backups: List[DatabaseBackupReadSchema] = Field(..., description="History of recent backup attempts")


class BackupDownloadMetadataSchema(BaseModel):
    """
    Metadata for a backup artifact being prepared for download.
    
    Usually returned in headers or as part of a pre-signed URL response.
    """
    filename: str = Field(..., description="The filename of the decrypted artifact")
    size_bytes: int = Field(..., description="The size of the decrypted file")
    checksum_sha256: Optional[str] = Field(None, description="Integrity checksum for client-side verification")
