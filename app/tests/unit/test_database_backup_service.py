"""Unit tests for TenantBackupService and the backup read schemas.

These cover the ORM ↔ schema field-name bridge (``file_name`` → ``filename``,
``format`` → ``pg_dump_format``, ``started_at``/``completed_at`` →
``backup_started_at``/``backup_finished_at``) and the ``SUCCESS`` →
``COMPLETED`` status normalization that the dashboard endpoint relies on.

External dependencies are patched — no database, network, or filesystem.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.database_backup_schemas import (
    BackupListResponseSchema,
    DatabaseBackupReadSchema,
)
from app.services.tenant_backup_service import TenantBackupService


NOW = datetime(2026, 7, 16, 10, 0, tzinfo=timezone.utc)


def _orm_row(**overrides):
    """Build an object shaped like the real ``DatabaseBackup`` ORM model."""
    base = dict(
        id=1,
        file_name="backup_ACME_20260716_100000.dump.enc",
        s3_url="https://bucket.s3.eu-west-1.amazonaws.com/backups/x.enc",
        s3_key="backups/x.enc",
        size_bytes=1024 * 1024,
        status="SUCCESS",
        storage_location="S3",
        error_message=None,
        is_encrypted=True,
        encryption_algo="FERNET_AES128",
        checksum_sha256="ab" * 32,
        format="custom",
        schema_only=False,
        retention_days=30,
        note=None,
        started_at=NOW,
        completed_at=NOW + timedelta(minutes=1),
        duration_ms=60_000,
        backup_type="FULL",
        triggered_by="MANUAL",
        retention_until=NOW + timedelta(days=30),
        date_created=NOW,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestDatabaseBackupReadSchema:
    def test_maps_orm_attribute_names(self):
        m = DatabaseBackupReadSchema.model_validate(_orm_row(), from_attributes=True)
        assert m.filename == "backup_ACME_20260716_100000.dump.enc"
        assert m.pg_dump_format == "custom"
        assert m.backup_started_at == NOW
        assert m.backup_finished_at == NOW + timedelta(minutes=1)

    def test_normalizes_success_to_completed(self):
        m = DatabaseBackupReadSchema.model_validate(_orm_row(status="SUCCESS"), from_attributes=True)
        assert m.status == "COMPLETED"

    def test_accepts_api_field_names(self):
        m = DatabaseBackupReadSchema.model_validate(
            {"id": 3, "filename": "b.dump", "status": "COMPLETED", "date_created": NOW}
        )
        assert m.filename == "b.dump"
        assert m.status == "COMPLETED"

    def test_tolerates_null_legacy_columns(self):
        row = _orm_row(
            file_name=None, status=None, storage_location=None,
            backup_type=None, format=None, triggered_by=None,
        )
        m = DatabaseBackupReadSchema.model_validate(row, from_attributes=True)
        assert m.filename is None
        assert m.status == "PENDING"
        assert m.storage_location == "LOCAL"
        assert m.backup_type == "FULL"
        assert m.pg_dump_format == "custom"
        assert m.triggered_by == "MANUAL"


class TestGetBackupDashboardData:
    def _svc(self):
        return TenantBackupService(MagicMock(), tenant_code="ACME")

    def test_counts_success_rows_as_recovery_points(self):
        rows = [
            _orm_row(id=2, status="SUCCESS", size_bytes=2 * 1024**3, completed_at=NOW),
            _orm_row(id=1, status="FAILED", size_bytes=None),
        ]
        with patch(
            "app.services.tenant_backup_service.DatabaseBackupRepository"
        ) as repo_cls:
            repo_cls.return_value.get_all.return_value = rows
            data = self._svc().get_backup_dashboard_data()

        assert data["summary"]["recovery_points_count"] == 1
        assert data["summary"]["storage_usage_gb"] == 2.0
        assert data["summary"]["last_backup_at"] == NOW
        assert data["summary"]["health_status"] == "Degraded"

    def test_serializes_end_to_end(self):
        rows = [_orm_row()]
        with patch(
            "app.services.tenant_backup_service.DatabaseBackupRepository"
        ) as repo_cls:
            repo_cls.return_value.get_all.return_value = rows
            data = self._svc().get_backup_dashboard_data()

        # This is exactly what the /backups/dashboard response_model does.
        envelope = BackupListResponseSchema.model_validate(data, from_attributes=True)
        assert envelope.backups[0].filename == rows[0].file_name
        assert envelope.backups[0].status == "COMPLETED"

    def test_degrades_gracefully_when_query_fails(self):
        with patch(
            "app.services.tenant_backup_service.DatabaseBackupRepository"
        ) as repo_cls:
            repo_cls.return_value.get_all.side_effect = RuntimeError("no table")
            data = self._svc().get_backup_dashboard_data()

        assert data["backups"] == []
        assert data["summary"]["health_status"] == "Unknown"


class TestGetDownloadLink:
    def test_accepts_success_status(self):
        svc = TenantBackupService(MagicMock(), tenant_code="ACME")
        record = _orm_row(status="SUCCESS")
        svc.tenant_db.query.return_value.filter.return_value.first.return_value = record

        tenant = SimpleNamespace(aws_s3_bucket_name="bucket")
        master_ctx = MagicMock()
        master_ctx.__enter__.return_value.query.return_value.filter.return_value.first.return_value = tenant

        with patch("app.services.tenant_backup_service.get_master_db_context", return_value=master_ctx), \
             patch("app.services.aws_s3_service.S3Service") as s3_cls:
            s3_cls.return_value.generate_presigned_url.return_value = "https://signed"
            out = svc.get_download_link(1)

        assert out["success"] is True
        assert out["filename"] == record.file_name

    def test_rejects_pending_status(self):
        from app.core.exceptions import BadRequestError

        svc = TenantBackupService(MagicMock(), tenant_code="ACME")
        svc.tenant_db.query.return_value.filter.return_value.first.return_value = _orm_row(status="PENDING")
        with pytest.raises(BadRequestError, match="not downloadable"):
            svc.get_download_link(1)
