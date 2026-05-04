# app/tests/integration/test_invoice_routes.py
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
def test_billing(client, auth_header):
    p_payload = {"first_name": _unique("Inv"), "last_name": "Patient", "hospital_number": _unique("INV-HN"), "gender": "MALE"}
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
        "items": [{"service_name": "Consultation Fee", "quantity": 1, "unit_price": 500}]
    }
    b_res = client.post("/api/v1/billing/", json=b_payload, headers=auth_header)
    b_data = b_res.json()
    return b_data.get("billing", b_data)

class TestInvoiceRoutes:
    def _issue_invoice_from_billing(self, client, auth_header, test_billing):
        payload = {"billing_id": test_billing["id"]}
        response = client.post("/api/v1/invoices/issue-from-billing", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "invoice" in data
        return data["invoice"]


    def test_issue_invoice_from_billing(self, client, auth_header, test_billing):
        self._issue_invoice_from_billing(client, auth_header, test_billing)

    def test_get_invoice_by_visit(self, client, auth_header, test_billing):
        self._issue_invoice_from_billing(client, auth_header, test_billing)
        response = client.get(f"/api/v1/invoices/visits/{test_billing['visit_id']}", headers=auth_header)
        assert response.status_code == 200

    def test_reject_anonymous(self, client):
        response = client.post("/api/v1/invoices/issue-from-billing", json={})
        assert response.status_code in (401, 422)
