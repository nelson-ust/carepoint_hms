# app/tests/integration/test_inventory_routes.py
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

class TestInventoryRoutes:
    def _create_store(self, client, auth_header):
        payload = {
            "name": _unique("Test Store"),
            "code": _unique("STR"),
            "description": "Integration test store"
        }
        response = client.post("/api/v1/inventory/stores", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        # Response wrapped: {"success": true, "store": {...}}
        store = data.get("store", data)
        assert store["code"].upper() == payload["code"].upper()
        return store


    def test_create_store(self, client, auth_header):
        self._create_store(client, auth_header)

    def test_list_stores(self, client, auth_header):
        self._create_store(client, auth_header)
        response = client.get("/api/v1/inventory/stores", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0

    def test_list_inventory_items(self, client, auth_header):
        response = client.get("/api/v1/inventory/items", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/inventory/stores")
        assert response.status_code == 401
