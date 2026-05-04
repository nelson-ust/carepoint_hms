# app/tests/integration/test_visit_routes.py
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
    hospital_number = _unique("VISIT-PAT")
    payload = {
        "first_name": _unique("Visit"),
        "last_name": _unique("Patient"),
        "hospital_number": hospital_number,
        "gender": "MALE"
    }
    res = client.post(
        "/api/v1/patients/?force_create_if_possible_duplicate=true",
        json=payload, headers=auth_header,
    )
    return res.json()

@pytest.fixture()
def test_sdp(client, auth_header):
    # Ensure at least one SDP exists or fetch one
    res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdps = res.json()["items"]
    if sdps:
        return sdps[0]
    
    # Create if none
    payload = {
        "name": "Test Clinic",
        "code": _unique("SDP-TEST"),
        "service_point_type": "CLINIC",
        "supports_walk_in": True
    }
    res = client.post("/api/v1/service-delivery-points/", json=payload, headers=auth_header)
    return res.json()

class TestVisitLifecycle:
    def test_initiate_visit(self, client, auth_header, test_patient, test_sdp):
        payload = {
            "patient_id": test_patient["patient_id"],
            "visit_reason": "Regular checkup",
            "priority": "NORMAL",
            "first_service_delivery_point_id": test_sdp["id"],
            "create_first_flow_step": True,
            "create_queue_ticket": True
        }
        response = client.post("/api/v1/visits/initiate", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["visit"]["patient_id"] == test_patient["patient_id"]
        assert data["first_flow_step"]["service_delivery_point_id"] == test_sdp["id"]
        assert data["first_queue_ticket"] is not None

    def test_get_visit_detailed(self, client, auth_header, test_patient, test_sdp):
        # Create visit
        init_payload = {
            "patient_id": test_patient["patient_id"],
            "first_service_delivery_point_id": test_sdp["id"]
        }
        init_res = client.post("/api/v1/visits/initiate", json=init_payload, headers=auth_header)
        visit_id = init_res.json()["visit"]["id"]

        # Get detailed
        response = client.get(f"/api/v1/visits/{visit_id}/detailed", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == visit_id
        assert "patient" in data
        assert "flow_steps" in data
        assert len(data["flow_steps"]) > 0

    def test_reroute_visit(self, client, auth_header, test_patient, test_sdp):
        # Create visit at first SDP
        init_payload = {
            "patient_id": test_patient["patient_id"],
            "first_service_delivery_point_id": test_sdp["id"]
        }
        init_res = client.post("/api/v1/visits/initiate", json=init_payload, headers=auth_header)
        visit_id = init_res.json()["visit"]["id"]

        # Create second SDP
        sdp2_payload = {
            "name": "Second Clinic",
            "code": _unique("SDP-REROUTE"),
            "service_point_type": "CLINIC"
        }
        sdp2_res = client.post("/api/v1/service-delivery-points/", json=sdp2_payload, headers=auth_header)
        sdp2_id = sdp2_res.json()["id"]

        # Reroute
        reroute_payload = {
            "service_delivery_point_id": sdp2_id,
            "reason": "Referral for tests",
            "create_queue_ticket": True
        }
        response = client.post(f"/api/v1/visits/{visit_id}/reroute", json=reroute_payload, headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["new_flow_step"]["service_delivery_point_id"] == sdp2_id

    def test_list_visits(self, client, auth_header, test_patient, test_sdp):
        # Ensure at least one visit exists
        client.post("/api/v1/visits/initiate", json={
            "patient_id": test_patient["patient_id"],
            "first_service_delivery_point_id": test_sdp["id"]
        }, headers=auth_header)

        response = client.get("/api/v1/visits/", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0
