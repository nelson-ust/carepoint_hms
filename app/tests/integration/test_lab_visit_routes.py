# app/tests/integration/test_lab_visit_routes.py
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
def test_data(client, auth_header):
    # 1. Create Patient with unique names + force_create
    h_no = _unique("LAB-PAT")
    p_res = client.post(
        "/api/v1/patients/?force_create_if_possible_duplicate=true",
        json={
            "first_name": _unique("Lab"),
            "last_name": _unique("Patient"),
            "hospital_number": h_no,
            "gender": "MALE",
            "email": f"{h_no}@example.com",
        },
        headers=auth_header,
    )
    patient = p_res.json()

    # 2. Get SDP
    sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdp_id = sdp_res.json()["items"][0]["id"]

    # 3. Create Lab Catalog Item
    catalog_payload = {
        "code": _unique("TEST"),
        "name": _unique("Malaria Parasite"),
        "sample_type": "BLOOD",
        "unit_of_measure": "per high power field",
        "default_price": 2500.0
    }
    cat_res = client.post("/api/v1/lab/tests/", json=catalog_payload, headers=auth_header)
    cat_data = cat_res.json()
    # Handle both response shapes: {"lab_test": {...}} or direct dict
    catalog_item = cat_data.get("lab_test", cat_data)

    # 4. Initiate Visit
    v_res = client.post("/api/v1/visits/initiate", json={
        "patient_id": patient["patient_id"],
        "first_service_delivery_point_id": sdp_id
    }, headers=auth_header)
    visit = v_res.json()["visit"]

    return {
        "patient": patient,
        "visit": visit,
        "catalog_item": catalog_item
    }

class TestLabWorkflow:
    def test_full_lab_cycle_to_portal(self, client, auth_header, test_data):
        patient = test_data["patient"]
        visit = test_data["visit"]
        catalog_item = test_data["catalog_item"]

        # 1. Create Lab Order
        order_payload = {
            "visit_id": visit["id"],
            "items": [{"lab_test_catalog_id": catalog_item["id"]}]
        }
        order_res = client.post("/api/v1/lab/orders/", json=order_payload, headers=auth_header)
        assert order_res.status_code == 201
        order = order_res.json()["lab_order"]
        item_id = order["items"][0]["id"]

        # 2. Collect Specimen
        coll_payload = {"specimen_id": "SPEC-123"}
        client.post(f"/api/v1/lab/orders/items/{item_id}/collect-specimen", json=coll_payload, headers=auth_header)

        # 3. Start Processing
        client.post(f"/api/v1/lab/orders/items/{item_id}/start-processing", json={}, headers=auth_header)

        # 4. Enter Result
        res_payload = {
            "lab_order_item_id": item_id,
            "result_value": "Negative",
            "result_text": "No parasites seen",
            "interpretation": "Normal"
        }
        enter_res = client.post("/api/v1/lab/results/", json=res_payload, headers=auth_header)
        assert enter_res.status_code == 201
        result_id = enter_res.json()["result"]["id"]

        # 5. Verify Result
        client.post(f"/api/v1/lab/results/{result_id}/verify", json={"notes": "Looks good"}, headers=auth_header)

        # 6. Release Result
        client.post(f"/api/v1/lab/results/{result_id}/release", json={"notes": "Final release"}, headers=auth_header)

        # 7. Verify result is RELEASED in the lab system
        get_res = client.get(f"/api/v1/lab/results/{result_id}", headers=auth_header)
        assert get_res.json()["result_status"] == "RELEASED"
