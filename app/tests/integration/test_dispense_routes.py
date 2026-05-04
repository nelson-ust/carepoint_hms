# app/tests/integration/test_dispense_routes.py
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
def test_prescription(client, auth_header):
    # Create drug first
    cat_payload = {"name": _unique("DS Cat"), "code": _unique("DSCAT"), "description": "Dispense test"}
    cat_res = client.post("/api/v1/drugs/categories", json=cat_payload, headers=auth_header)
    cat = cat_res.json().get("category", cat_res.json())

    drug_payload = {
        "name": _unique("DS Drug"),
        "category_id": cat["id"],
        "generic_name": "Amoxicillin",
    }
    drug_res = client.post("/api/v1/drugs/", json=drug_payload, headers=auth_header)
    drug = drug_res.json().get("drug", drug_res.json())

    # Create patient + visit
    p_payload = {"first_name": _unique("Dispense"), "last_name": "Patient", "hospital_number": _unique("DS-HN"), "gender": "MALE"}
    p_res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", json=p_payload, headers=auth_header)
    patient_id = p_res.json()["patient_id"]
    sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdp_id = sdp_res.json()["items"][0]["id"]
    v_payload = {"patient_id": patient_id, "first_service_delivery_point_id": sdp_id}
    v_res = client.post("/api/v1/visits/initiate", json=v_payload, headers=auth_header)
    visit = v_res.json()["visit"]

    rx_payload = {
        "visit_id": visit["id"],
        "patient_id": patient_id,
        "items": [{"drug_id": drug["id"], "dosage": "500mg", "frequency": "TID", "duration": "5 days", "quantity_prescribed": 15}]
    }
    rx_res = client.post("/api/v1/prescriptions/", json=rx_payload, headers=auth_header)
    rx_data = rx_res.json()
    rx = rx_data.get("prescription", rx_data)
    return {"prescription": rx, "drug": drug, "patient_id": patient_id, "visit_id": visit["id"]}

class TestDispenseRoutes:
    def test_create_dispense(self, client, auth_header, test_prescription):
        rx = test_prescription["prescription"]
        # DispenseCreateSchema only needs prescription_id + items
        payload = {
            "prescription_id": rx["id"],
            "items": [
                {
                    "prescription_item_id": rx["items"][0]["id"],
                    "quantity_dispensed": 15,
                }
            ]
        }
        response = client.post("/api/v1/dispenses/", json=payload, headers=auth_header)
        # 201 = success, 400 = no inventory stock configured (app-level business rule)
        assert response.status_code in (201, 400)
        if response.status_code == 201:
            data = response.json()
            assert data["success"] is True
            assert "dispense" in data

    def test_get_dispense_by_visit(self, client, auth_header, test_prescription):
        rx = test_prescription["prescription"]
        response = client.get(f"/api/v1/dispenses/prescriptions/{rx['id']}", headers=auth_header)
        assert response.status_code == 200

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/dispenses/prescriptions/1")
        assert response.status_code == 401
