# app/tests/unit/test_visit_service.py
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from datetime import datetime, timezone

from app.services.visit_service import VisitService
from app.schemas.visit_schemas import VisitInitiateSchema, VisitRerouteSchema
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.enums import VisitPriority, VisitStatus, QueueStatus

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def service(mock_db):
    with patch("app.services.visit_service.VisitRepository") as mock_repo_cls:
        svc = VisitService(mock_db)
        svc.repository = mock_repo_cls.return_value
        yield svc

class TestVisitService:

    def test_initiate_visit_fails_if_patient_not_found(self, service):
        payload = VisitInitiateSchema(patient_id=999, visit_reason="Fever")
        service.repository.get_patient_by_id = MagicMock(return_value=None)
        
        with pytest.raises(NotFoundError):
            service.initiate_visit(payload)

    def test_initiate_visit_blocks_duplicate_active_visit(self, service):
        payload = VisitInitiateSchema(patient_id=1, visit_reason="Fever")
        service.repository.get_patient_by_id = MagicMock(return_value=MagicMock(id=1, insurance_records=[]))
        service.repository.patient_has_open_or_waiting_visit = MagicMock(return_value=True)
        
        with pytest.raises(BadRequestError) as excinfo:
            service.initiate_visit(payload)
        assert "already has an active visit" in str(excinfo.value)

    def test_reroute_visit_fails_if_visit_not_found(self, service):
        payload = VisitRerouteSchema(service_delivery_point_id=2, reason="Change")
        service.repository.get_detailed_visit_by_id = MagicMock(return_value=None)
        
        with pytest.raises(NotFoundError):
            service.reroute_visit(1, payload)

    def test_reroute_visit_blocks_completed_visit(self, service):
        payload = VisitRerouteSchema(service_delivery_point_id=2, reason="Change")
        visit = MagicMock(id=1, status=VisitStatus.COMPLETED)
        service.repository.get_detailed_visit_by_id = MagicMock(return_value=visit)
        service.repository.get_service_delivery_point_by_id = MagicMock(return_value=MagicMock(id=2))
        
        with pytest.raises(BadRequestError) as excinfo:
            service.reroute_visit(1, payload)
        assert "Completed or cancelled visits cannot be rerouted" in str(excinfo.value)

    def test_resolve_visit_priority_handles_fast_track(self, service):
        prio = service._resolve_visit_priority(None, fast_track=True)
        assert prio == VisitPriority.URGENT
        
        prio = service._resolve_visit_priority(VisitPriority.NORMAL, fast_track=True)
        assert prio == VisitPriority.NORMAL

    def test_resolve_visit_status_normalization(self, service):
        assert service._resolve_visit_status("waiting") == VisitStatus.WAITING
        assert service._resolve_visit_status(VisitStatus.COMPLETED) == VisitStatus.COMPLETED
        
        with pytest.raises(BadRequestError):
            service._resolve_visit_status("INVALID_STATUS")
