# app/tests/integration/test_patient_portal_routes.py
from __future__ import annotations

import pytest
from unittest.mock import patch
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
    # 1. Create Patient with unique names + force_create
    h_no = _unique("PORTAL-PAT")
    p_res = client.post(
        "/api/v1/patients/?force_create_if_possible_duplicate=true",
        json={
            "first_name": _unique("Portal"),
            "last_name": _unique("User"),
            "hospital_number": h_no,
            "gender": "MALE",
            "email": f"{h_no}@example.com",
        },
        headers=auth_header,
    )
    return p_res.json()

class TestPatientPortal:
    def test_otp_login_and_dashboard(self, client, test_patient):
        # 1. Request OTP
        # We mock _generate_otp to return a known value
        with patch("app.services.patient_portal_auth_service._generate_otp", return_value="12345"):
            req_res = client.post("/api/v1/portal/auth/request-otp", json={
                "identifier": test_patient["hospital_number"]
            })
            assert req_res.status_code == 200
            otp_id = req_res.json()["otp_id"]

            # 2. Verify OTP
            ver_res = client.post("/api/v1/portal/auth/verify-otp", json={
                "otp_id": otp_id,
                "otp_code": "12345"
            })
            assert ver_res.status_code == 200
            portal_token = ver_res.json()["tokens"]["access_token"]
            portal_header = _bearer_headers(portal_token)

            # 3. Access Dashboard
            dash_res = client.get("/api/v1/portal/dashboard", headers=portal_header)
            assert dash_res.status_code == 200
            data = dash_res.json()
            assert "recent_lab_results" in data
            assert "wallet_balance" in data

    def test_fund_card_no_card_fail(self, client, test_patient):
        # Login first
        with patch("app.services.patient_portal_auth_service._generate_otp", return_value="54321"):
            req_res = client.post("/api/v1/portal/auth/request-otp", json={
                "identifier": test_patient["hospital_number"]
            })
            otp_id = req_res.json()["otp_id"]
            ver_res = client.post("/api/v1/portal/auth/verify-otp", json={
                "otp_id": otp_id, "otp_code": "54321"
            })
            portal_token = ver_res.json()["tokens"]["access_token"]
            portal_header = _bearer_headers(portal_token)

            # Try to fund card (should fail as no card is assigned yet)
            fund_res = client.post("/api/v1/portal/fund-card", json={"amount": 1000}, headers=portal_header)
            assert fund_res.status_code == 404
            assert "No membership card found" in fund_res.json()["detail"]
