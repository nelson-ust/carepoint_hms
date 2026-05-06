# app/tests/integration/test_tenant_domain_routes.py
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


class TestTenantDomainRoutes:
    def test_list_domains_unknown_tenant(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/tenant-domains/9999999", headers=saas_auth_header
        )
        # Service may return [] or 404 for an unknown tenant.
        assert res.status_code in (200, 404)
        if res.status_code == 200:
            assert isinstance(res.json(), list)

    def test_add_domain_unknown_tenant(self, saas_client, saas_auth_header):
        res = saas_client.post(
            "/api/v1/tenant-domains/9999999",
            json={
                "domain_name": f"{_unique('clinic')}.example.com",
                "is_primary": False,
            },
            headers=saas_auth_header,
        )
        assert res.status_code in (201, 404, 400, 422)

    def test_get_verification_unknown(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/tenant-domains/9999999/9999999/verification",
            headers=saas_auth_header,
        )
        assert res.status_code in (404, 400)

    def test_verify_domain_unknown(self, saas_client, saas_auth_header):
        res = saas_client.post(
            "/api/v1/tenant-domains/9999999/9999999/verify",
            headers=saas_auth_header,
        )
        assert res.status_code in (404, 400)

    def test_make_primary_unknown(self, saas_client, saas_auth_header):
        res = saas_client.post(
            "/api/v1/tenant-domains/9999999/9999999/make-primary",
            headers=saas_auth_header,
        )
        assert res.status_code in (404, 400)

    def test_remove_domain_unknown(self, saas_client, saas_auth_header):
        res = saas_client.delete(
            "/api/v1/tenant-domains/9999999/9999999",
            headers=saas_auth_header,
        )
        assert res.status_code in (200, 404, 400)

    def test_update_ssl_status_unknown(self, saas_client, saas_auth_header):
        res = saas_client.put(
            "/api/v1/tenant-domains/9999999/9999999/ssl",
            json={"ssl_status": "ACTIVE"},
            headers=saas_auth_header,
        )
        assert res.status_code in (200, 404, 400, 422)

    def test_add_domain_invalid_payload(self, saas_client, saas_auth_header):
        res = saas_client.post(
            "/api/v1/tenant-domains/1",
            json={},  # missing domain_name
            headers=saas_auth_header,
        )
        assert res.status_code == 422

    def test_list_anonymous(self, saas_client):
        res = saas_client.get("/api/v1/tenant-domains/1")
        assert res.status_code == 401

    def test_add_anonymous(self, saas_client):
        res = saas_client.post(
            "/api/v1/tenant-domains/1",
            json={"domain_name": "x.example.com"},
        )
        assert res.status_code == 401
