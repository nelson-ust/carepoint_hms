# app/tests/integration/test_patient_routes.py
from __future__ import annotations

import pytest
import uuid
from datetime import date
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


def _create_patient(client, auth_header, **overrides):
    """Helper to create a patient with unique data, bypassing duplicate detection."""
    defaults = {
        "first_name": _unique("FN"),
        "last_name": _unique("LN"),
        "hospital_number": _unique("HOSP"),
        "gender": "MALE",
    }
    defaults.update(overrides)
    response = client.post(
        "/api/v1/patients/?force_create_if_possible_duplicate=true",
        json=defaults,
        headers=auth_header,
    )
    return response


class TestPatientLifecycle:
    def test_create_patient(self, client, auth_header):
        response = _create_patient(
            client, auth_header,
            date_of_birth="1990-01-01",
            phone_number="1234567890",
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "patient_id" in data
        assert "hospital_number" in data
        assert data["message"] == "Patient registered successfully."

    def test_get_patient(self, client, auth_header):
        # First create
        create_res = _create_patient(client, auth_header, gender="FEMALE")
        assert create_res.status_code == 201
        patient_id = create_res.json()["patient_id"]

        # Then fetch
        response = client.get(f"/api/v1/patients/{patient_id}", headers=auth_header)
        assert response.status_code == 200
        assert response.json()["id"] == patient_id

    def test_update_patient(self, client, auth_header):
        create_res = _create_patient(client, auth_header, gender="OTHER")
        assert create_res.status_code == 201
        patient_id = create_res.json()["patient_id"]

        update_payload = {"first_name": _unique("Updated")}
        response = client.put(f"/api/v1/patients/{patient_id}", json=update_payload, headers=auth_header)
        assert response.status_code == 200
        assert response.json()["first_name"] == update_payload["first_name"]

    def test_search_patients(self, client, auth_header):
        unique_name = _unique("SearchTarget")
        _create_patient(client, auth_header, first_name=unique_name, last_name="Doe")

        response = client.get(f"/api/v1/patients/search?full_name={unique_name}", headers=auth_header)
        assert response.status_code == 200
        results = response.json()["items"]
        assert len(results) > 0
