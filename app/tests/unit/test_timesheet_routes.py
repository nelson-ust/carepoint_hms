"""Unit tests for timesheet routes (mock-based)."""
from __future__ import annotations

import pytest


class TestTimesheetRouteAuth:
    def test_unauthenticated_create_returns_401(self, client):
        payload = {
            "staff_profile_id": 1,
            "period_start": "2026-05-01",
            "period_end": "2026-05-07",
        }
        response = client.post("/api/v1/timesheets", json=payload)
        assert response.status_code == 401

    def test_unauthenticated_list_returns_401(self, client):
        response = client.get("/api/v1/timesheets")
        assert response.status_code == 401

    def test_unauthenticated_submit_returns_401(self, client):
        response = client.post("/api/v1/timesheets/1/submit", json={"flow_id": 1, "title": "Test"})
        assert response.status_code == 401
