# app/tests/integration/test_service_delivery_point_routes.py
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

class TestServiceDeliveryPointRoutes:
    def _create_sdp(self, client, auth_header):
        payload = {
            "name": _unique("SDP"),
            "code": _unique("SDPC"),
            "service_point_type": "CLINIC",
            "supports_walk_in": True
        }
        response = client.post("/api/v1/service-delivery-points/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == payload["name"]
        assert data["code"].upper() == payload["code"].upper()
        return data


    def test_create_sdp(self, client, auth_header):
        self._create_sdp(client, auth_header)

    def test_list_sdps(self, client, auth_header):
        self._create_sdp(client, auth_header)
        response = client.get("/api/v1/service-delivery-points/", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0

    def test_get_sdp(self, client, auth_header):
        sdp = self._create_sdp(client, auth_header)
        sdp_id = sdp["id"]
        response = client.get(f"/api/v1/service-delivery-points/{sdp_id}", headers=auth_header)
        assert response.status_code == 200
        assert response.json()["id"] == sdp_id

    def test_update_sdp(self, client, auth_header):
        sdp = self._create_sdp(client, auth_header)
        sdp_id = sdp["id"]
        payload = {"name": _unique("Updated SDP")}
        response = client.put(f"/api/v1/service-delivery-points/{sdp_id}", json=payload, headers=auth_header)
        assert response.status_code == 200
        assert response.json()["name"] == payload["name"]

    def test_get_by_code(self, client, auth_header):
        sdp = self._create_sdp(client, auth_header)
        code = sdp["code"]
        response = client.get(f"/api/v1/service-delivery-points/by-code/{code}", headers=auth_header)
        assert response.status_code == 200
        assert response.json()["code"].upper() == code.upper()

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/service-delivery-points/")
        assert response.status_code == 401
