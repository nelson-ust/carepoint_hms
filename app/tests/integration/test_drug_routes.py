# app/tests/integration/test_drug_routes.py
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

class TestDrugRoutes:
    def _create_drug_category(self, client, auth_header):
        payload = {
            "name": _unique("Drug Category"),
            "code": _unique("DCAT"),
            "description": "Test category"
        }
        response = client.post("/api/v1/drugs/categories", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        # Response wrapped: {"success": true, "category": {...}}
        cat = data.get("category", data)
        assert "id" in cat
        return cat


    def test_create_drug_category(self, client, auth_header):
        self._create_drug_category(client, auth_header)

    def _create_drug(self, client, auth_header):
        cat = self._create_drug_category(client, auth_header)
        drug_name = _unique("Drug")
        payload = {
            "name": drug_name,
            "category_id": cat["id"],
            "generic_name": "Generic Name",
            "unit_of_measure": "Tablet"
        }
        response = client.post("/api/v1/drugs/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        # Response wrapped: {"success": true, "drug": {...}}
        drug = data.get("drug", data)
        assert drug["name"] == drug_name
        return drug


    def test_create_drug(self, client, auth_header):
        self._create_drug(client, auth_header)

    def test_list_drugs(self, client, auth_header):
        self._create_drug(client, auth_header)
        response = client.get("/api/v1/drugs/", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/drugs/")
        assert response.status_code == 401
