"""Unit tests for TenantLogService.

Covers daily-log generation (no-logs short-circuit, success path, S3
failure rollback), the simple list query, and presigned-URL generation.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.tenant_log_service import TenantLogService


def _fake_audit_log():
    """
    Build a stand-in for ``AuditLog`` whose ``created_at`` attribute can
    be compared (``>=``, ``<=``) with a real ``datetime`` without raising.

    The service code is real SQLAlchemy and references
    ``AuditLog.created_at`` which is a Python ``@property`` (returns
    ``self.date_created``). At the class level this property doesn't
    behave like a column, so unmodified comparison would crash. We mock
    the whole symbol and explicitly wire up __ge__/__le__ on the
    ``created_at`` child so the where-clause construction succeeds.
    """
    fake = MagicMock(name="AuditLog")
    fake.created_at.__ge__ = lambda self, other: MagicMock()
    fake.created_at.__le__ = lambda self, other: MagicMock()
    return fake


def _make_svc():
    db = MagicMock()
    with patch("app.services.tenant_log_service.S3Service") as s3_cls:
        s3 = MagicMock()
        s3_cls.return_value = s3
        svc = TenantLogService(db, "ACME")
    return svc, db, s3


class TestGenerateDailyLog:
    # The service constructs ``select(AuditLog).where(AuditLog.created_at >= ...)``,
    # but ``created_at`` on the model is a Python ``@property`` (not a SQLAlchemy
    # column) — so the comparison raises at *call-time*, not when SQL runs. We
    # patch ``select``/``and_`` (and the AuditLog symbol) so the where-clause
    # construction is short-circuited to a MagicMock.
    @patch("app.services.tenant_log_service.and_", new=lambda *a, **kw: MagicMock())
    @patch("app.services.tenant_log_service.select", new=lambda *a, **kw: MagicMock())
    @patch("app.services.tenant_log_service.AuditLog", new=_fake_audit_log())
    def test_returns_none_when_no_logs(self):
        svc, db, s3 = _make_svc()
        db.execute.return_value.scalars.return_value.all.return_value = []
        out = svc.generate_daily_log(date(2025, 1, 1))
        assert out is None
        db.add.assert_not_called()

    @patch("app.services.tenant_log_service.os.path.exists", return_value=False)
    @patch("app.services.tenant_log_service.os.path.getsize", return_value=1234)
    @patch("app.services.tenant_log_service.tempfile.NamedTemporaryFile")
    @patch("app.services.tenant_log_service.and_", new=lambda *a, **kw: MagicMock())
    @patch("app.services.tenant_log_service.select", new=lambda *a, **kw: MagicMock())
    @patch("app.services.tenant_log_service.AuditLog", new=_fake_audit_log())
    def test_success_path_uploads_and_records(self, mock_tmp, mock_size, mock_exists):
        svc, db, s3 = _make_svc()
        log = SimpleNamespace(
            id=1,
            actor_user_id=2,
            action="X",
            entity_name="Patient",
            entity_id=99,
            created_at=SimpleNamespace(isoformat=lambda: "T"),
            before_data=None,
            after_data=None,
            extra_metadata=None,
            request_id="r",
            ip_address="1.1.1.1",
        )
        db.execute.return_value.scalars.return_value.all.return_value = [log]
        tmp_handle = MagicMock()
        tmp_handle.name = "/tmp/x.json"
        mock_tmp.return_value.__enter__.return_value = tmp_handle
        s3.s3_client.upload_fileobj = MagicMock()
        with patch("builtins.open", new=MagicMock()):
            tenant_log = svc.generate_daily_log(date(2025, 1, 5))
        assert tenant_log is not None
        db.add.assert_called_once()
        added = db.add.call_args[0][0]
        assert added.file_size_bytes == 1234
        assert added.status == "COMPLETED"
        assert added.filename.startswith("logs_ACME_2025-01-05")
        s3.s3_client.upload_fileobj.assert_called_once()

    @patch("app.services.tenant_log_service.os.path.exists", return_value=False)
    @patch("app.services.tenant_log_service.tempfile.NamedTemporaryFile")
    @patch("app.services.tenant_log_service.and_", new=lambda *a, **kw: MagicMock())
    @patch("app.services.tenant_log_service.select", new=lambda *a, **kw: MagicMock())
    @patch("app.services.tenant_log_service.AuditLog", new=_fake_audit_log())
    def test_s3_failure_rolls_back(self, mock_tmp, mock_exists):
        svc, db, s3 = _make_svc()
        log = SimpleNamespace(
            id=1,
            actor_user_id=2,
            action="X",
            entity_name="Patient",
            entity_id=99,
            created_at=None,
            before_data=None,
            after_data=None,
            extra_metadata=None,
            request_id=None,
            ip_address=None,
        )
        db.execute.return_value.scalars.return_value.all.return_value = [log]
        tmp_handle = MagicMock()
        tmp_handle.name = "/tmp/y.json"
        mock_tmp.return_value.__enter__.return_value = tmp_handle
        s3.s3_client.upload_fileobj.side_effect = RuntimeError("boom")
        # An S3 upload failure now rolls back AND re-raises to signal failure to
        # the caller, rather than swallowing the error and returning None.
        with patch("builtins.open", new=MagicMock()):
            with pytest.raises(RuntimeError, match="boom"):
                svc.generate_daily_log(date(2025, 1, 5))
        db.rollback.assert_called_once()


class TestGetLogs:
    def test_returns_ordered_list(self):
        svc, db, _ = _make_svc()
        db.execute.return_value.scalars.return_value.all.return_value = ["a", "b"]
        assert svc.get_logs() == ["a", "b"]


class TestGetDownloadUrl:
    def test_returns_none_when_missing(self):
        svc, db, s3 = _make_svc()
        db.get.return_value = None
        assert svc.get_download_url(1) is None

    def test_returns_presigned_url(self):
        svc, db, s3 = _make_svc()
        rec = SimpleNamespace(id=1, s3_key="k")
        db.get.return_value = rec
        # The bucket is now resolved via the tenant's provisioned bucket
        # (S3Service.ensure_tenant_bucket) rather than a hard-coded name.
        s3.ensure_tenant_bucket.return_value = "carepoint-hms-acme-dev"
        s3.generate_presigned_url.return_value = "https://signed"
        assert svc.get_download_url(1) == "https://signed"
        s3.generate_presigned_url.assert_called_once_with(
            "carepoint-hms-acme-dev", "k"
        )


class TestConstruction:
    def test_holds_session_and_tenant(self):
        svc, db, s3 = _make_svc()
        assert svc.db is db
        assert svc.tenant_code == "ACME"
        assert svc.s3_service is s3
