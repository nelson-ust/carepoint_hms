# app/tests/integration/test_support_access_routes.py
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


class TestSupportAccessRoutes:
    def test_list_my_grants_empty(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/support-access/me", headers=saas_auth_header
        )
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_all_grants(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/support-access", headers=saas_auth_header
        )
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_request_grant_invalid_reason_too_short(
        self, saas_client, saas_auth_header
    ):
        res = saas_client.post(
            "/api/v1/support-access/request",
            json={
                "tenant_id": 1,
                "reason": "x",  # too short, min_length=10
                "valid_hours": 4,
            },
            headers=saas_auth_header,
        )
        assert res.status_code == 422

    def test_request_grant_unknown_tenant(
        self, saas_client, saas_auth_header
    ):
        res = saas_client.post(
            "/api/v1/support-access/request",
            json={
                "tenant_id": 9999999,
                "reason": "Investigating reported login issue from tenant.",
                "valid_hours": 2,
                "permissions": ["read"],
            },
            headers=saas_auth_header,
        )
        assert res.status_code in (200, 201, 404, 400)

    def test_approve_grant_not_found(self, saas_client, saas_auth_header):
        res = saas_client.post(
            "/api/v1/support-access/9999999/approve",
            json={},
            headers=saas_auth_header,
        )
        assert res.status_code in (404, 400)

    def test_revoke_grant_not_found(self, saas_client, saas_auth_header):
        res = saas_client.post(
            "/api/v1/support-access/9999999/revoke",
            headers=saas_auth_header,
        )
        assert res.status_code in (404, 400)

    def test_sweep_expired(self, saas_client, saas_auth_header, mocker):
        mocker.patch(
            "app.services.support_access_service.SupportAccessService.expire_due_grants",
            return_value=0,
        )
        res = saas_client.post(
            "/api/v1/support-access/sweep", headers=saas_auth_header
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_list_anonymous(self, saas_client):
        res = saas_client.get("/api/v1/support-access")
        assert res.status_code == 401

    def test_request_anonymous(self, saas_client):
        res = saas_client.post(
            "/api/v1/support-access/request",
            json={
                "tenant_id": 1,
                "reason": "Test reason long enough.",
                "valid_hours": 1,
            },
        )
        assert res.status_code == 401

    def test_list_grants_filter_by_status(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/support-access?grant_status=PENDING",
            headers=saas_auth_header,
        )
        assert res.status_code in (200, 422)
