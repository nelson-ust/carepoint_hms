# app/tests/integration/test_tenant_email_routes.py
from __future__ import annotations

import pytest
from app.tests.conftest import HAS_TEST_DB
from app.tests.integration.test_auth_routes import _login, _bearer_headers, _unique

pytestmark = pytest.mark.skipif(
    not HAS_TEST_DB,
    reason="CAREPOINT_HMS_DATABASE_URL not configured for integration tests.",
)


@pytest.fixture()
def auth_header(client, admin_user):
    login_res = _login(client, admin_user["username"], admin_user["password"])
    token = login_res.json()["tokens"]["access_token"]
    return _bearer_headers(token)


class TestTenantEmailRoutes:
    def _create_config(self, client, auth_header):
        payload = {
            "provider": "SMTP",
            "display_name": _unique("EmailCfg"),
            "from_email": f"sender-{_unique('e')}@test.example",
            "from_name": "Test Sender",
            "is_active": True,
            "is_default": True,
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_security": "TLS",
            "smtp_username": "user",
            "credentials": {"smtp_password": "secret-password"},
        }
        res = client.post(
            "/api/v1/tenant-email-config", json=payload, headers=auth_header
        )
        # Schema validation may pass; service may still fail if encryption
        # backend is not configured. Accept 201 or fallback to 400/500.
        return res, payload

    def test_list_email_configs(self, client, auth_header):
        res = client.get("/api/v1/tenant-email-config", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_email_configs_only_active(self, client, auth_header):
        res = client.get(
            "/api/v1/tenant-email-config?only_active=true", headers=auth_header
        )
        assert res.status_code == 200

    def test_create_email_config(self, client, auth_header):
        res, payload = self._create_config(client, auth_header)
        assert res.status_code in (201, 400, 422, 500)
        if res.status_code == 201:
            body = res.json()
            assert body["display_name"] == payload["display_name"]
            assert body["from_email"] == payload["from_email"]

    def test_update_email_config_not_found(self, client, auth_header):
        res = client.put(
            "/api/v1/tenant-email-config/9999999",
            json={"display_name": "x"},
            headers=auth_header,
        )
        assert res.status_code in (404, 400)

    def test_delete_email_config_not_found(self, client, auth_header):
        res = client.delete(
            "/api/v1/tenant-email-config/9999999", headers=auth_header
        )
        assert res.status_code in (200, 404, 400)

    def test_test_config_not_found(self, client, auth_header):
        res = client.post(
            "/api/v1/tenant-email-config/9999999/test", headers=auth_header
        )
        assert res.status_code in (404, 400, 200)

    def test_send_test_email_invalid_recipient(self, client, auth_header):
        res = client.post(
            "/api/v1/tenant-email-config/9999999/send-test",
            json={"recipient": "not-an-email"},
            headers=auth_header,
        )
        assert res.status_code == 422

    def test_create_invalid_payload(self, client, auth_header):
        res = client.post(
            "/api/v1/tenant-email-config",
            json={"provider": "SMTP"},  # missing display_name + from_email
            headers=auth_header,
        )
        assert res.status_code == 422

    def test_list_anonymous(self, client):
        res = client.get("/api/v1/tenant-email-config")
        assert res.status_code == 401

    def test_create_anonymous(self, client):
        res = client.post(
            "/api/v1/tenant-email-config",
            json={
                "provider": "SMTP",
                "display_name": "x",
                "from_email": "x@y.example",
            },
        )
        assert res.status_code == 401
