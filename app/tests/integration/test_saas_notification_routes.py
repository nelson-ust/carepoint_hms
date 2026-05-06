# app/tests/integration/test_saas_notification_routes.py
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


class TestSaaSNotificationRoutes:
    def test_list_empty(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/notifications", headers=saas_auth_header
        )
        assert res.status_code == 200
        body = res.json()
        assert body.get("success") is True
        assert "data" in body
        assert isinstance(body["data"], list)

    def test_list_paginated(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/notifications?skip=0&limit=10",
            headers=saas_auth_header,
        )
        assert res.status_code == 200
        body = res.json()
        assert "total" in body
        assert isinstance(body["total"], int)

    def test_list_unread_only(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/notifications?unread_only=true",
            headers=saas_auth_header,
        )
        assert res.status_code == 200
        body = res.json()
        assert body.get("success") is True

    def test_mark_read_not_found(self, saas_client, saas_auth_header):
        res = saas_client.patch(
            "/api/v1/saas/notifications/9999999/read",
            headers=saas_auth_header,
        )
        assert res.status_code == 404

    def test_list_anonymous(self, saas_client):
        res = saas_client.get("/api/v1/saas/notifications")
        assert res.status_code == 401

    def test_mark_read_anonymous(self, saas_client):
        res = saas_client.patch("/api/v1/saas/notifications/1/read")
        assert res.status_code == 401
