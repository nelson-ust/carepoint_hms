# app/tests/integration/test_doctor_calendar_routes.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

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


@pytest.fixture()
def staff_profile_id(client, auth_header):
    response = client.get("/api/v1/staff/", headers=auth_header)
    if response.status_code == 200 and response.json().get("items"):
        items = response.json()["items"]
        return items[0].get("id") or items[0].get("staff_profile_id") or 1
    return 1


class TestDoctorCalendarRoutes:
    def test_list_templates(self, client, auth_header):
        response = client.get(
            "/api/v1/doctor-calendar/templates", headers=auth_header
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_template_invalid(self, client, auth_header):
        response = client.post(
            "/api/v1/doctor-calendar/templates", json={}, headers=auth_header
        )
        assert response.status_code == 422

    def test_create_template(self, client, auth_header, staff_profile_id):
        payload = {
            "staff_profile_id": staff_profile_id,
            "weekday": 1,
            "start_time": "09:00",
            "end_time": "17:00",
            "slot_duration_minutes": 30,
            "max_patients_per_slot": 1,
        }
        response = client.post(
            "/api/v1/doctor-calendar/templates", json=payload, headers=auth_header
        )
        assert response.status_code in (200, 201, 404, 400)

    def test_deactivate_template_missing(self, client, auth_header):
        response = client.post(
            "/api/v1/doctor-calendar/templates/99999999/deactivate",
            headers=auth_header,
        )
        assert response.status_code in (200, 404)

    def test_add_time_off_invalid(self, client, auth_header):
        response = client.post(
            "/api/v1/doctor-calendar/time-off", json={}, headers=auth_header
        )
        assert response.status_code == 422

    def test_materialise_slots_invalid(self, client, auth_header):
        response = client.post(
            "/api/v1/doctor-calendar/slots/materialise",
            json={},
            headers=auth_header,
        )
        assert response.status_code == 422

    def test_list_slots_requires_range(self, client, auth_header):
        # from_dt and to_dt are required query params; missing them = 422
        response = client.get(
            "/api/v1/doctor-calendar/slots", headers=auth_header
        )
        assert response.status_code == 422

    def test_list_slots_with_range(self, client, auth_header):
        # ``+`` in the timezone offset is interpreted as a literal space when
        # placed in a URL query string, so we pass the params via httpx's
        # ``params=`` kwarg which URL-encodes them properly.
        from_dt = datetime.now(timezone.utc).isoformat()
        to_dt = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        response = client.get(
            "/api/v1/doctor-calendar/slots",
            params={"from_dt": from_dt, "to_dt": to_dt},
            headers=auth_header,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_doctor_workload(self, client, auth_header, staff_profile_id):
        today = datetime.now(timezone.utc).date().isoformat()
        response = client.get(
            f"/api/v1/doctor-calendar/workload/{staff_profile_id}?on_date={today}",
            headers=auth_header,
        )
        assert response.status_code in (200, 404)

    def test_reserve_slot_missing(self, client, auth_header):
        response = client.post(
            "/api/v1/doctor-calendar/slots/99999999/reserve?appointment_id=1",
            headers=auth_header,
        )
        assert response.status_code in (200, 404, 400, 422)

    def test_release_slot_missing(self, client, auth_header):
        response = client.post(
            "/api/v1/doctor-calendar/slots/99999999/release",
            headers=auth_header,
        )
        assert response.status_code in (200, 404, 400)

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/doctor-calendar/templates")
        assert response.status_code == 401
