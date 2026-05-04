"""Unit tests for ServiceDeliveryService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import NotFoundError
from app.services.service_delivery_point_service import ServiceDeliveryService


def _make_svc():
    db = MagicMock()
    svc = ServiceDeliveryService(db)
    svc.repository = MagicMock()
    return svc


class TestGetServiceDeliveryPoint:
    def test_raises_not_found(self):
        svc = _make_svc()
        svc.repository.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            svc.get_service_delivery_point(999)

    def test_returns_point(self):
        svc = _make_svc()
        sdp = SimpleNamespace(id=1, code="LAB")
        svc.repository.get_by_id.return_value = sdp
        assert svc.get_service_delivery_point(1) is sdp


class TestGetByCode:
    def test_raises_not_found(self):
        svc = _make_svc()
        svc.repository.get_by_code.return_value = None
        with pytest.raises(NotFoundError):
            svc.get_service_delivery_point_by_code("NOPE")


class TestConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = ServiceDeliveryService(db)
        assert svc.db is db
