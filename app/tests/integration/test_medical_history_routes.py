# app/tests/integration/test_medical_history_routes.py
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

@pytest.fixture()
def test_patient(client, auth_header):
    payload = {
        "first_name": _unique("History"),
        "last_name": "Patient",
        "hospital_number": _unique("HIST-HN"),
        "gender": "FEMALE"
    }
    res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", json=payload, headers=auth_header)
    return res.json()

class TestMedicalHistoryRoutes:
    def test_get_patient_history(self, client, auth_header, test_patient):
        patient_id = test_patient["patient_id"]
        # Add a structured allergy first
        client.post(
            f"/api/v1/patients/{patient_id}/allergies",
            json={"allergen_name": "Pollen", "severity": "MILD"},
            headers=auth_header
        )

        response = client.get(f"/api/v1/patients/{patient_id}/medical-history", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "history" in data
        
        history = data["history"]
        assert "chronic_conditions" in history["patient"]
        assert "structured_allergies" in history
        assert len(history["structured_allergies"]) >= 1
        assert history["structured_allergies"][0]["allergen_name"] == "Pollen"

    def test_get_history_for_visit(self, client, auth_header, test_patient):
        # Create visit
        # Get SDP
        sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
        sdp_id = sdp_res.json()["items"][0]["id"]
        
        v_payload = {
            "patient_id": test_patient["patient_id"],
            "first_service_delivery_point_id": sdp_id
        }
        v_res = client.post("/api/v1/visits/initiate", json=v_payload, headers=auth_header)
        visit_id = v_res.json()["visit"]["id"]

        response = client.get(f"/api/v1/visits/{visit_id}/medical-history", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "history" in data
