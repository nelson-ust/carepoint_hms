"""Unit tests for TenantJobService.

Covers list / get / create / update / soft-delete of TenantScheduledJob,
plus the handler-validation guard and the schedule-required guard on
create.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.services.tenant_job_service import TenantJobService


def _make_svc():
    db = MagicMock()
    return TenantJobService(db), db


class TestListJobs:
    def test_returns_filtered_records(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = ["j1"]
        assert svc.list_jobs() == ["j1"]


class TestGetJob:
    def test_returns_record(self):
        svc, db = _make_svc()
        rec = SimpleNamespace(id=1)
        db.query.return_value.filter.return_value.first.return_value = rec
        assert svc.get_job(1) is rec

    def test_raises_when_missing(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundError, match="Scheduled job not found"):
            svc.get_job(99)


class TestCreateJob:
    @patch("app.services.tenant_job_service.get_handler", return_value=None)
    def test_rejects_unknown_handler(self, mock_get_handler):
        svc, db = _make_svc()
        with pytest.raises(BadRequestError, match="Unknown job handler"):
            svc.create_job(job_code="X", handler="missing", schedule_interval_minutes=5)

    @patch("app.services.tenant_job_service.get_handler", return_value=None)
    def test_rejects_empty_handler(self, mock_get_handler):
        svc, db = _make_svc()
        with pytest.raises(BadRequestError, match="Unknown job handler"):
            svc.create_job(job_code="X", handler="", schedule_interval_minutes=5)

    @patch("app.services.tenant_job_service._compute_next_run", return_value="NEXT")
    @patch("app.services.tenant_job_service.get_handler", return_value=lambda: None)
    def test_rejects_when_no_schedule(self, mock_get_handler, mock_compute):
        svc, db = _make_svc()
        with pytest.raises(BadRequestError, match="schedule_cron or schedule_interval_minutes"):
            svc.create_job(job_code="X", handler="h")

    @patch("app.services.tenant_job_service._compute_next_run", return_value="NEXT")
    @patch("app.services.tenant_job_service.get_handler", return_value=lambda: None)
    def test_creates_with_interval(self, mock_get_handler, mock_compute):
        svc, db = _make_svc()
        svc.create_job(
            job_code="  X  ",
            handler="  h  ",
            schedule_interval_minutes=5,
            params={"k": "v"},
        )
        added = db.add.call_args[0][0]
        # Strip whitespace
        assert added.job_code == "X"
        assert added.handler == "h"
        assert added.schedule_interval_minutes == 5
        assert added.params == {"k": "v"}
        assert added.next_run_at == "NEXT"
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

    @patch("app.services.tenant_job_service._compute_next_run", return_value="NEXT")
    @patch("app.services.tenant_job_service.get_handler", return_value=lambda: None)
    def test_creates_with_cron(self, mock_get_handler, mock_compute):
        svc, db = _make_svc()
        svc.create_job(
            job_code="X",
            handler="h",
            schedule_cron="*/5 * * * *",
            is_enabled=False,
        )
        added = db.add.call_args[0][0]
        assert added.schedule_cron == "*/5 * * * *"
        assert added.is_enabled is False


class TestUpdateJob:
    @patch("app.services.tenant_job_service._compute_next_run", return_value="NEXT")
    def test_applies_partial_update(self, mock_compute):
        svc, db = _make_svc()
        rec = SimpleNamespace(
            id=1,
            schedule_cron=None,
            schedule_interval_minutes=10,
            params=None,
            is_enabled=True,
            next_run_at=None,
            is_deleted=False,
        )
        db.query.return_value.filter.return_value.first.return_value = rec
        svc.update_job(1, schedule_interval_minutes=30, is_enabled=False)
        assert rec.schedule_interval_minutes == 30
        assert rec.is_enabled is False
        assert rec.next_run_at == "NEXT"
        db.commit.assert_called_once()

    @patch("app.services.tenant_job_service._compute_next_run", return_value="NEXT")
    def test_updates_cron_and_params(self, mock_compute):
        svc, db = _make_svc()
        rec = SimpleNamespace(
            id=1,
            schedule_cron=None,
            schedule_interval_minutes=10,
            params={},
            is_enabled=True,
            next_run_at=None,
            is_deleted=False,
        )
        db.query.return_value.filter.return_value.first.return_value = rec
        svc.update_job(1, schedule_cron="0 0 * * *", params={"a": 1})
        assert rec.schedule_cron == "0 0 * * *"
        assert rec.params == {"a": 1}

    def test_raises_when_missing(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundError):
            svc.update_job(99, schedule_interval_minutes=5)


class TestDeleteJob:
    def test_soft_deletes(self):
        svc, db = _make_svc()
        rec = MagicMock()
        rec.is_deleted = False
        db.query.return_value.filter.return_value.first.return_value = rec
        svc.delete_job(1)
        rec.soft_delete.assert_called_once()
        db.commit.assert_called_once()

    def test_raises_when_missing(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundError):
            svc.delete_job(99)
