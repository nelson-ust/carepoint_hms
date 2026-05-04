# app/tests/integration/test_triage_routes.py
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
def test_visit(client, auth_header):
    # Create patient
    p_payload = {"first_name": _unique("Triage"), "last_name": "Patient", "hospital_number": _unique("TR-HN"), "gender": "MALE"}
    p_res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", json=p_payload, headers=auth_header)
    patient_id = p_res.json()["patient_id"]
    
    # Get SDP
    sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdp_id = sdp_res.json()["items"][0]["id"]
    
    v_payload = {"patient_id": patient_id, "first_service_delivery_point_id": sdp_id}
    v_res = client.post("/api/v1/visits/initiate", json=v_payload, headers=auth_header)
    return v_res.json()["visit"]

class TestTriageRoutes:
    def _create_triage(self, client, auth_header, test_visit):
        payload = {
            "visit_id": test_visit["id"],
            "patient_id": test_visit["patient_id"],
            "chief_complaint": "Headache",
            "priority": "NORMAL"
        }
        response = client.post("/api/v1/triage/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        # Response is wrapped: {"success": true, "triage": {...}}
        triage = data.get("triage", data)
        assert triage["chief_complaint"] == "Headache"
        return triage


    def test_create_triage(self, client, auth_header, test_visit):
        self._create_triage(client, auth_header, test_visit)

    def test_get_triage_by_visit(self, client, auth_header, test_visit):
        self._create_triage(client, auth_header, test_visit)
        response = client.get(f"/api/v1/triage/visits/{test_visit['id']}", headers=auth_header)
        assert response.status_code == 200

    def test_update_triage(self, client, auth_header, test_visit):
        triage = self._create_triage(client, auth_header, test_visit)
        triage_id = triage["id"]
        payload = {"chief_complaint": "Severe Headache"}
        response = client.put(f"/api/v1/triage/{triage_id}", json=payload, headers=auth_header)
        assert response.status_code == 200

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/triage/visits/1")
        assert response.status_code == 401
