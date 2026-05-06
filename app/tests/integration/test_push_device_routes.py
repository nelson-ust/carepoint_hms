# app/tests/integration/test_push_device_routes.py
from __future__ import annotations

"""
Integration tests for push-device registration routes.
"""

import pytest

from app.tests.conftest import HAS_TEST_DB
from app.tests.integration.test_auth_routes import _login, _bearer_headers, _unique

pytestmark = pytest.mark.skipif(
    not HAS_TEST_DB,
    reason="CAREPOINT_HMS_DATABASE_URL not configured for integration tests.",
)


@pytest.fixture()
def auth_header(client, admin_user):
    res = _login(client, admin_user["username"], admin_user["password"])
    token = res.json()["tokens"]["access_token"]
    return _bearer_headers(token)


def _payload(platform: str = "WEB") -> dict:
    return {
        "device_token": _unique("device-token-").ljust(40, "x"),
        "platform": platform,
        "label": "Test device",
    }


class TestPushDeviceRoutes:
    def test_list_returns_array(self, client, auth_header):
        res = client.get("/api/v1/push-devices", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_register_happy_path(self, client, auth_header):
        res = client.post(
            "/api/v1/push-devices", json=_payload(), headers=auth_header
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["is_active"] is True
        assert body["platform"] == "WEB"

    def test_register_idempotent_refreshes_existing(self, client, auth_header):
        payload = _payload(platform="ANDROID")
        first = client.post(
            "/api/v1/push-devices", json=payload, headers=auth_header
        )
        assert first.status_code == 201
        again = client.post(
            "/api/v1/push-devices", json=payload, headers=auth_header
        )
        assert again.status_code == 201
        assert again.json()["device_token"] == payload["device_token"]

    def test_register_rejects_short_token(self, client, auth_header):
        bad = _payload()
        bad["device_token"] = "short"
        res = client.post("/api/v1/push-devices", json=bad, headers=auth_header)
        assert res.status_code == 422

    def test_register_rejects_invalid_platform(self, client, auth_header):
        bad = _payload(platform="SYMBIAN")
        res = client.post(
            "/api/v1/push-devices", json=bad, headers=auth_header
        )
        assert res.status_code == 422

    def test_register_accepts_ios(self, client, auth_header):
        res = client.post(
            "/api/v1/push-devices",
            json=_payload(platform="IOS"),
            headers=auth_header,
        )
        assert res.status_code == 201
        assert res.json()["platform"] == "IOS"

    def test_delete_returns_success(self, client, auth_header):
        # Create then delete
        created = client.post(
            "/api/v1/push-devices", json=_payload(), headers=auth_header
        )
        device_id = created.json()["id"]
        res = client.delete(
            f"/api/v1/push-devices/{device_id}", headers=auth_header
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_delete_unknown_returns_success(self, client, auth_header):
        # The route returns 200 + {success: True} even when missing.
        res = client.delete(
            "/api/v1/push-devices/999999", headers=auth_header
        )
        assert res.status_code == 200


class TestPushDeviceRoutesAuth:
    def test_anonymous_list_returns_401(self, client):
        assert client.get("/api/v1/push-devices").status_code == 401

    def test_anonymous_register_returns_401(self, client):
        assert client.post("/api/v1/push-devices", json=_payload()).status_code == 401

    def test_anonymous_delete_returns_401(self, client):
        assert client.delete("/api/v1/push-devices/1").status_code == 401
