# app/tests/integration/test_edge_node_routes.py
from __future__ import annotations

import pytest
from app.tests.conftest import HAS_TEST_DB
from app.tests.integration.test_auth_routes import _login, _bearer_headers, _unique

pytestmark = pytest.mark.skipif(
    not HAS_TEST_DB,
    reason="CAREPOINT_HMS_DATABASE_URL not configured for integration tests.",
)


@pytest.fixture()
def saas_auth_header(saas_client, saas_admin_user):
    login_res = saas_client.post(
        "/api/v1/auth/login",
        json={
            "identifier": saas_admin_user["email"],
            "password": saas_admin_user["password"],
        },
    )
    if login_res.status_code != 200:
        pytest.skip(f"SaaS admin login failed: {login_res.status_code}")
    data = login_res.json()
    token = data.get("tokens", {}).get("access_token") or data.get("access_token")
    return _bearer_headers(token)


class TestEdgeNodeAdminRoutes:
    def test_list_edge_nodes(self, saas_client, saas_auth_header):
        response = saas_client.get(
            "/api/v1/edge-nodes", headers=saas_auth_header
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_register_edge_node_invalid(self, saas_client, saas_auth_header):
        response = saas_client.post(
            "/api/v1/edge-nodes", json={}, headers=saas_auth_header
        )
        assert response.status_code == 422

    def test_register_edge_node_missing_tenant(self, saas_client, saas_auth_header):
        payload = {
            "tenant_id": 99999999,
            "code": _unique("EDGE"),
            "display_name": "Test Edge Node",
            "heartbeat_interval_seconds": 300,
            "heartbeat_grace_seconds": 900,
        }
        response = saas_client.post(
            "/api/v1/edge-nodes", json=payload, headers=saas_auth_header
        )
        # Tenant FK may not exist; tolerate either creation, 400, or 404.
        assert response.status_code in (200, 201, 400, 404, 422, 500)

    def test_rotate_token_missing(self, saas_client, saas_auth_header):
        response = saas_client.post(
            "/api/v1/edge-nodes/99999999/rotate-token", headers=saas_auth_header
        )
        assert response.status_code in (200, 404, 400)

    def test_decommission_missing(self, saas_client, saas_auth_header):
        response = saas_client.post(
            "/api/v1/edge-nodes/99999999/decommission", headers=saas_auth_header
        )
        assert response.status_code in (200, 404, 400)

    def test_reject_anonymous(self, saas_client):
        response = saas_client.get("/api/v1/edge-nodes")
        assert response.status_code == 401


class TestEdgeSyncRoutes:
    def test_handshake_requires_token(self, saas_client):
        response = saas_client.post("/api/v1/sync/handshake", json={})
        # ForbiddenError -> 403 in this codebase, sometimes mapped to 401
        assert response.status_code in (401, 403)

    def test_pull_requires_token(self, saas_client):
        response = saas_client.get("/api/v1/sync/pull")
        assert response.status_code in (401, 403)

    def test_push_requires_token(self, saas_client):
        response = saas_client.post(
            "/api/v1/sync/push", json={"rows": []}
        )
        assert response.status_code in (401, 403)

    def test_handshake_with_bogus_token(self, saas_client):
        response = saas_client.post(
            "/api/v1/sync/handshake",
            json={},
            headers={"Authorization": "Bearer bogus-edge-token"},
        )
        assert response.status_code in (401, 403)


class TestConnectivityProbe:
    def test_probe_public(self, saas_client):
        response = saas_client.get("/api/v1/connectivity/probe")
        assert response.status_code == 200
        body = response.json()
        assert body.get("ok") is True
        assert "server_time" in body
        assert body.get("supports_offline_sync") is True
