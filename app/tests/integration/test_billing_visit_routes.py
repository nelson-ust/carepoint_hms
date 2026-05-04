# app/tests/integration/test_billing_visit_routes.py
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
    # 1. Create Patient with unique names + force_create
    h_no = _unique("BILL-PAT")
    p_res = client.post(
        "/api/v1/patients/?force_create_if_possible_duplicate=true",
        json={
            "first_name": _unique("Billing"),
            "last_name": _unique("Patient"),
            "hospital_number": h_no,
            "gender": "FEMALE",
        },
        headers=auth_header,
    )
    patient = p_res.json()

    # 2. Get SDP
    sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdp_id = sdp_res.json()["items"][0]["id"]

    # 3. Initiate Visit
    v_res = client.post("/api/v1/visits/initiate", json={
        "patient_id": patient["patient_id"],
        "first_service_delivery_point_id": sdp_id
    }, headers=auth_header)
    return v_res.json()["visit"]

class TestBillingWorkflow:
    def test_full_billing_payment_cycle(self, client, auth_header, test_visit):
        # 1. Create Billable Service
        s_payload = {
            "code": _unique("CONS"),
            "name": _unique("General Consultation"),
            "category": "CONSULTATION",
            "default_price": 5000.0
        }
        s_res = client.post("/api/v1/billing/services", json=s_payload, headers=auth_header)
        service_id = s_res.json()["service"]["id"]

        # 2. Create Billing (Charges)
        b_payload = {
            "patient_id": test_visit["patient_id"],
            "visit_id": test_visit["id"],
            "items": [{"billable_service_id": service_id, "service_name": s_payload["name"], "quantity": 1, "unit_price": 5000.0}]
        }
        b_res = client.post("/api/v1/billing/", json=b_payload, headers=auth_header)
        assert b_res.status_code == 201
        billing_id = b_res.json()["billing"]["id"]

        # 3. Issue Invoice
        inv_payload = {"billing_id": billing_id}
        inv_res = client.post("/api/v1/invoices/issue-from-billing", json=inv_payload, headers=auth_header)
        assert inv_res.status_code == 201
        invoice_id = inv_res.json()["invoice"]["id"]
        total_amount = inv_res.json()["invoice"]["total_amount"]

        # 4. Receive Payment (Partial - Cash)
        p1_payload = {
            "invoice_id": invoice_id,
            "payment_method": "CASH",
            "amount": 2000.0,
            "note": "Initial deposit"
        }
        p1_res = client.post("/api/v1/payments/", json=p1_payload, headers=auth_header)
        assert p1_res.status_code == 201
        
        # Verify invoice balance
        inv_check = client.get(f"/api/v1/invoices/{invoice_id}", headers=auth_header)
        assert float(inv_check.json()["amount_paid"]) == 2000.0
        assert inv_check.json()["status"] == "PARTIALLY_PAID"

        # 5. Receive Payment (Remaining - Bank Transfer)
        p2_payload = {
            "invoice_id": invoice_id,
            "payment_method": "BANK_TRANSFER",
            "amount": float(total_amount) - 2000.0,
            "note": "Balance clear",
            "payment_reference": "BT-12345"
        }
        p2_res = client.post("/api/v1/payments/", json=p2_payload, headers=auth_header)
        assert p2_res.status_code == 201
        
        # Verify invoice status
        inv_final = client.get(f"/api/v1/invoices/{invoice_id}", headers=auth_header)
        assert float(inv_final.json()["balance_due"]) == 0
        assert inv_final.json()["status"] == "PAID"
