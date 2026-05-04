# app/tests/integration/test_ward_routes.py
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

class TestWardRoutes:
    def _create_ward(self, client, auth_header):
        payload = {
            "name": _unique("Ward"),
            "code": _unique("WRD"),
            "ward_type": "GENERAL",
            "capacity": 10
        }
        response = client.post("/api/v1/wards/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == payload["name"]
        assert data["code"].upper() == payload["code"].upper()
        return data


    def test_create_ward(self, client, auth_header):
        self._create_ward(client, auth_header)

    def test_list_wards(self, client, auth_header):
        self._create_ward(client, auth_header)
        response = client.get("/api/v1/wards/", headers=auth_header)
        assert response.status_code == 200

    def test_get_ward(self, client, auth_header):
        ward = self._create_ward(client, auth_header)
        ward_id = ward["id"]
        response = client.get(f"/api/v1/wards/{ward_id}", headers=auth_header)
        assert response.status_code == 200
        assert response.json()["id"] == ward_id

    def test_update_ward(self, client, auth_header):
        ward = self._create_ward(client, auth_header)
        ward_id = ward["id"]
        payload = {"name": _unique("Updated Ward")}
        response = client.put(f"/api/v1/wards/{ward_id}", json=payload, headers=auth_header)
        assert response.status_code == 200
        assert response.json()["name"] == payload["name"]

    def test_get_ward_summary(self, client, auth_header):
        ward = self._create_ward(client, auth_header)
        ward_id = ward["id"]
        response = client.get(f"/api/v1/wards/{ward_id}/summary", headers=auth_header)
        assert response.status_code == 200

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/wards/")
        assert response.status_code == 401
