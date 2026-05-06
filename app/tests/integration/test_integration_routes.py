# app/tests/integration/test_integration_routes.py
from __future__ import annotations

"""
Integration tests for /api/v1/integrations CRUD routes.
"""

import pytest

from app.tests.conftest import HAS_TEST_DB
from app.tests.integration.test_auth_routes import _login, _bearer_headers, _unique

pytestmark = pytest.mark.skipif(
    not HAS_TEST_DB,
    reason="CAREPOINT_HMS_DATABASE_URL not configured for integration tests.",
)


@pytest.fixture()
def auth_header(client, admin_user):
    res = _login(client, admin_user["username"], admin_user["password"])
    token = res.json()["tokens"]["access_token"]
    return _bearer_headers(token)


def _payload() -> dict:
    return {
        "code": _unique("INTG").upper(),
        "name": _unique("Integration"),
        "base_url": "https://api.example.com/v1",
        "protocol": "REST_JSON",
        "provider_type": "EXTERNAL_API",
        "direction": "OUTBOUND",
        "is_active": True,
    }


class TestIntegrationRoutes:
    def _create(self, client, auth_header):
        res = client.post(
            "/api/v1/integrations/", json=_payload(), headers=auth_header
        )
        assert res.status_code == 201, res.text
        return res.json()

    def test_list_integrations(self, client, auth_header):
        res = client.get("/api/v1/integrations/", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_create_happy_path(self, client, auth_header):
        body = self._create(client, auth_header)
        assert body["name"]
        assert "id" in body

    def test_create_validates_missing_required(self, client, auth_header):
        bad = _payload()
        bad.pop("code")
        res = client.post("/api/v1/integrations/", json=bad, headers=auth_header)
        assert res.status_code == 422

    def test_create_rejects_invalid_protocol(self, client, auth_header):
        bad = _payload()
        bad["protocol"] = "NOT_A_PROTOCOL"
        res = client.post("/api/v1/integrations/", json=bad, headers=auth_header)
        assert res.status_code == 422

    def test_get_integration(self, client, auth_header):
        body = self._create(client, auth_header)
        res = client.get(
            f"/api/v1/integrations/{body['id']}", headers=auth_header
        )
        assert res.status_code == 200
        assert res.json()["id"] == body["id"]

    def test_get_unknown_returns_404(self, client, auth_header):
        res = client.get("/api/v1/integrations/999999", headers=auth_header)
        assert res.status_code == 404

    def test_update_integration(self, client, auth_header):
        body = self._create(client, auth_header)
        new_name = _unique("Renamed")
        res = client.put(
            f"/api/v1/integrations/{body['id']}",
            json={"name": new_name},
            headers=auth_header,
        )
        assert res.status_code == 200
        assert res.json()["name"] == new_name

    def test_update_unknown_returns_404(self, client, auth_header):
        res = client.put(
            "/api/v1/integrations/999999",
            json={"name": "x"},
            headers=auth_header,
        )
        assert res.status_code == 404

    def test_delete_integration(self, client, auth_header):
        body = self._create(client, auth_header)
        res = client.delete(
            f"/api/v1/integrations/{body['id']}", headers=auth_header
        )
        assert res.status_code in (204, 200)

    def test_delete_unknown_returns_404(self, client, auth_header):
        res = client.delete("/api/v1/integrations/999999", headers=auth_header)
        assert res.status_code == 404


class TestIntegrationRoutesAuth:
    def test_anonymous_list_returns_401(self, client):
        assert client.get("/api/v1/integrations/").status_code == 401

    def test_anonymous_create_returns_401(self, client):
        assert client.post("/api/v1/integrations/", json=_payload()).status_code == 401

    def test_anonymous_update_returns_401(self, client):
        assert client.put("/api/v1/integrations/1", json={}).status_code == 401

    def test_anonymous_delete_returns_401(self, client):
        assert client.delete("/api/v1/integrations/1").status_code == 401
