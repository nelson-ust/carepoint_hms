# app/tests/integration/test_billing_routes.py
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
    p_payload = {"first_name": _unique("Bill"), "last_name": "Patient", "hospital_number": _unique("BL-HN"), "gender": "MALE"}
    p_res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", json=p_payload, headers=auth_header)
    patient_id = p_res.json()["patient_id"]
    sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdp_id = sdp_res.json()["items"][0]["id"]
    v_payload = {"patient_id": patient_id, "first_service_delivery_point_id": sdp_id}
    v_res = client.post("/api/v1/visits/initiate", json=v_payload, headers=auth_header)
    return v_res.json()["visit"]

class TestBillingRoutes:
    def test_list_billing_services(self, client, auth_header):
        response = client.get("/api/v1/billing/services", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def _create_billing_record(self, client, auth_header, test_visit):
        # 1. Get a service from catalog
        svc_res = client.get("/api/v1/billing/services", headers=auth_header)
        if not svc_res.json()["items"]:
            # Create one if none
            svc_payload = {"code": _unique("SCODE"), "name": "Consultation Fee", "default_price": 2000}
            svc_res = client.post("/api/v1/billing/services", json=svc_payload, headers=auth_header)
            svc = svc_res.json()["service"]
        else:
            svc = svc_res.json()["items"][0]

        # 2. Create billing
        payload = {
            "visit_id": test_visit["id"],
            "patient_id": test_visit["patient_id"],
            "items": [
                {
                    "billable_service_id": svc["id"],
                    "service_name": svc["name"],
                    "quantity": 1,
                    "unit_price": svc["default_price"]
                }
            ]
        }
        response = client.post("/api/v1/billing/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        return data["billing"]


    def test_create_billing_record(self, client, auth_header, test_visit):
        self._create_billing_record(client, auth_header, test_visit)

    def test_get_billing_by_visit(self, client, auth_header, test_visit):
        self._create_billing_record(client, auth_header, test_visit)
        response = client.get(f"/api/v1/billing/visits/{test_visit['id']}", headers=auth_header)
        assert response.status_code == 200
        assert len(response.json()) > 0

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/billing/services")
        assert response.status_code == 401
