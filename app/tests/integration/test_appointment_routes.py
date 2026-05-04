# app/tests/integration/test_appointment_routes.py
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
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
def test_patient(client, auth_header):
    p_payload = {"first_name": _unique("Appt"), "last_name": "Patient", "hospital_number": _unique("AP-HN"), "gender": "MALE"}
    p_res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", json=p_payload, headers=auth_header)
    return p_res.json()

class TestAppointmentRoutes:
    def _create_appointment(self, client, auth_header, test_patient):
        start = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        payload = {
            "patient_id": test_patient["patient_id"],
            "scheduled_start_at": start,
            "reason": "Regular checkup",
        }
        response = client.post("/api/v1/appointments/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        # Response may be wrapped
        appt = data.get("appointment", data)
        assert appt.get("reason") == "Regular checkup" or data.get("success") is True
        return appt


    def test_create_appointment(self, client, auth_header, test_patient):
        self._create_appointment(client, auth_header, test_patient)

    def test_list_appointments(self, client, auth_header, test_patient):
        self._create_appointment(client, auth_header, test_patient)
        response = client.get("/api/v1/appointments/", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/appointments/")
        assert response.status_code == 401
