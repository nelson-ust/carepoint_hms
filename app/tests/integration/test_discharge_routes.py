# app/tests/integration/test_discharge_routes.py
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
def test_admission(client, auth_header):
    # Setup patient, visit, ward, bed
    p_payload = {"first_name": _unique("Disch"), "last_name": "Patient", "hospital_number": _unique("DC-HN"), "gender": "MALE"}
    p_res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", json=p_payload, headers=auth_header)
    patient_id = p_res.json()["patient_id"]
    sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdp_id = sdp_res.json()["items"][0]["id"]
    v_payload = {"patient_id": patient_id, "first_service_delivery_point_id": sdp_id}
    v_res = client.post("/api/v1/visits/initiate", json=v_payload, headers=auth_header)
    visit_id = v_res.json()["visit"]["id"]
    
    w_payload = {"name": _unique("DC Ward"), "code": _unique("DWRD"), "ward_type": "GENERAL"}
    w_res = client.post("/api/v1/wards/", json=w_payload, headers=auth_header)
    ward_id = w_res.json()["id"]
    
    b_payload = {"ward_id": ward_id, "bed_no": _unique("DBED"), "bed_status": "AVAILABLE", "bed_type": "STANDARD"}
    b_res = client.post("/api/v1/beds/", json=b_payload, headers=auth_header)
    bed_id = b_res.json()["id"]

    
    adm_payload = {
        "visit_id": visit_id,
        "patient_id": patient_id,
        "ward_id": ward_id,
        "bed_id": bed_id,
        "admission_reason": "Test"
    }
    adm_res = client.post("/api/v1/admissions/", json=adm_payload, headers=auth_header)
    adm_data = adm_res.json()
    return adm_data.get("admission", adm_data)

class TestDischargeRoutes:
    def _create_discharge(self, client, auth_header, test_admission):
        payload = {
            "admission_id": test_admission["id"],
            "patient_id": test_admission["patient_id"],
            "discharge_type": "ROUTINE",
            "discharge_summary": "Patient recovered",
            "follow_up_instructions": "Rest"
        }
        response = client.post("/api/v1/discharges/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "discharge" in data
        return data["discharge"]


    def test_create_discharge(self, client, auth_header, test_admission):
        self._create_discharge(client, auth_header, test_admission)

    def test_get_discharge_by_admission(self, client, auth_header, test_admission):
        self._create_discharge(client, auth_header, test_admission)
        response = client.get(f"/api/v1/discharges/admissions/{test_admission['id']}", headers=auth_header)
        assert response.status_code == 200
        assert response.json()["admission_id"] == test_admission["id"]

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/discharges/admissions/1")
        assert response.status_code == 401
