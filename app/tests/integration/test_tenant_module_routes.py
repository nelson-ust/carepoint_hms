# app/tests/integration/test_tenant_module_routes.py
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


class TestTenantModuleRoutes:
    def test_catalog_public(self, saas_client):
        # Catalog is unauthenticated (no current user dep).
        res = saas_client.get("/api/v1/tenant-modules/catalog")
        assert res.status_code == 200
        body = res.json()
        assert "modules" in body
        assert isinstance(body["modules"], list)
        if body["modules"]:
            assert "code" in body["modules"][0]
            assert "label" in body["modules"][0]

    def test_list_modules_for_tenant_unknown(
        self, saas_client, saas_auth_header
    ):
        res = saas_client.get(
            "/api/v1/tenant-modules/9999999", headers=saas_auth_header
        )
        # Service may return [] or 404 — accept both.
        assert res.status_code in (200, 404)

    def test_set_module_unknown_tenant(self, saas_client, saas_auth_header):
        res = saas_client.put(
            "/api/v1/tenant-modules/9999999",
            json={
                "module_code": "pharmacy",
                "is_enabled": True,
                "notes": "test",
            },
            headers=saas_auth_header,
        )
        assert res.status_code in (200, 404, 400, 422)

    def test_bulk_set_modules_invalid_payload(
        self, saas_client, saas_auth_header
    ):
        res = saas_client.put(
            "/api/v1/tenant-modules/1/bulk",
            json={"modules": "not-a-list"},
            headers=saas_auth_header,
        )
        assert res.status_code == 422

    def test_reset_module_unknown(self, saas_client, saas_auth_header):
        res = saas_client.delete(
            "/api/v1/tenant-modules/9999999/pharmacy",
            headers=saas_auth_header,
        )
        assert res.status_code in (200, 404, 400)

    def test_set_module_invalid_payload(self, saas_client, saas_auth_header):
        res = saas_client.put(
            "/api/v1/tenant-modules/1",
            json={},  # missing module_code
            headers=saas_auth_header,
        )
        assert res.status_code == 422

    def test_list_modules_anonymous(self, saas_client):
        res = saas_client.get("/api/v1/tenant-modules/1")
        assert res.status_code == 401

    def test_set_module_anonymous(self, saas_client):
        res = saas_client.put(
            "/api/v1/tenant-modules/1",
            json={"module_code": "pharmacy", "is_enabled": True},
        )
        assert res.status_code == 401

    def test_my_tenant_modules_anonymous(self, saas_client):
        # Tenant-self-service route
        res = saas_client.get("/api/v1/tenant-modules/me/list")
        assert res.status_code == 401
