# app/tests/integration/test_appointment_extension_routes.py
from __future__ import annotations

import pytest
from app.tests.conftest import HAS_TEST_DB
from app.tests.integration.test_auth_routes import _login, _bearer_headers, _unique

pytestmark = pytest.mark.skipif(
    not HAS_TEST_DB,
    reason="CAREPOINT_HMS_DATABASE_URL not configured for integration tests.",
)


@pytest.fixture()
def auth_header(client, admin_user):
    login_res = _login(client, admin_user["username"], admin_user["password"])
    token = login_res.json()["tokens"]["access_token"]
    return _bearer_headers(token)


class TestAppointmentExtensionRoutes:
    def test_schedule_reminders_unknown_appointment(self, client, auth_header):
        # Routes return [] when appointment not found rather than 404
        payload = {"appointment_id": 99999999, "rules": ["H24_BEFORE", "H2_BEFORE"]}
        response = client.post(
            "/api/v1/appointment-scheduling/reminders/schedule",
            json=payload,
            headers=auth_header,
        )
        assert response.status_code in (200, 201)
        assert response.json() == []

    def test_dispatch_due_reminders(self, client, auth_header):
        response = client.post(
            "/api/v1/appointment-scheduling/reminders/dispatch-due",
            headers=auth_header,
        )
        assert response.status_code in (200, 201)

    def test_log_history_invalid_action_returns_422(self, client, auth_header):
        payload = {"action": "BAD"}
        response = client.post(
            "/api/v1/appointment-scheduling/history/1/log",
            json=payload,
            headers=auth_header,
        )
        assert response.status_code == 422

    def test_read_history_returns_list(self, client, auth_header):
        response = client.get(
            "/api/v1/appointment-scheduling/history/1",
            headers=auth_header,
        )
        # Service returns [] for unknown appointment, or 200 with list
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            assert isinstance(response.json(), list)

    def test_create_recurrence_invalid_body_422(self, client, auth_header):
        response = client.post(
            "/api/v1/appointment-scheduling/recurrence",
            json={},
            headers=auth_header,
        )
        assert response.status_code == 422

    def test_expand_recurrence_unknown_rule(self, client, auth_header):
        response = client.post(
            "/api/v1/appointment-scheduling/recurrence/99999999/expand",
            headers=auth_header,
        )
        assert response.status_code in (200, 201)
        assert response.json().get("created") == 0

    def test_reject_anonymous_schedule(self, client):
        response = client.post(
            "/api/v1/appointment-scheduling/reminders/schedule",
            json={"appointment_id": 1},
        )
        assert response.status_code == 401

    def test_reject_anonymous_history(self, client):
        response = client.get("/api/v1/appointment-scheduling/history/1")
        assert response.status_code == 401
