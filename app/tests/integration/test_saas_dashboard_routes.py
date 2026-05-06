# app/tests/integration/test_saas_dashboard_routes.py
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


class TestSaaSDashboardRoutes:
    def test_metrics(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/dashboard/metrics", headers=saas_auth_header
        )
        assert res.status_code == 200
        body = res.json()
        assert body.get("success") is True
        assert "data" in body

    def test_overview(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/dashboard/overview", headers=saas_auth_header
        )
        assert res.status_code == 200
        body = res.json()
        assert body.get("success") is True

    def test_tenant_summary(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/dashboard/tenants", headers=saas_auth_header
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_onboarding_pipeline(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/dashboard/onboarding-pipeline", headers=saas_auth_header
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_subscription_summary(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/dashboard/subscriptions", headers=saas_auth_header
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_billing_summary(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/dashboard/billing", headers=saas_auth_header
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_billing_ageing(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/dashboard/billing/ageing", headers=saas_auth_header
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_edge_node_summary(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/dashboard/edge-nodes", headers=saas_auth_header
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_support_access_summary(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/dashboard/support-access", headers=saas_auth_header
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_usage_summary(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/dashboard/usage", headers=saas_auth_header
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_top_tenants(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/dashboard/top-tenants?limit=5",
            headers=saas_auth_header,
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_recent_activity(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/dashboard/recent-activity?limit=5",
            headers=saas_auth_header,
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_metrics_anonymous(self, saas_client):
        res = saas_client.get("/api/v1/saas/dashboard/metrics")
        assert res.status_code == 401

    def test_overview_anonymous(self, saas_client):
        res = saas_client.get("/api/v1/saas/dashboard/overview")
        assert res.status_code == 401
