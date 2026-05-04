# app/tests/integration/test_admission_routes.py
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
    p_payload = {"first_name": _unique("Admit"), "last_name": "Patient", "hospital_number": _unique("ADM-HN"), "gender": "MALE"}
    p_res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", json=p_payload, headers=auth_header)
    patient_id = p_res.json()["patient_id"]
    sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdp_id = sdp_res.json()["items"][0]["id"]
    v_payload = {"patient_id": patient_id, "first_service_delivery_point_id": sdp_id}
    v_res = client.post("/api/v1/visits/initiate", json=v_payload, headers=auth_header)
    return v_res.json()["visit"]

@pytest.fixture()
def test_ward(client, auth_header):
    payload = {"name": _unique("Admission Ward"), "code": _unique("AWRD"), "ward_type": "GENERAL"}
    res = client.post("/api/v1/wards/", json=payload, headers=auth_header)
    return res.json()

@pytest.fixture()
def test_bed(client, auth_header, test_ward):
    payload = {"ward_id": test_ward["id"], "bed_no": _unique("ABED"), "bed_status": "AVAILABLE", "bed_type": "STANDARD"}
    res = client.post("/api/v1/beds/", json=payload, headers=auth_header)
    return res.json()


class TestAdmissionRoutes:
    def _create_admission(self, client, auth_header, test_visit, test_bed):
        payload = {
            "visit_id": test_visit["id"],
            "patient_id": test_visit["patient_id"],
            "ward_id": test_bed["ward_id"],
            "bed_id": test_bed["id"],
            "admission_reason": "Surgery recovery"
        }
        response = client.post("/api/v1/admissions/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        # Response is wrapped: {"success": true, "admission": {...}}
        admission = data.get("admission", data)
        assert admission["admission_reason"] == "Surgery recovery"
        return admission

    def test_create_admission(self, client, auth_header, test_visit, test_bed):
        self._create_admission(client, auth_header, test_visit, test_bed)

    def test_get_admission(self, client, auth_header, test_visit, test_bed):
        adm = self._create_admission(client, auth_header, test_visit, test_bed)
        adm_id = adm["id"]
        response = client.get(f"/api/v1/admissions/{adm_id}", headers=auth_header)
        assert response.status_code == 200
        assert response.json()["id"] == adm_id

    def test_list_admissions(self, client, auth_header, test_visit, test_bed):
        self._create_admission(client, auth_header, test_visit, test_bed)
        response = client.get("/api/v1/admissions/", headers=auth_header)
        assert response.status_code == 200

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/admissions/")
        assert response.status_code == 401
