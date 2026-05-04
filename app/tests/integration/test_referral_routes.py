# app/tests/integration/test_referral_routes.py
from __future__ import annotations

"""
Integration tests for the patient referral module.
"""

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
    hospital_number = _unique("REF-PAT")
    payload = {
        "first_name": _unique("Referral"),
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
def test_visit(client, auth_header, test_patient):
    # Get an SDP
    sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdps = sdp_res.json()["items"]
    sdp_id = sdps[0]["id"] if sdps else 1
    
    payload = {
        "patient_id": test_patient["patient_id"],
        "first_service_delivery_point_id": sdp_id
    }
    res = client.post("/api/v1/visits/initiate", json=payload, headers=auth_header)
    return res.json()["visit"]

class TestReferralWorkflow:
    def test_create_referral(self, client, auth_header, test_patient, test_visit):
        payload = {
            "patient_id": test_patient["patient_id"],
            "visit_id": test_visit["id"],
            "destination_facility": "General Hospital",
            "reason_for_referral": "Specialized care required",
            "clinical_summary": "Patient needs ENT specialist.",
            "priority": "HIGH"
        }
        response = client.post("/api/v1/referrals/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["referral"]["destination_facility"] == "General Hospital"
        assert data["referral"]["referral_no"].startswith("REF-")

    def test_list_referrals(self, client, auth_header, test_patient, test_visit):
        # Create a referral first
        payload = {
            "patient_id": test_patient["patient_id"],
            "visit_id": test_visit["id"],
            "destination_facility": "Clinic B",
            "reason_for_referral": "Test"
        }
        client.post("/api/v1/referrals/", json=payload, headers=auth_header)

        response = client.get("/api/v1/referrals/", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0

    def test_update_referral(self, client, auth_header, test_patient, test_visit):
        # Create a referral
        payload = {
            "patient_id": test_patient["patient_id"],
            "visit_id": test_visit["id"],
            "destination_facility": "Initial Facility",
            "reason_for_referral": "Initial Reason"
        }
        res = client.post("/api/v1/referrals/", json=payload, headers=auth_header)
        referral_id = res.json()["referral"]["id"]

        # Update
        update_payload = {
            "destination_facility": "Updated Facility",
            "priority": "URGENT"
        }
        response = client.patch(f"/api/v1/referrals/{referral_id}", json=update_payload, headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["referral"]["destination_facility"] == "Updated Facility"
        assert data["referral"]["priority"] == "URGENT"

    def test_cancel_referral(self, client, auth_header, test_patient, test_visit):
        # Create a referral
        payload = {
            "patient_id": test_patient["patient_id"],
            "visit_id": test_visit["id"],
            "destination_facility": "Facility to Cancel",
            "reason_for_referral": "Reason"
        }
        res = client.post("/api/v1/referrals/", json=payload, headers=auth_header)
        referral_id = res.json()["referral"]["id"]

        # Cancel
        response = client.post(f"/api/v1/referrals/{referral_id}/cancel", params={"reason": "Mistake"}, headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["referral"]["status"] == "CANCELLED"
