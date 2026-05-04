# app/tests/integration/test_lab_order_routes.py
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
    p_payload = {"first_name": _unique("Lab"), "last_name": "Patient", "hospital_number": _unique("L-HN"), "gender": "MALE"}
    p_res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", json=p_payload, headers=auth_header)
    patient_id = p_res.json()["patient_id"]
    sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdp_id = sdp_res.json()["items"][0]["id"]
    v_payload = {"patient_id": patient_id, "first_service_delivery_point_id": sdp_id}
    v_res = client.post("/api/v1/visits/initiate", json=v_payload, headers=auth_header)
    return v_res.json()["visit"]

class TestLabOrderRoutes:
    def _create_lab_order(self, client, auth_header, test_visit):
        # 1. Get test from catalog
        cat_res = client.get("/api/v1/lab/tests/", headers=auth_header)
        items = cat_res.json().get("items", [])
        if not items:
            # Create one if none
            cat_payload = {"code": _unique("LCODE"), "name": "Test Lab", "default_price": 2000}
            cat_res = client.post("/api/v1/lab/tests/", json=cat_payload, headers=auth_header)
            test_id = cat_res.json().get("id") or cat_res.json().get("lab_test", {}).get("id")
        else:
            test_id = items[0]["id"]

        # 2. Create order
        payload = {
            "visit_id": test_visit["id"],
            "items": [{"lab_test_catalog_id": test_id}]
        }
        response = client.post("/api/v1/lab/orders/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        return data["lab_order"]


    def test_create_lab_order(self, client, auth_header, test_visit):
        self._create_lab_order(client, auth_header, test_visit)

    def test_get_order_by_visit(self, client, auth_header, test_visit):
        self._create_lab_order(client, auth_header, test_visit)
        response = client.get(f"/api/v1/lab/orders/visits/{test_visit['id']}", headers=auth_header)
        assert response.status_code == 200

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/lab/orders/worklist")
        assert response.status_code == 401
