"""Unit tests for ReimbursementService (mock-based)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.enums import ReimbursementStatus
from app.services.reimbursement_service import ReimbursementService


class TestReimbursementGet:
    def test_raises_404_when_not_found(self):
        db = MagicMock()
        svc = ReimbursementService.__new__(ReimbursementService)
        svc.db = db
        svc.repository = MagicMock()
        svc.repository.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            svc.get_reimbursement(999)
        assert exc_info.value.status_code == 404

    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = ReimbursementService.__new__(ReimbursementService)
        svc.db = db
        svc.repository = MagicMock()
        req = SimpleNamespace(id=1, category="Travel")
        svc.repository.get_by_id.return_value = req

        result = svc.get_reimbursement(1)
        svc.repository.get_by_id.assert_called_once_with(1)
        assert result.category == "Travel"


class TestReimbursementList:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = ReimbursementService.__new__(ReimbursementService)
        svc.db = db
        svc.repository = MagicMock()
        svc.repository.list_requests.return_value = ([], 0)

        items, total = svc.list_reimbursements(staff_profile_id=5)
        svc.repository.list_requests.assert_called_once_with(5, 0, 100)
        assert total == 0


class TestReimbursementCreate:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = ReimbursementService.__new__(ReimbursementService)
        svc.db = db
        svc.repository = MagicMock()
        payload = MagicMock()
        svc.create_reimbursement(payload)
        svc.repository.create.assert_called_once_with(payload)


class TestReimbursementUpdate:
    def test_rejects_non_draft(self):
        db = MagicMock()
        svc = ReimbursementService.__new__(ReimbursementService)
        svc.db = db
        svc.repository = MagicMock()
        req = SimpleNamespace(id=1, status=ReimbursementStatus.PENDING)
        svc.repository.get_by_id.return_value = req

        with pytest.raises(HTTPException, match="draft"):
            svc.update_reimbursement(1, MagicMock())

    def test_allows_draft(self):
        db = MagicMock()
        svc = ReimbursementService.__new__(ReimbursementService)
        svc.db = db
        svc.repository = MagicMock()
        req = SimpleNamespace(id=1, status=ReimbursementStatus.DRAFT)
        svc.repository.get_by_id.return_value = req

        payload = MagicMock()
        svc.update_reimbursement(1, payload)
        svc.repository.update.assert_called_once_with(req, payload)


class TestReimbursementDelete:
    def test_rejects_non_draft(self):
        db = MagicMock()
        svc = ReimbursementService.__new__(ReimbursementService)
        svc.db = db
        svc.repository = MagicMock()
        req = SimpleNamespace(id=1, status=ReimbursementStatus.APPROVED)
        svc.repository.get_by_id.return_value = req

        with pytest.raises(HTTPException, match="draft"):
            svc.delete_reimbursement(1)

    def test_allows_draft(self):
        db = MagicMock()
        svc = ReimbursementService.__new__(ReimbursementService)
        svc.db = db
        svc.repository = MagicMock()
        req = SimpleNamespace(id=1, status=ReimbursementStatus.DRAFT)
        svc.repository.get_by_id.return_value = req

        svc.delete_reimbursement(1)
        svc.repository.delete.assert_called_once_with(req)


class TestReimbursementSubmit:
    def test_rejects_non_draft(self):
        db = MagicMock()
        svc = ReimbursementService.__new__(ReimbursementService)
        svc.db = db
        svc.repository = MagicMock()
        svc.approval_service = MagicMock()
        req = SimpleNamespace(id=1, status=ReimbursementStatus.PAID)
        svc.repository.get_by_id.return_value = req

        with pytest.raises(HTTPException, match="draft"):
            svc.submit_reimbursement(1, MagicMock(), user_id=10)

    def test_submits_to_approval_engine(self):
        db = MagicMock()
        svc = ReimbursementService.__new__(ReimbursementService)
        svc.db = db
        svc.repository = MagicMock()
        svc.approval_service = MagicMock()
        req = SimpleNamespace(id=5, status=ReimbursementStatus.DRAFT)
        svc.repository.get_by_id.return_value = req

        payload = MagicMock(flow_id=10, title="Submit", submit_now=True)
        svc.submit_reimbursement(5, payload, user_id=42)

        svc.approval_service.submit.assert_called_once()
        db.refresh.assert_called_once_with(req)
