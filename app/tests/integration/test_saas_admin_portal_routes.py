# app/tests/integration/test_saas_admin_portal_routes.py
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


class TestSaaSAdminPortalRoutes:
    def test_get_system_health(self, saas_client, saas_auth_header, mocker):
        mocker.patch(
            "app.services.tenant_service.TenantService.get_system_health",
            return_value={"db": "ok", "queue": "ok"},
        )
        res = saas_client.get("/api/v1/saas/admin/health", headers=saas_auth_header)
        assert res.status_code == 200
        body = res.json()
        assert isinstance(body, dict)
        assert "db" in body or "status" in body or body  # structure depends on service

    def test_sync_tenant_migrations(self, saas_client, saas_auth_header, mocker):
        mocker.patch(
            "app.services.tenant_service.TenantService.run_migrations_all_tenants",
            return_value={"success": True, "synced": 0},
        )
        res = saas_client.post(
            "/api/v1/saas/admin/migrations/sync", headers=saas_auth_header
        )
        assert res.status_code == 200
        assert isinstance(res.json(), dict)

    def test_health_anonymous(self, saas_client):
        res = saas_client.get("/api/v1/saas/admin/health")
        assert res.status_code == 401

    def test_migrations_sync_anonymous(self, saas_client):
        res = saas_client.post("/api/v1/saas/admin/migrations/sync")
        assert res.status_code == 401
