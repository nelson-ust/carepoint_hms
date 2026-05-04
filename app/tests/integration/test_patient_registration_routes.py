# app/tests/integration/test_patient_registration_routes.py
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

class TestPatientRegistrationRoutes:
    def test_initiate_visit_new_patient(self, client, auth_header):
        """Unified flow: register a brand-new patient and initiate a visit."""
        sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
        sdp_id = sdp_res.json()["items"][0]["id"]

        payload = {
            "new_patient": {
                "first_name": _unique("Reg"),
                "last_name": "Patient",
                "hospital_number": _unique("REG-HN"),
                "gender": "MALE",
            },
            "options": {
                "first_service_delivery_point_id": sdp_id,
                "visit_reason": "New Registration",
            }
        }
        response = client.post("/api/v1/patient-registration/initiate-visit", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        # Response uses flat keys: patient_id, visit_id (not nested)
        assert data["patient_id"] is not None

    def test_initiate_visit_returning_patient(self, client, auth_header):
        """Unified flow: look up a returning patient by hospital number."""
        # First create a patient
        hn = _unique("RET-HN")
        p_payload = {"first_name": _unique("Ret"), "last_name": "Patient", "hospital_number": hn, "gender": "MALE"}
        p_res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", json=p_payload, headers=auth_header)
        assert p_res.status_code == 201
        # Use the hospital_number as returned by the server (may be normalized)
        actual_hn = p_res.json().get("hospital_number", hn)

        sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
        sdp_id = sdp_res.json()["items"][0]["id"]

        payload = {
            "existing_patient": {"hospital_number": actual_hn},
            "options": {
                "first_service_delivery_point_id": sdp_id,
                "visit_reason": "Follow-up visit",
            }
        }
        response = client.post("/api/v1/patient-registration/initiate-visit", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
