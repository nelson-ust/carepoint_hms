# app/tests/integration/test_lab_result_routes.py
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
def test_lab_order(client, auth_header):
    # Setup visit
    p_payload = {"first_name": _unique("Res"), "last_name": "Patient", "hospital_number": _unique("R-HN"), "gender": "MALE"}
    p_res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", json=p_payload, headers=auth_header)
    patient_id = p_res.json()["patient_id"]
    sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdp_id = sdp_res.json()["items"][0]["id"]
    v_payload = {"patient_id": patient_id, "first_service_delivery_point_id": sdp_id}
    v_res = client.post("/api/v1/visits/initiate", json=v_payload, headers=auth_header)
    visit_id = v_res.json()["visit"]["id"]
    
    # Get lab test
    cat_res = client.get("/api/v1/lab/tests/", headers=auth_header)
    items = cat_res.json().get("items", [])
    if not items:
        cat_payload = {"code": _unique("LRCODE"), "name": "Result Test", "default_price": 2000}
        cat_res = client.post("/api/v1/lab/tests/", json=cat_payload, headers=auth_header)
        test_id = cat_res.json().get("id") or cat_res.json().get("lab_test", {}).get("id")
    else:
        test_id = items[0]["id"]
        
    # Create order
    ord_payload = {
        "visit_id": visit_id,
        "items": [{"lab_test_catalog_id": test_id}]
    }
    ord_res = client.post("/api/v1/lab/orders/", json=ord_payload, headers=auth_header)
    return ord_res.json()["lab_order"]

class TestLabResultRoutes:
    def _create_lab_result(self, client, auth_header, test_lab_order):
        item_id = test_lab_order["items"][0]["id"]
        payload = {
            "lab_order_item_id": item_id,
            "result_value": "Negative",
            "reference_range": "Negative",
            "unit": "N/A",
            "is_abnormal": False
        }
        response = client.post("/api/v1/lab/results/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        return data["result"]


    def test_create_lab_result(self, client, auth_header, test_lab_order):
        self._create_lab_result(client, auth_header, test_lab_order)

    def test_get_result_by_item(self, client, auth_header, test_lab_order):
        self._create_lab_result(client, auth_header, test_lab_order)
        item_id = test_lab_order["items"][0]["id"]
        response = client.get(f"/api/v1/lab/results/by-item/{item_id}", headers=auth_header)
        assert response.status_code == 200

    def test_verify_result(self, client, auth_header, test_lab_order):
        res = self._create_lab_result(client, auth_header, test_lab_order)
        res_id = res["id"]
        payload = {"verification_note": "Confirmed accurate"}
        response = client.post(f"/api/v1/lab/results/{res_id}/verify", json=payload, headers=auth_header)
        assert response.status_code == 200

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/lab/results/by-item/1")
        assert response.status_code == 401
