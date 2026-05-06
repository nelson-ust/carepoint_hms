# app/tests/integration/test_saas_subscription_plan_routes.py
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


class TestSaaSSubscriptionPlanRoutes:
    def _create_plan(self, saas_client, saas_auth_header):
        payload = {
            "name": _unique("Plan"),
            "code": _unique("PLAN").upper(),
            "description": "Integration test plan",
            "price": 49.99,
            "currency": "NGN",
            "interval": "MONTHLY",
            "max_facilities": 1,
            "max_users": 10,
            "max_patients": 100,
            "is_active": True,
        }
        res = saas_client.post(
            "/api/v1/saas/plans", json=payload, headers=saas_auth_header
        )
        assert res.status_code == 201, res.text
        return res.json(), payload

    def test_list_plans(self, saas_client, saas_auth_header):
        res = saas_client.get("/api/v1/saas/plans", headers=saas_auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_plans_include_inactive(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/plans?include_inactive=true", headers=saas_auth_header
        )
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_create_plan(self, saas_client, saas_auth_header):
        plan, payload = self._create_plan(saas_client, saas_auth_header)
        assert plan["code"].upper() == payload["code"].upper()
        assert plan["max_users"] == 10

    def test_update_plan(self, saas_client, saas_auth_header):
        plan, _ = self._create_plan(saas_client, saas_auth_header)
        res = saas_client.put(
            f"/api/v1/saas/plans/{plan['id']}",
            json={"max_users": 25},
            headers=saas_auth_header,
        )
        assert res.status_code == 200
        assert res.json()["max_users"] == 25

    def test_create_plan_invalid_payload(self, saas_client, saas_auth_header):
        res = saas_client.post(
            "/api/v1/saas/plans",
            json={"name": "missing required fields"},
            headers=saas_auth_header,
        )
        assert res.status_code == 422

    def test_list_plans_anonymous(self, saas_client):
        res = saas_client.get("/api/v1/saas/plans")
        assert res.status_code == 401

    def test_create_plan_anonymous(self, saas_client):
        res = saas_client.post(
            "/api/v1/saas/plans",
            json={
                "name": "x",
                "code": "X",
                "price": 1,
            },
        )
        assert res.status_code == 401
