"""Unit tests for approval routes (mock-based)."""
from __future__ import annotations

import pytest


class TestApprovalRouteAuth:
    def test_unauthenticated_create_flow_returns_401(self, client):
        payload = {
            "code": "TEST",
            "name": "Test Flow",
            "subject_type": "LEAVE_REQUEST",
            "steps": []
        }
        response = client.post("/api/v1/approvals/flows", json=payload)
        assert response.status_code == 401

    def test_unauthenticated_list_flows_returns_401(self, client):
        response = client.get("/api/v1/approvals/flows")
        assert response.status_code == 401

    def test_unauthenticated_submit_request_returns_401(self, client):
        payload = {
            "flow_id": 1,
            "subject_type": "LEAVE_REQUEST",
            "subject_id": 1,
            "title": "Test"
        }
        response = client.post("/api/v1/approvals/requests", json=payload)
        assert response.status_code == 401

    def test_unauthenticated_record_decision_returns_401(self, client):
        payload = {"action": "APPROVE"}
        response = client.post("/api/v1/approvals/requests/1/decisions", json=payload)
        assert response.status_code == 401
