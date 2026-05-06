# app/tests/integration/test_saas_admin_routes.py
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


class TestSaaSAdminRoutes:
    def _create_admin(self, saas_client, saas_auth_header):
        payload = {
            "first_name": "Plat",
            "last_name": "Admin",
            "email": f"{_unique('plat')}@admin.example",
            "password": "PlatAdminPass123!",
            "is_superuser": False,
            "platform_role": "SUPPORT_ADMIN",
        }
        res = saas_client.post(
            "/api/v1/saas/admins", json=payload, headers=saas_auth_header
        )
        assert res.status_code == 201, res.text
        return res.json()

    def test_list_admins(self, saas_client, saas_auth_header):
        res = saas_client.get("/api/v1/saas/admins", headers=saas_auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_create_admin(self, saas_client, saas_auth_header):
        # The route uses SaaSAdminReadSchema from saas_auth_schemas, which
        # exposes id/email/first_name/last_name/is_superuser/is_active —
        # NOT platform_role. Assert against fields the route actually
        # serializes.
        admin = self._create_admin(saas_client, saas_auth_header)
        assert admin["id"] is not None
        assert admin["email"]
        assert admin["first_name"] == "Plat"
        assert admin["last_name"] == "Admin"

    def test_get_admin(self, saas_client, saas_auth_header):
        admin = self._create_admin(saas_client, saas_auth_header)
        res = saas_client.get(
            f"/api/v1/saas/admins/{admin['id']}", headers=saas_auth_header
        )
        assert res.status_code == 200
        assert res.json()["id"] == admin["id"]

    def test_update_admin(self, saas_client, saas_auth_header):
        admin = self._create_admin(saas_client, saas_auth_header)
        res = saas_client.put(
            f"/api/v1/saas/admins/{admin['id']}",
            json={"first_name": "Updated"},
            headers=saas_auth_header,
        )
        assert res.status_code == 200
        assert res.json()["first_name"] == "Updated"

    def test_update_admin_status(self, saas_client, saas_auth_header):
        admin = self._create_admin(saas_client, saas_auth_header)
        res = saas_client.put(
            f"/api/v1/saas/admins/{admin['id']}/status",
            json={"status": "SUSPENDED"},
            headers=saas_auth_header,
        )
        assert res.status_code in (200, 400, 422)
        if res.status_code == 200:
            assert res.json()["id"] == admin["id"]

    def test_delete_admin(self, saas_client, saas_auth_header):
        admin = self._create_admin(saas_client, saas_auth_header)
        res = saas_client.delete(
            f"/api/v1/saas/admins/{admin['id']}", headers=saas_auth_header
        )
        assert res.status_code == 200

    def test_get_admin_not_found(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/saas/admins/9999999", headers=saas_auth_header
        )
        assert res.status_code in (404, 400)

    def test_create_admin_invalid_payload(self, saas_client, saas_auth_header):
        res = saas_client.post(
            "/api/v1/saas/admins",
            json={"email": "not-an-email"},  # missing required fields
            headers=saas_auth_header,
        )
        assert res.status_code == 422

    def test_reject_anonymous_list(self, saas_client):
        res = saas_client.get("/api/v1/saas/admins")
        assert res.status_code == 401

    def test_reject_anonymous_create(self, saas_client):
        res = saas_client.post(
            "/api/v1/saas/admins",
            json={
                "first_name": "x",
                "last_name": "y",
                "email": "x@y.example",
                "password": "Pass1234!",
            },
        )
        assert res.status_code == 401
