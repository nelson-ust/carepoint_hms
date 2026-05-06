"""Unit tests for DatabaseBackupService.

External dependencies (subprocess.run, S3Service, decrypt_string,
get_master_db_context, tempfile and os.path) are all patched so the
tests never touch a real database, network or filesystem.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.services.database_backup_service import DatabaseBackupService


def _make_svc(tenant_code="ACME"):
    db = MagicMock()
    return DatabaseBackupService(db, tenant_code), db


class TestGetBackups:
    def test_lists_ordered(self):
        svc, db = _make_svc()
        db.query.return_value.order_by.return_value.all.return_value = ["b1", "b2"]
        assert svc.get_backups() == ["b1", "b2"]


class TestGetBackupById:
    def test_returns_record(self):
        svc, db = _make_svc()
        rec = SimpleNamespace(id=1)
        db.query.return_value.filter.return_value.first.return_value = rec
        assert svc.get_backup_by_id(1) is rec

    def test_raises_when_missing(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundError, match="Backup record not found"):
            svc.get_backup_by_id(99)


class TestTriggerBackup:
    @patch("app.services.database_backup_service.get_master_db_context")
    def test_raises_when_tenant_missing(self, mock_ctx):
        svc, db = _make_svc()
        master = MagicMock()
        mock_ctx.return_value.__enter__.return_value = master
        master.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundError, match="Tenant not found"):
            svc.trigger_backup()

    @patch("app.services.database_backup_service.os.remove")
    @patch("app.services.database_backup_service.os.path.exists", return_value=False)
    @patch("app.services.database_backup_service.os.path.getsize", return_value=4096)
    @patch("app.services.database_backup_service.tempfile.gettempdir", return_value="/tmp")
    @patch("app.services.database_backup_service.S3Service")
    @patch("app.services.database_backup_service.subprocess.run")
    @patch("app.services.database_backup_service.decrypt_string",
           return_value="postgresql+psycopg2://u:p@h/db")
    @patch("app.services.database_backup_service.get_master_db_context")
    def test_records_failed_status_when_pg_dump_fails(
        self, mock_ctx, mock_decrypt, mock_run, mock_s3_cls,
        mock_tempdir, mock_size, mock_exists, mock_remove
    ):
        svc, db = _make_svc()
        master = MagicMock()
        mock_ctx.return_value.__enter__.return_value = master
        tenant = SimpleNamespace(
            id=1,
            code="ACME",
            db_connection_string="ENC",
            aws_s3_bucket_name="bkt",
        )
        master.query.return_value.filter.return_value.first.return_value = tenant
        # pg_dump returns non-zero
        mock_run.return_value = SimpleNamespace(returncode=1, stderr="explosion")
        result = svc.trigger_backup()
        assert result.status == "FAILED"
        assert "explosion" in (result.error_message or "")
        # S3 never reached
        mock_s3_cls.return_value.s3_client.upload_fileobj.assert_not_called()

    @patch("app.services.database_backup_service.os.remove")
    @patch("app.services.database_backup_service.os.path.exists", return_value=True)
    @patch("app.services.database_backup_service.os.path.getsize", return_value=4096)
    @patch("app.services.database_backup_service.tempfile.gettempdir", return_value="/tmp")
    @patch("app.services.database_backup_service.S3Service")
    @patch("app.services.database_backup_service.subprocess.run")
    @patch("app.services.database_backup_service.decrypt_string",
           return_value="postgresql+psycopg2://u:p@h/db")
    @patch("app.services.database_backup_service.get_master_db_context")
    def test_happy_path_uploads_to_s3(
        self, mock_ctx, mock_decrypt, mock_run, mock_s3_cls,
        mock_tempdir, mock_size, mock_exists, mock_remove
    ):
        svc, db = _make_svc()
        master = MagicMock()
        mock_ctx.return_value.__enter__.return_value = master
        tenant = SimpleNamespace(
            id=1,
            code="ACME",
            db_connection_string="ENC",
            aws_s3_bucket_name="bkt",
        )
        master.query.return_value.filter.return_value.first.return_value = tenant
        mock_run.return_value = SimpleNamespace(returncode=0, stderr="")
        s3_inst = MagicMock()
        s3_inst.is_enabled = True
        s3_inst.region = "us-east-1"
        mock_s3_cls.return_value = s3_inst
        with patch("builtins.open", new=MagicMock()):
            result = svc.trigger_backup()
        assert result.status == "COMPLETED"
        assert result.size_bytes == 4096
        assert "https://bkt.s3.us-east-1.amazonaws.com/backups/" in result.s3_url
        s3_inst.s3_client.upload_fileobj.assert_called_once()

    @patch("app.services.database_backup_service.os.remove")
    @patch("app.services.database_backup_service.os.path.exists", return_value=True)
    @patch("app.services.database_backup_service.os.path.getsize", return_value=512)
    @patch("app.services.database_backup_service.tempfile.gettempdir", return_value="/tmp")
    @patch("app.services.database_backup_service.S3Service")
    @patch("app.services.database_backup_service.subprocess.run")
    @patch("app.services.database_backup_service.decrypt_string",
           return_value="postgresql+psycopg2://u:p@h/db")
    @patch("app.services.database_backup_service.get_master_db_context")
    def test_disabled_s3_uses_mocked_url(
        self, mock_ctx, mock_decrypt, mock_run, mock_s3_cls,
        mock_tempdir, mock_size, mock_exists, mock_remove
    ):
        svc, db = _make_svc()
        master = MagicMock()
        mock_ctx.return_value.__enter__.return_value = master
        tenant = SimpleNamespace(
            id=1,
            code="ACME",
            db_connection_string="ENC",
            aws_s3_bucket_name=None,
        )
        master.query.return_value.filter.return_value.first.return_value = tenant
        mock_run.return_value = SimpleNamespace(returncode=0, stderr="")
        s3_inst = MagicMock()
        s3_inst.is_enabled = False
        mock_s3_cls.return_value = s3_inst
        result = svc.trigger_backup()
        assert result.status == "COMPLETED"
        assert "mocked-s3-bucket" in result.s3_url
        s3_inst.s3_client.upload_fileobj.assert_not_called()


class TestRestoreBackup:
    @patch("app.services.database_backup_service.get_master_db_context")
    def test_rejects_non_completed_backup(self, mock_ctx):
        svc, db = _make_svc()
        backup = SimpleNamespace(id=1, status="FAILED", filename="x.dump")
        db.query.return_value.filter.return_value.first.return_value = backup
        with pytest.raises(BadRequestError, match="failed or pending"):
            svc.restore_backup(1)

    @patch("app.services.database_backup_service.os.remove")
    @patch("app.services.database_backup_service.os.path.exists", return_value=False)
    @patch("app.services.database_backup_service.tempfile.gettempdir", return_value="/tmp")
    @patch("app.services.database_backup_service.S3Service")
    @patch("app.services.database_backup_service.decrypt_string",
           return_value="postgresql+psycopg2://u:p@h/db")
    @patch("app.services.database_backup_service.get_master_db_context")
    def test_returns_simulated_when_s3_disabled_and_local_missing(
        self, mock_ctx, mock_decrypt, mock_s3_cls, mock_tempdir, mock_exists, mock_remove
    ):
        svc, db = _make_svc()
        backup = SimpleNamespace(id=1, status="COMPLETED", filename="x.dump")
        db.query.return_value.filter.return_value.first.return_value = backup
        master = MagicMock()
        mock_ctx.return_value.__enter__.return_value = master
        tenant = SimpleNamespace(
            id=1, code="ACME", db_connection_string="ENC", aws_s3_bucket_name="bkt"
        )
        master.query.return_value.filter.return_value.first.return_value = tenant
        s3_inst = MagicMock()
        s3_inst.is_enabled = False
        mock_s3_cls.return_value = s3_inst
        out = svc.restore_backup(1)
        assert out["success"] is True
        assert "simulated" in out["message"].lower()

    @patch("app.services.database_backup_service.os.remove")
    @patch("app.services.database_backup_service.os.path.exists", return_value=True)
    @patch("app.services.database_backup_service.tempfile.gettempdir", return_value="/tmp")
    @patch("app.services.database_backup_service.subprocess.run")
    @patch("app.services.database_backup_service.S3Service")
    @patch("app.services.database_backup_service.decrypt_string",
           return_value="postgresql+psycopg2://u:p@h/db")
    @patch("app.services.database_backup_service.get_master_db_context")
    def test_pg_restore_failure_raises_bad_request(
        self, mock_ctx, mock_decrypt, mock_s3_cls, mock_run,
        mock_tempdir, mock_exists, mock_remove
    ):
        svc, db = _make_svc()
        backup = SimpleNamespace(id=1, status="COMPLETED", filename="x.dump")
        db.query.return_value.filter.return_value.first.return_value = backup
        master = MagicMock()
        mock_ctx.return_value.__enter__.return_value = master
        tenant = SimpleNamespace(
            id=1, code="ACME", db_connection_string="ENC", aws_s3_bucket_name="bkt"
        )
        master.query.return_value.filter.return_value.first.return_value = tenant
        s3_inst = MagicMock()
        s3_inst.is_enabled = True
        mock_s3_cls.return_value = s3_inst
        mock_run.return_value = SimpleNamespace(returncode=1, stderr="boom")
        with pytest.raises(BadRequestError, match="Restore"):
            svc.restore_backup(1)

    @patch("app.services.database_backup_service.os.remove")
    @patch("app.services.database_backup_service.os.path.exists", return_value=True)
    @patch("app.services.database_backup_service.tempfile.gettempdir", return_value="/tmp")
    @patch("app.services.database_backup_service.subprocess.run")
    @patch("app.services.database_backup_service.S3Service")
    @patch("app.services.database_backup_service.decrypt_string",
           return_value="postgresql+psycopg2://u:p@h/db")
    @patch("app.services.database_backup_service.get_master_db_context")
    def test_happy_restore(
        self, mock_ctx, mock_decrypt, mock_s3_cls, mock_run,
        mock_tempdir, mock_exists, mock_remove
    ):
        svc, db = _make_svc()
        backup = SimpleNamespace(id=1, status="COMPLETED", filename="x.dump")
        db.query.return_value.filter.return_value.first.return_value = backup
        master = MagicMock()
        mock_ctx.return_value.__enter__.return_value = master
        tenant = SimpleNamespace(
            id=1, code="ACME", db_connection_string="ENC", aws_s3_bucket_name="bkt"
        )
        master.query.return_value.filter.return_value.first.return_value = tenant
        s3_inst = MagicMock()
        s3_inst.is_enabled = True
        mock_s3_cls.return_value = s3_inst
        mock_run.return_value = SimpleNamespace(returncode=0, stderr="")
        out = svc.restore_backup(1)
        assert out["success"] is True
        s3_inst.s3_client.download_file.assert_called_once()
