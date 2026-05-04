# app/tests/integration/test_role_routes.py
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

class TestRoleRoutes:
    def _create_role(self, client, auth_header):
        payload = {
            "name": _unique("Role"),
            "code": _unique("ROLE"),
            "description": "Integration test role"
        }
        response = client.post("/api/v1/roles/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == payload["name"]
        assert data["code"].upper() == payload["code"].upper()
        return data


    def test_create_role(self, client, auth_header):
        self._create_role(client, auth_header)

    def test_list_roles(self, client, auth_header):
        response = client.get("/api/v1/roles/", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0

    def test_get_role(self, client, auth_header):
        role = self._create_role(client, auth_header)
        role_id = role["id"]
        response = client.get(f"/api/v1/roles/{role_id}", headers=auth_header)
        assert response.status_code == 200
        assert response.json()["id"] == role_id

    def test_update_role(self, client, auth_header):
        role = self._create_role(client, auth_header)
        role_id = role["id"]
        payload = {"name": _unique("Updated Role")}
        response = client.put(f"/api/v1/roles/{role_id}", json=payload, headers=auth_header)
        assert response.status_code == 200
        assert response.json()["name"] == payload["name"]

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/roles/")
        assert response.status_code in (401, 403)
