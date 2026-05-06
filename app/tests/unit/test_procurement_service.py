"""Unit tests for ProcurementService (mock-based)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.enums import ProcurementRequisitionStatus
from app.services.procurement_service import ProcurementService


class TestProcurementGet:
    def test_raises_404_when_not_found(self):
        db = MagicMock()
        svc = ProcurementService.__new__(ProcurementService)
        svc.db = db
        svc.repository = MagicMock()
        svc.repository.get_requisition_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            svc.get_requisition(999)
        assert exc_info.value.status_code == 404

    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = ProcurementService.__new__(ProcurementService)
        svc.db = db
        svc.repository = MagicMock()
        req = SimpleNamespace(id=1, justification="Lab supplies")
        svc.repository.get_requisition_by_id.return_value = req

        result = svc.get_requisition(1)
        svc.repository.get_requisition_by_id.assert_called_once_with(1)
        assert result.justification == "Lab supplies"


class TestProcurementList:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = ProcurementService.__new__(ProcurementService)
        svc.db = db
        svc.repository = MagicMock()
        svc.repository.list_requisitions.return_value = ([], 0)

        items, total = svc.list_requisitions(department_id=1)
        svc.repository.list_requisitions.assert_called_once_with(1, 0, 100)
        assert total == 0


class TestProcurementCreate:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = ProcurementService.__new__(ProcurementService)
        svc.db = db
        svc.repository = MagicMock()
        payload = MagicMock()
        svc.create_requisition(payload)
        svc.repository.create_requisition.assert_called_once_with(payload)


class TestProcurementUpdate:
    def test_rejects_non_draft(self):
        db = MagicMock()
        svc = ProcurementService.__new__(ProcurementService)
        svc.db = db
        svc.repository = MagicMock()
        req = SimpleNamespace(id=1, status=ProcurementRequisitionStatus.SUBMITTED)
        svc.repository.get_requisition_by_id.return_value = req

        with pytest.raises(HTTPException, match="draft"):
            svc.update_requisition(1, MagicMock())

    def test_allows_draft(self):
        db = MagicMock()
        svc = ProcurementService.__new__(ProcurementService)
        svc.db = db
        svc.repository = MagicMock()
        req = SimpleNamespace(id=1, status=ProcurementRequisitionStatus.DRAFT)
        svc.repository.get_requisition_by_id.return_value = req

        payload = MagicMock()
        svc.update_requisition(1, payload)
        svc.repository.update_requisition.assert_called_once_with(req, payload)


class TestProcurementDelete:
    def test_rejects_non_draft(self):
        db = MagicMock()
        svc = ProcurementService.__new__(ProcurementService)
        svc.db = db
        svc.repository = MagicMock()
        req = SimpleNamespace(id=1, status=ProcurementRequisitionStatus.FINANCE_APPROVED)
        svc.repository.get_requisition_by_id.return_value = req

        with pytest.raises(HTTPException, match="draft"):
            svc.delete_requisition(1)

    def test_allows_draft(self):
        db = MagicMock()
        svc = ProcurementService.__new__(ProcurementService)
        svc.db = db
        svc.repository = MagicMock()
        req = SimpleNamespace(id=1, status=ProcurementRequisitionStatus.DRAFT)
        svc.repository.get_requisition_by_id.return_value = req

        svc.delete_requisition(1)
        svc.repository.delete_requisition.assert_called_once_with(req)


class TestProcurementSubmit:
    def test_rejects_non_draft(self):
        db = MagicMock()
        svc = ProcurementService.__new__(ProcurementService)
        svc.db = db
        svc.repository = MagicMock()
        svc.approval_service = MagicMock()
        req = SimpleNamespace(id=1, status=ProcurementRequisitionStatus.SUBMITTED)
        svc.repository.get_requisition_by_id.return_value = req

        with pytest.raises(HTTPException, match="draft"):
            svc.submit_requisition(1, MagicMock(), user_id=10)

    def test_submits_to_approval_engine(self):
        db = MagicMock()
        svc = ProcurementService.__new__(ProcurementService)
        svc.db = db
        svc.repository = MagicMock()
        svc.approval_service = MagicMock()
        req = SimpleNamespace(id=5, status=ProcurementRequisitionStatus.DRAFT)
        svc.repository.get_requisition_by_id.return_value = req

        payload = MagicMock(flow_id=10, title="Submit", submit_now=True)
        svc.submit_requisition(5, payload, user_id=42)

        svc.approval_service.submit.assert_called_once()
        db.refresh.assert_called_once_with(req)
