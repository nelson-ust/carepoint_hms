"""Unit tests for TimesheetService (mock-based)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.enums import TimesheetStatus
from app.services.timesheet_service import TimesheetService


class TestTimesheetGet:
    def test_raises_404_when_not_found(self):
        db = MagicMock()
        svc = TimesheetService.__new__(TimesheetService)
        svc.db = db
        svc.repository = MagicMock()
        svc.repository.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            svc.get_timesheet(999)
        assert exc_info.value.status_code == 404

    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = TimesheetService.__new__(TimesheetService)
        svc.db = db
        svc.repository = MagicMock()
        ts = SimpleNamespace(id=1, notes="Week 1")
        svc.repository.get_by_id.return_value = ts

        result = svc.get_timesheet(1)
        svc.repository.get_by_id.assert_called_once_with(1)
        assert result.notes == "Week 1"


class TestTimesheetList:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = TimesheetService.__new__(TimesheetService)
        svc.db = db
        svc.repository = MagicMock()
        svc.repository.list_timesheets.return_value = ([], 0)

        items, total = svc.list_timesheets(staff_profile_id=7)
        svc.repository.list_timesheets.assert_called_once_with(7, 0, 100)
        assert total == 0


class TestTimesheetCreate:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = TimesheetService.__new__(TimesheetService)
        svc.db = db
        svc.repository = MagicMock()
        payload = MagicMock()
        svc.create_timesheet(payload)
        svc.repository.create.assert_called_once_with(payload)


class TestTimesheetUpdate:
    def test_rejects_non_draft(self):
        db = MagicMock()
        svc = TimesheetService.__new__(TimesheetService)
        svc.db = db
        svc.repository = MagicMock()
        ts = SimpleNamespace(id=1, status=TimesheetStatus.SUBMITTED)
        svc.repository.get_by_id.return_value = ts

        with pytest.raises(HTTPException, match="draft"):
            svc.update_timesheet(1, MagicMock())

    def test_allows_draft(self):
        db = MagicMock()
        svc = TimesheetService.__new__(TimesheetService)
        svc.db = db
        svc.repository = MagicMock()
        ts = SimpleNamespace(id=1, status=TimesheetStatus.DRAFT)
        svc.repository.get_by_id.return_value = ts

        payload = MagicMock()
        svc.update_timesheet(1, payload)
        svc.repository.update.assert_called_once_with(ts, payload)


class TestTimesheetDelete:
    def test_rejects_non_draft(self):
        db = MagicMock()
        svc = TimesheetService.__new__(TimesheetService)
        svc.db = db
        svc.repository = MagicMock()
        ts = SimpleNamespace(id=1, status=TimesheetStatus.APPROVED)
        svc.repository.get_by_id.return_value = ts

        with pytest.raises(HTTPException, match="draft"):
            svc.delete_timesheet(1)

    def test_allows_draft(self):
        db = MagicMock()
        svc = TimesheetService.__new__(TimesheetService)
        svc.db = db
        svc.repository = MagicMock()
        ts = SimpleNamespace(id=1, status=TimesheetStatus.DRAFT)
        svc.repository.get_by_id.return_value = ts

        svc.delete_timesheet(1)
        svc.repository.delete.assert_called_once_with(ts)


class TestTimesheetSubmit:
    def test_rejects_non_draft(self):
        db = MagicMock()
        svc = TimesheetService.__new__(TimesheetService)
        svc.db = db
        svc.repository = MagicMock()
        svc.approval_service = MagicMock()
        ts = SimpleNamespace(id=1, status=TimesheetStatus.LOCKED)
        svc.repository.get_by_id.return_value = ts

        with pytest.raises(HTTPException, match="draft"):
            svc.submit_timesheet(1, MagicMock(), user_id=10)

    def test_submits_to_approval_engine(self):
        db = MagicMock()
        svc = TimesheetService.__new__(TimesheetService)
        svc.db = db
        svc.repository = MagicMock()
        svc.approval_service = MagicMock()
        ts = SimpleNamespace(id=3, status=TimesheetStatus.DRAFT)
        svc.repository.get_by_id.return_value = ts

        payload = MagicMock(flow_id=5, title="Timesheet", submit_now=True)
        svc.submit_timesheet(3, payload, user_id=20)

        svc.approval_service.submit.assert_called_once()
        # The row is refreshed twice now: once after the approval engine may have
        # auto-finalized a zero-step flow, and again after the final commit.
        assert db.refresh.call_count == 2
        db.refresh.assert_called_with(ts)
