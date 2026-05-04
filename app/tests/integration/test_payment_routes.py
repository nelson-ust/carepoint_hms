# app/tests/integration/test_payment_routes.py
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
def test_invoice(client, auth_header):
    # Setup patient, visit, billing, invoice
    p_payload = {"first_name": _unique("Pay"), "last_name": "Patient", "hospital_number": _unique("PAY-HN"), "gender": "MALE"}
    p_res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", json=p_payload, headers=auth_header)
    patient_id = p_res.json()["patient_id"]
    sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdp_id = sdp_res.json()["items"][0]["id"]
    v_payload = {"patient_id": patient_id, "first_service_delivery_point_id": sdp_id}
    v_res = client.post("/api/v1/visits/initiate", json=v_payload, headers=auth_header)
    visit_id = v_res.json()["visit"]["id"]

    b_payload = {
        "visit_id": visit_id,
        "patient_id": patient_id,
        "items": [{"service_name": "Payment Test Svc", "quantity": 1, "unit_price": 1000}]
    }
    b_res = client.post("/api/v1/billing/", json=b_payload, headers=auth_header)
    billing = b_res.json().get("billing", b_res.json())
    billing_id = billing["id"]

    inv_payload = {"billing_id": billing_id}
    inv_res = client.post("/api/v1/invoices/issue-from-billing", json=inv_payload, headers=auth_header)
    inv_data = inv_res.json()
    return inv_data.get("invoice", inv_data)

class TestPaymentRoutes:
    def _create_payment(self, client, auth_header, test_invoice):
        payload = {
            "invoice_id": test_invoice["id"],
            "amount": float(test_invoice.get("net_amount", test_invoice.get("total_amount", 1000))),
            "payment_method": "CASH",
        }
        response = client.post("/api/v1/payments/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "payment" in data
        return data["payment"]


    def test_create_payment(self, client, auth_header, test_invoice):
        self._create_payment(client, auth_header, test_invoice)

    def test_get_payment_by_invoice(self, client, auth_header, test_invoice):
        self._create_payment(client, auth_header, test_invoice)
        response = client.get(f"/api/v1/payments/invoices/{test_invoice['id']}", headers=auth_header)
        assert response.status_code == 200

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/payments/")
        assert response.status_code == 401
