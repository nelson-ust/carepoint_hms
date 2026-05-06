"""Unit tests for salary advance routes (mock-based)."""
from __future__ import annotations

import pytest


class TestSalaryAdvanceRouteAuth:
    def test_unauthenticated_create_returns_401(self, client):
        payload = {
            "staff_profile_id": 1,
            "amount": "500.00",
            "reason": "Emergency",
        }
        response = client.post("/api/v1/salary-advances", json=payload)
        assert response.status_code == 401

    def test_unauthenticated_list_returns_401(self, client):
        response = client.get("/api/v1/salary-advances")
        assert response.status_code == 401

    def test_unauthenticated_submit_returns_401(self, client):
        response = client.post("/api/v1/salary-advances/1/submit", json={"flow_id": 1, "title": "Test"})
        assert response.status_code == 401
