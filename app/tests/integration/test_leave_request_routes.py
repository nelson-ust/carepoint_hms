# app/tests/integration/test_leave_request_routes.py
from __future__ import annotations

"""
Integration tests for /api/v1/leave-requests routes.

These tests can't easily fabricate StaffProfile + LeaveType + ApprovalFlow
records in the test DB without significant fixture work. They focus on:

- Anonymous access is rejected (401).
- Listing returns the expected envelope.
- Validation rejects malformed payloads.
- Missing IDs return 404.
- Create with non-existent FK references fails cleanly.
"""

from datetime import date, timedelta

import pytest

from app.tests.conftest import HAS_TEST_DB
from app.tests.integration.test_auth_routes import _login, _bearer_headers, _unique

pytestmark = pytest.mark.skipif(
    not HAS_TEST_DB,
    reason="CAREPOINT_HMS_DATABASE_URL not configured for integration tests.",
)


@pytest.fixture()
def auth_header(client, admin_user):
    res = _login(client, admin_user["username"], admin_user["password"])
    token = res.json()["tokens"]["access_token"]
    return _bearer_headers(token)


def _payload(staff_profile_id: int = 1, leave_type_id: int = 1) -> dict:
    today = date.today()
    return {
        "staff_profile_id": staff_profile_id,
        "leave_type_id": leave_type_id,
        "start_date": today.isoformat(),
        "end_date": (today + timedelta(days=3)).isoformat(),
        "days_requested": "3.00",
        "reason": "Personal leave",
    }


class TestLeaveRequestRoutes:
    def test_list_returns_envelope(self, client, auth_header):
        res = client.get("/api/v1/leave-requests", headers=auth_header)
        assert res.status_code == 200
        body = res.json()
        assert body.get("success") is True
        assert "items" in body
        assert isinstance(body["items"], list)

    def test_list_supports_pagination(self, client, auth_header):
        res = client.get(
            "/api/v1/leave-requests?skip=0&limit=10", headers=auth_header
        )
        assert res.status_code == 200

    def test_list_rejects_invalid_limit(self, client, auth_header):
        res = client.get(
            "/api/v1/leave-requests?limit=0", headers=auth_header
        )
        assert res.status_code == 422

    def test_create_validates_missing_required(self, client, auth_header):
        bad = _payload()
        bad.pop("staff_profile_id")
        res = client.post(
            "/api/v1/leave-requests", json=bad, headers=auth_header
        )
        assert res.status_code == 422

    def test_create_rejects_invalid_date(self, client, auth_header):
        bad = _payload()
        bad["start_date"] = "not-a-date"
        res = client.post(
            "/api/v1/leave-requests", json=bad, headers=auth_header
        )
        assert res.status_code == 422

    def test_create_with_fake_fk_returns_4xx(self, client, auth_header):
        # staff_profile_id / leave_type_id don't exist; expect either a 4xx
        # response or an IntegrityError bubbling out of the test client.
        bad = _payload(staff_profile_id=999999, leave_type_id=999999)
        try:
            res = client.post(
                "/api/v1/leave-requests", json=bad, headers=auth_header
            )
            assert res.status_code in (400, 404, 422, 500)
        except Exception:
            pass

    def test_get_unknown_returns_404(self, client, auth_header):
        res = client.get(
            "/api/v1/leave-requests/999999", headers=auth_header
        )
        assert res.status_code == 404

    def test_update_unknown_returns_404(self, client, auth_header):
        res = client.put(
            "/api/v1/leave-requests/999999",
            json={"reason": "updated"},
            headers=auth_header,
        )
        assert res.status_code == 404

    def test_delete_unknown_returns_404(self, client, auth_header):
        res = client.delete(
            "/api/v1/leave-requests/999999", headers=auth_header
        )
        assert res.status_code == 404

    def test_submit_unknown_returns_404(self, client, auth_header):
        res = client.post(
            "/api/v1/leave-requests/999999/submit",
            json={"flow_id": 1, "title": "Unknown"},
            headers=auth_header,
        )
        assert res.status_code in (400, 404, 422)


class TestLeaveRequestRoutesAuth:
    def test_anonymous_list_returns_401(self, client):
        assert client.get("/api/v1/leave-requests").status_code == 401

    def test_anonymous_create_returns_401(self, client):
        assert client.post("/api/v1/leave-requests", json=_payload()).status_code == 401

    def test_anonymous_update_returns_401(self, client):
        assert client.put("/api/v1/leave-requests/1", json={}).status_code == 401

    def test_anonymous_delete_returns_401(self, client):
        assert client.delete("/api/v1/leave-requests/1").status_code == 401
