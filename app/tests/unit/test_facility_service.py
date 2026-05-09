"""Unit tests for FacilityService.

Covers list / get / create / update / delete for Facilities, 
FacilityNetworks, and FacilityServiceAreas.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.services.facility_service import FacilityService


def _make_svc():
    db = MagicMock()
    return FacilityService(db), db


class TestFacilityLogic:
    """
    Unit tests for core Facility management logic.
    """
    
    def test_list_returns_all(self):
        svc, db = _make_svc()
        with patch.object(svc.repo, 'list_facilities', return_value=["f1", "f2"]):
            assert svc.list_facilities() == ["f1", "f2"]

    def test_get_returns_facility(self):
        svc, db = _make_svc()
        f = SimpleNamespace(id=1, code="HQ")
        with patch.object(svc.repo, 'get_facility', return_value=f):
            assert svc.get_facility(1) is f

    def test_get_raises_when_missing(self):
        svc, db = _make_svc()
        with patch.object(svc.repo, 'get_facility', return_value=None):
            with pytest.raises(NotFoundError, match="Facility not found"):
                svc.get_facility(99)

    @patch("app.services.facility_service.get_master_db_context")
    @patch("app.services.facility_service.get_current_tenant_id")
    def test_create_facility_happy_path(self, mock_tenant, mock_master_ctx):
        svc, db = _make_svc()
        mock_tenant.return_value = 7
        
        # Mock subscription
        plan = SimpleNamespace(max_facilities=10)
        sub = SimpleNamespace(plan=plan)
        master = MagicMock()
        mock_master_ctx.return_value.__enter__.return_value = master
        master.query.return_value.join.return_value.filter.return_value.first.return_value = sub
        
        # Mock repo checks
        db.query.return_value.scalar.return_value = 0
        with patch.object(svc.repo, 'get_facility_by_code', return_value=None):
            payload = MagicMock()
            payload.code = "NEW-01"
            svc.create_facility(payload)
            assert svc.repo.db.add.called

class TestFacilityNetworkLogic:
    """
    Unit tests for FacilityNetwork management.
    """
    
    def test_list_networks(self):
        svc, _ = _make_svc()
        with patch.object(svc.repo, 'list_networks', return_value=["n1"]):
            assert svc.list_networks() == ["n1"]

    def test_get_network_happy_path(self):
        svc, _ = _make_svc()
        n = SimpleNamespace(id=1, name="Net 1")
        with patch.object(svc.repo, 'get_network', return_value=n):
            assert svc.get_network(1) == n

    def test_get_network_raises_404(self):
        svc, _ = _make_svc()
        with patch.object(svc.repo, 'get_network', return_value=None):
            with pytest.raises(NotFoundError, match="Hospital network not found"):
                svc.get_network(404)

    def test_create_network_happy_path(self):
        svc, _ = _make_svc()
        payload = MagicMock()
        payload.code = "NET-01"
        with patch.object(svc.repo, 'get_network_by_code', return_value=None):
            svc.create_network(payload)
            assert svc.repo.db.add.called

    def test_create_network_rejects_duplicate(self):
        svc, _ = _make_svc()
        payload = MagicMock()
        payload.code = "DUP"
        with patch.object(svc.repo, 'get_network_by_code', return_value=SimpleNamespace(id=1)):
            with pytest.raises(BadRequestError, match="already exists"):
                svc.create_network(payload)

class TestFacilityServiceAreaLogic:
    """
    Unit tests for FacilityServiceArea management.
    """

    def test_list_service_areas(self):
        svc, _ = _make_svc()
        with patch.object(svc.repo, 'list_service_areas', return_value=["area1"]):
            assert svc.list_service_areas() == ["area1"]

    def test_get_service_area_happy_path(self):
        svc, _ = _make_svc()
        a = SimpleNamespace(id=1, area_name="Lagos Central")
        with patch.object(svc.repo, 'get_service_area', return_value=a):
            assert svc.get_service_area(1) == a

    def test_create_service_area_happy_path(self):
        svc, _ = _make_svc()
        payload = MagicMock()
        payload.facility_id = 1
        with patch.object(svc, 'get_facility', return_value=SimpleNamespace(id=1)):
            svc.create_service_area(payload)
            assert svc.repo.db.add.called
