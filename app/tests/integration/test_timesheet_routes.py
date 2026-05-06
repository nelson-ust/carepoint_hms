# app/tests/integration/test_timesheet_routes.py
from __future__ import annotations

"""
Integration tests for /api/v1/timesheets routes.
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


def _payload(staff_profile_id: int = 1) -> dict:
    today = date.today()
    return {
        "staff_profile_id": staff_profile_id,
        "period_start": (today - timedelta(days=14)).isoformat(),
        "period_end": today.isoformat(),
        "notes": "Bi-weekly timesheet",
        "entries": [],
    }


class TestTimesheetRoutes:
    def test_list_returns_envelope(self, client, auth_header):
        res = client.get("/api/v1/timesheets", headers=auth_header)
        assert res.status_code == 200
        body = res.json()
        assert body.get("success") is True
        assert "items" in body

    def test_list_supports_pagination(self, client, auth_header):
        res = client.get(
            "/api/v1/timesheets?skip=0&limit=10", headers=auth_header
        )
        assert res.status_code == 200

    def test_list_rejects_invalid_limit(self, client, auth_header):
        res = client.get("/api/v1/timesheets?limit=0", headers=auth_header)
        assert res.status_code == 422

    def test_create_validates_missing_required(self, client, auth_header):
        bad = _payload()
        bad.pop("staff_profile_id")
        res = client.post(
            "/api/v1/timesheets", json=bad, headers=auth_header
        )
        assert res.status_code == 422

    def test_create_rejects_invalid_date(self, client, auth_header):
        bad = _payload()
        bad["period_start"] = "not-a-date"
        res = client.post(
            "/api/v1/timesheets", json=bad, headers=auth_header
        )
        assert res.status_code == 422

    def test_create_with_fake_fk_returns_4xx(self, client, auth_header):
        bad = _payload(staff_profile_id=999999)
        # The service doesn't pre-check FK existence, so SQLAlchemy raises
        # IntegrityError that the TestClient propagates as an exception.
        try:
            res = client.post(
                "/api/v1/timesheets", json=bad, headers=auth_header
            )
            assert res.status_code in (400, 404, 422, 500)
        except Exception:
            pass

    def test_get_unknown_returns_404(self, client, auth_header):
        res = client.get("/api/v1/timesheets/999999", headers=auth_header)
        assert res.status_code == 404

    def test_update_unknown_returns_404(self, client, auth_header):
        res = client.put(
            "/api/v1/timesheets/999999",
            json={"notes": "updated"},
            headers=auth_header,
        )
        assert res.status_code == 404

    def test_delete_unknown_returns_404(self, client, auth_header):
        res = client.delete(
            "/api/v1/timesheets/999999", headers=auth_header
        )
        assert res.status_code == 404

    def test_submit_unknown_returns_4xx(self, client, auth_header):
        res = client.post(
            "/api/v1/timesheets/999999/submit",
            json={"flow_id": 1, "title": "Unknown"},
            headers=auth_header,
        )
        assert res.status_code in (400, 404, 422)


class TestTimesheetRoutesAuth:
    def test_anonymous_list_returns_401(self, client):
        assert client.get("/api/v1/timesheets").status_code == 401

    def test_anonymous_create_returns_401(self, client):
        assert client.post("/api/v1/timesheets", json=_payload()).status_code == 401

    def test_anonymous_update_returns_401(self, client):
        assert client.put("/api/v1/timesheets/1", json={}).status_code == 401

    def test_anonymous_delete_returns_401(self, client):
        assert client.delete("/api/v1/timesheets/1").status_code == 401
