# app/tests/integration/test_diagnosis_routes.py
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
    p_payload = {"first_name": _unique("Diag"), "last_name": "Patient", "hospital_number": _unique("D-HN"), "gender": "MALE"}
    p_res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", json=p_payload, headers=auth_header)
    patient_id = p_res.json()["patient_id"]
    sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdp_id = sdp_res.json()["items"][0]["id"]
    v_payload = {"patient_id": patient_id, "first_service_delivery_point_id": sdp_id}
    v_res = client.post("/api/v1/visits/initiate", json=v_payload, headers=auth_header)
    return v_res.json()["visit"]

class TestDiagnosisRoutes:
    def _create_diagnosis(self, client, auth_header, test_visit):
        payload = {
            "visit_id": test_visit["id"],
            "diagnosis_code": "J00",
            "diagnosis_name": "Common cold",
            "diagnosis_type": "PRELIMINARY"
        }
        response = client.post("/api/v1/diagnoses/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["diagnosis"]["diagnosis_code"] == "J00"
        return data["diagnosis"]


    def test_create_diagnosis(self, client, auth_header, test_visit):
        self._create_diagnosis(client, auth_header, test_visit)

    def test_get_diagnosis_by_visit(self, client, auth_header, test_visit):
        self._create_diagnosis(client, auth_header, test_visit)
        response = client.get(f"/api/v1/diagnoses/visits/{test_visit['id']}", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) > 0

    def test_update_diagnosis(self, client, auth_header, test_visit):
        diag = self._create_diagnosis(client, auth_header, test_visit)
        diag_id = diag["id"]
        payload = {"diagnosis_type": "FINAL"}
        response = client.put(f"/api/v1/diagnoses/{diag_id}", json=payload, headers=auth_header)
        assert response.status_code == 200
        assert response.json()["diagnosis"]["diagnosis_type"] == "FINAL"

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/diagnoses/visits/1")
        assert response.status_code == 401
