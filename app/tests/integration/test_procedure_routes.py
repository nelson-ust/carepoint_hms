# app/tests/integration/test_procedure_routes.py
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
    p_payload = {"first_name": _unique("Proc"), "last_name": "Patient", "hospital_number": _unique("PR-HN"), "gender": "MALE"}
    p_res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", json=p_payload, headers=auth_header)
    patient_id = p_res.json()["patient_id"]
    sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdp_id = sdp_res.json()["items"][0]["id"]
    v_payload = {"patient_id": patient_id, "first_service_delivery_point_id": sdp_id}
    v_res = client.post("/api/v1/visits/initiate", json=v_payload, headers=auth_header)
    return v_res.json()["visit"]

class TestProcedureRoutes:
    def test_list_procedures(self, client, auth_header):
        response = client.get("/api/v1/procedures/", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def _create_procedure_order(self, client, auth_header, test_visit):
        # 1. Get a procedure from catalog
        cat_res = client.get("/api/v1/procedures/", headers=auth_header)
        if not cat_res.json()["items"]:
            # Create one if none
            cat_payload = {"code": _unique("PCODE"), "name": "Test Procedure", "default_price": 5000}
            cat_res = client.post("/api/v1/procedures/", json=cat_payload, headers=auth_header)
            proc_id = cat_res.json()["procedure"]["id"]
        else:
            proc_id = cat_res.json()["items"][0]["id"]

        # 2. Create order
        payload = {
            "visit_id": test_visit["id"],
            "procedure_catalog_id": proc_id,
            "notes": "Urgent procedure"
        }
        response = client.post("/api/v1/procedure-orders/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        return data["order"]


    def test_create_procedure_order(self, client, auth_header, test_visit):
        self._create_procedure_order(client, auth_header, test_visit)

    def test_get_procedure_order_by_visit(self, client, auth_header, test_visit):
        self._create_procedure_order(client, auth_header, test_visit)
        response = client.get(f"/api/v1/procedure-orders/visits/{test_visit['id']}", headers=auth_header)
        assert response.status_code == 200
        assert len(response.json()) > 0

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/procedures/")
        assert response.status_code == 401
