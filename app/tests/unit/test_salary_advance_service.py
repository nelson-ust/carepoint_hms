"""Unit tests for SalaryAdvanceService (mock-based)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.enums import SalaryAdvanceStatus
from app.services.salary_advance_service import SalaryAdvanceService


class TestSalaryAdvanceGet:
    def test_raises_404_when_not_found(self):
        db = MagicMock()
        svc = SalaryAdvanceService.__new__(SalaryAdvanceService)
        svc.db = db
        svc.repository = MagicMock()
        svc.repository.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            svc.get_salary_advance(999)
        assert exc_info.value.status_code == 404

    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = SalaryAdvanceService.__new__(SalaryAdvanceService)
        svc.db = db
        svc.repository = MagicMock()
        advance = SimpleNamespace(id=1, reason="Emergency")
        svc.repository.get_by_id.return_value = advance

        result = svc.get_salary_advance(1)
        svc.repository.get_by_id.assert_called_once_with(1)
        assert result.reason == "Emergency"


class TestSalaryAdvanceList:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = SalaryAdvanceService.__new__(SalaryAdvanceService)
        svc.db = db
        svc.repository = MagicMock()
        svc.repository.list_requests.return_value = ([], 0)

        items, total = svc.list_salary_advances(staff_profile_id=3)
        svc.repository.list_requests.assert_called_once_with(3, 0, 100)
        assert total == 0


class TestSalaryAdvanceCreate:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = SalaryAdvanceService.__new__(SalaryAdvanceService)
        svc.db = db
        svc.repository = MagicMock()
        payload = MagicMock()
        svc.create_salary_advance(payload)
        svc.repository.create.assert_called_once_with(payload)


class TestSalaryAdvanceUpdate:
    def test_rejects_non_draft(self):
        db = MagicMock()
        svc = SalaryAdvanceService.__new__(SalaryAdvanceService)
        svc.db = db
        svc.repository = MagicMock()
        advance = SimpleNamespace(id=1, status=SalaryAdvanceStatus.APPROVED)
        svc.repository.get_by_id.return_value = advance

        with pytest.raises(HTTPException, match="draft"):
            svc.update_salary_advance(1, MagicMock())

    def test_allows_draft(self):
        db = MagicMock()
        svc = SalaryAdvanceService.__new__(SalaryAdvanceService)
        svc.db = db
        svc.repository = MagicMock()
        advance = SimpleNamespace(id=1, status=SalaryAdvanceStatus.DRAFT)
        svc.repository.get_by_id.return_value = advance

        payload = MagicMock()
        svc.update_salary_advance(1, payload)
        svc.repository.update.assert_called_once_with(advance, payload)


class TestSalaryAdvanceDelete:
    def test_rejects_non_draft(self):
        db = MagicMock()
        svc = SalaryAdvanceService.__new__(SalaryAdvanceService)
        svc.db = db
        svc.repository = MagicMock()
        advance = SimpleNamespace(id=1, status=SalaryAdvanceStatus.PAID)
        svc.repository.get_by_id.return_value = advance

        with pytest.raises(HTTPException, match="draft"):
            svc.delete_salary_advance(1)

    def test_allows_draft(self):
        db = MagicMock()
        svc = SalaryAdvanceService.__new__(SalaryAdvanceService)
        svc.db = db
        svc.repository = MagicMock()
        advance = SimpleNamespace(id=1, status=SalaryAdvanceStatus.DRAFT)
        svc.repository.get_by_id.return_value = advance

        svc.delete_salary_advance(1)
        svc.repository.delete.assert_called_once_with(advance)


class TestSalaryAdvanceSubmit:
    def test_rejects_non_draft(self):
        db = MagicMock()
        svc = SalaryAdvanceService.__new__(SalaryAdvanceService)
        svc.db = db
        svc.repository = MagicMock()
        svc.approval_service = MagicMock()
        advance = SimpleNamespace(id=1, status=SalaryAdvanceStatus.SUBMITTED)
        svc.repository.get_by_id.return_value = advance

        with pytest.raises(HTTPException, match="draft"):
            svc.submit_salary_advance(1, MagicMock(), user_id=10)

    def test_submits_to_approval_engine(self):
        db = MagicMock()
        svc = SalaryAdvanceService.__new__(SalaryAdvanceService)
        svc.db = db
        svc.repository = MagicMock()
        svc.approval_service = MagicMock()
        advance = SimpleNamespace(id=7, status=SalaryAdvanceStatus.DRAFT)
        svc.repository.get_by_id.return_value = advance

        payload = MagicMock(flow_id=3, title="Advance", submit_now=True)
        svc.submit_salary_advance(7, payload, user_id=55)

        svc.approval_service.submit.assert_called_once()
        db.refresh.assert_called_once_with(advance)
