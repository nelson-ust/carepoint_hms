"""Unit tests for procurement routes (mock-based)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.enums import ProcurementRequisitionStatus


class TestProcurementRouteCreate:
    def test_unauthenticated_create_returns_401(self, client):
        payload = {
            "requested_by_staff_id": 1,
            "items": [{"item_name": "Paper", "quantity_requested": 5, "estimated_unit_price": "10.00"}]
        }
        response = client.post("/api/v1/procurements/requisitions", json=payload)
        assert response.status_code == 401


class TestProcurementRouteList:
    def test_unauthenticated_returns_401(self, client):
        response = client.get("/api/v1/procurements/requisitions")
        assert response.status_code == 401
