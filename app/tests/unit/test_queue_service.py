# app/tests/unit/test_queue_service.py
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from datetime import datetime, timezone

from app.services.queue_service import QueueService
from app.core.enums import QueueStatus, VisitFlowStepStatus
from app.core.exceptions import BadRequestError, NotFoundError

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def service(mock_db):
    with patch("app.services.queue_service.QueueRepository") as mock_repo_cls:
        svc = QueueService(mock_db)
        svc.repository = mock_repo_cls.return_value
        yield svc

class TestQueueService:

    def test_call_ticket_updates_status_and_time(self, service, mock_db):
        ticket = MagicMock(id=1, status=QueueStatus.WAITING, called_at=None)
        service.repository.get_required_by_id = MagicMock(return_value=ticket)
        service._link_step_status = MagicMock()
        
        result = service.call_ticket(1)
        
        assert ticket.status == QueueStatus.CALLED
        assert ticket.called_at is not None
        mock_db.commit.assert_called_once()
        service._link_step_status.assert_called_once_with(ticket, VisitFlowStepStatus.CALLED)

    def test_call_ticket_blocks_terminal_state(self, service):
        ticket = MagicMock(id=1, status=QueueStatus.SERVED)
        service.repository.get_required_by_id = MagicMock(return_value=ticket)
        
        with pytest.raises(BadRequestError) as excinfo:
            service.call_ticket(1)
        assert "reached a terminal state" in str(excinfo.value)

    def test_start_serving_updates_times(self, service, mock_db):
        ticket = MagicMock(id=1, status=QueueStatus.WAITING, called_at=None, service_started_at=None)
        service.repository.get_required_by_id = MagicMock(return_value=ticket)
        service._link_step_status = MagicMock()
        
        service.start_serving(1)
        
        assert ticket.status == QueueStatus.SERVING
        assert ticket.called_at is not None
        assert ticket.service_started_at is not None
        mock_db.commit.assert_called_once()

    def test_get_my_worklist_fails_if_no_sdp(self, service):
        user = MagicMock(staff_profile=MagicMock(service_delivery_point_id=None))
        
        with pytest.raises(BadRequestError) as excinfo:
            service.get_my_worklist(user)
        assert "not assigned to any service delivery point" in str(excinfo.value)

    def test_complete_and_route_to_blocks_same_sdp(self, service):
        ticket = MagicMock(id=1, status=QueueStatus.SERVING, service_delivery_point_id=10)
        service.repository.get_required_by_id = MagicMock(return_value=ticket)
        
        with pytest.raises(BadRequestError) as excinfo:
            service.complete_and_route_to(1, 10)
        assert "Target service delivery point must differ" in str(excinfo.value)

    def test_link_step_status_updates_flow_step(self, service, mock_db):
        ticket = MagicMock(visit_flow_step_id=100)
        mock_step = MagicMock(id=100, status=VisitFlowStepStatus.PENDING, started_at=None)
        mock_db.query().filter().first.return_value = mock_step
        
        service._link_step_status(ticket, VisitFlowStepStatus.IN_PROGRESS, started=True)
        
        assert mock_step.status == VisitFlowStepStatus.IN_PROGRESS
        assert mock_step.started_at is not None
        mock_db.add.assert_called_once_with(mock_step)
