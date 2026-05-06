"""Unit tests for ApprovalService (mock-based)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.enums import ApprovalSubjectType, ApprovalRequestStatus, ApprovalRequestStepStatus
from app.services.approval_service import ApprovalFlowService, ApprovalRequestService


class TestApprovalFlowService:
    def test_create_flow_delegates(self):
        db = MagicMock()
        svc = ApprovalFlowService.__new__(ApprovalFlowService)
        svc.db = db
        svc.flow_repo = MagicMock()
        
        payload = MagicMock()
        svc.create(payload, actor_user_id=1)
        
        svc.flow_repo.create_flow_with_steps.assert_called_once()
        kwargs = svc.flow_repo.create_flow_with_steps.call_args.kwargs
        assert kwargs["actor_user_id"] == 1

    def test_list_flows_delegates(self):
        db = MagicMock()
        svc = ApprovalFlowService.__new__(ApprovalFlowService)
        svc.db = db
        svc.flow_repo = MagicMock()
        svc.flow_repo.list_flows.return_value = ([], 0)

        flows, total = svc.list_flows()
        svc.flow_repo.list_flows.assert_called_once()
        assert total == 0


class TestApprovalRequestService:
    def test_submit_delegates_to_repo(self):
        db = MagicMock()
        svc = ApprovalRequestService.__new__(ApprovalRequestService)
        svc.db = db
        svc.flow_repo = MagicMock()
        svc.request_repo = MagicMock()
        
        # Mock internal helpers
        with patch.object(svc, "_resolve_flow") as mock_resolve_flow, \
             patch.object(svc, "_resolve_requester_context") as mock_resolve_ctx:
            
            mock_resolve_flow.return_value = SimpleNamespace(id=1, auto_cancel_after_hours=None)
            mock_resolve_ctx.return_value = (SimpleNamespace(id=1, department_id=2, facility_id=3), 2, 3)
            
            payload = MagicMock(submit_now=False, flow_id=1, flow_code=None, subject_type="TYPE", subject_id=1)
            svc.submit(payload, requester_user_id=42)
            
            svc.request_repo.create_request.assert_called_once()

    def test_decide_rejects_non_pending(self):
        db = MagicMock()
        svc = ApprovalRequestService.__new__(ApprovalRequestService)
        svc.db = db
        svc.request_repo = MagicMock()
        
        req = SimpleNamespace(status=ApprovalRequestStatus.APPROVED)
        svc.request_repo.get_required_by_id.return_value = req
        
        from app.core.exceptions import BadRequestError
        with pytest.raises(BadRequestError, match="not awaiting decisions"):
            svc.decide(1, MagicMock(), decider_user_id=42)

    def test_cancel_rejects_non_requester(self):
        db = MagicMock()
        svc = ApprovalRequestService.__new__(ApprovalRequestService)
        svc.db = db
        svc.request_repo = MagicMock()
        
        req = SimpleNamespace(
            status=ApprovalRequestStatus.IN_PROGRESS, 
            requester_user_id=99,
            subject_type=ApprovalSubjectType.LEAVE_REQUEST,
            subject_id=1
        )
        svc.request_repo.get_required_by_id.return_value = req
        
        from app.core.exceptions import ForbiddenError
        with pytest.raises(ForbiddenError, match="Only the requester can cancel"):
            svc.cancel(1, actor_user_id=42, reason="Test")
