"""Unit tests for reimbursement routes (mock-based)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestReimbursementRouteAuth:
    def test_unauthenticated_create_returns_401(self, client):
        payload = {
            "staff_profile_id": 1,
            "expense_date": "2026-05-01",
            "amount": "100.00",
            "category": "Travel",
            "description": "Test",
        }
        response = client.post("/api/v1/reimbursements", json=payload)
        assert response.status_code == 401

    def test_unauthenticated_list_returns_401(self, client):
        response = client.get("/api/v1/reimbursements")
        assert response.status_code == 401
