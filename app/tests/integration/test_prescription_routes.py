# app/tests/integration/test_prescription_routes.py
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
    p_payload = {"first_name": _unique("Rx"), "last_name": "Patient", "hospital_number": _unique("RX-HN"), "gender": "MALE"}
    p_res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", json=p_payload, headers=auth_header)
    patient_id = p_res.json()["patient_id"]
    sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdp_id = sdp_res.json()["items"][0]["id"]
    v_payload = {"patient_id": patient_id, "first_service_delivery_point_id": sdp_id}
    v_res = client.post("/api/v1/visits/initiate", json=v_payload, headers=auth_header)
    return v_res.json()["visit"]

@pytest.fixture()
def test_drug(client, auth_header):
    """Create a drug category and drug so prescriptions can reference it."""
    cat_payload = {"name": _unique("Rx Cat"), "code": _unique("RXCAT"), "description": "Prescription test"}
    cat_res = client.post("/api/v1/drugs/categories", json=cat_payload, headers=auth_header)
    cat = cat_res.json().get("category", cat_res.json())

    drug_payload = {
        "name": _unique("Rx Drug"),
        "code": _unique("RXDRG"),
        "category_id": cat["id"],
        "generic_name": "Paracetamol",
        "unit_of_measure": "Tablet"
    }
    drug_res = client.post("/api/v1/drugs/", json=drug_payload, headers=auth_header)
    return drug_res.json().get("drug", drug_res.json())

class TestPrescriptionRoutes:
    def _create_prescription(self, client, auth_header, test_visit, test_drug):
        payload = {
            "visit_id": test_visit["id"],
            "patient_id": test_visit["patient_id"],
            "items": [
                {
                    "drug_id": test_drug["id"],
                    "dosage": "500mg",
                    "frequency": "TID",
                    "duration": "5 days",
                    "quantity_prescribed": 15,
                    "instructions": "Take after meals"
                }
            ]
        }
        response = client.post("/api/v1/prescriptions/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "prescription" in data
        return data["prescription"]


    def test_create_prescription(self, client, auth_header, test_visit, test_drug):
        self._create_prescription(client, auth_header, test_visit, test_drug)

    def test_get_prescription_by_visit(self, client, auth_header, test_visit, test_drug):
        self._create_prescription(client, auth_header, test_visit, test_drug)
        response = client.get(f"/api/v1/prescriptions/visits/{test_visit['id']}", headers=auth_header)
        assert response.status_code == 200

    def test_cancel_prescription(self, client, auth_header, test_visit, test_drug):
        rx = self._create_prescription(client, auth_header, test_visit, test_drug)
        rx_id = rx["id"]
        response = client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json={"reason": "Incorrect drug"}, headers=auth_header)
        assert response.status_code == 200
        assert response.json()["prescription"]["status"] == "CANCELLED"

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/prescriptions/visits/1")
        assert response.status_code == 401
