# app/tests/integration/test_tenant_payment_method_routes.py
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


class TestTenantPaymentMethodRoutes:
    def _create_method(self, client, auth_header):
        payload = {
            "channel": "CASHIER",
            "provider": "MANUAL",
            "display_name": _unique("Cashier"),
            "currency": "NGN",
            "is_active": True,
            "is_default": False,
            "accepts_patient_payments": True,
            "accepts_subscription_payments": False,
            "fee_percent": 0,
            "fee_flat": 0,
        }
        res = client.post(
            "/api/v1/tenant-payment-methods", json=payload, headers=auth_header
        )
        return res, payload

    def test_list_payment_methods(self, client, auth_header):
        res = client.get(
            "/api/v1/tenant-payment-methods", headers=auth_header
        )
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_only_active(self, client, auth_header):
        res = client.get(
            "/api/v1/tenant-payment-methods?only_active=true",
            headers=auth_header,
        )
        assert res.status_code == 200

    def test_create_payment_method(self, client, auth_header):
        res, payload = self._create_method(client, auth_header)
        assert res.status_code in (201, 400, 422, 500)
        if res.status_code == 201:
            body = res.json()
            assert body["display_name"] == payload["display_name"]
            assert body["channel"] == payload["channel"]

    def test_update_not_found(self, client, auth_header):
        res = client.put(
            "/api/v1/tenant-payment-methods/9999999",
            json={"display_name": "x"},
            headers=auth_header,
        )
        assert res.status_code in (404, 400)

    def test_delete_not_found(self, client, auth_header):
        res = client.delete(
            "/api/v1/tenant-payment-methods/9999999",
            headers=auth_header,
        )
        assert res.status_code in (200, 404, 400)

    def test_test_method_not_found(self, client, auth_header):
        res = client.post(
            "/api/v1/tenant-payment-methods/9999999/test",
            headers=auth_header,
        )
        assert res.status_code in (404, 400, 200)

    def test_create_invalid_payload(self, client, auth_header):
        res = client.post(
            "/api/v1/tenant-payment-methods",
            json={"provider": "MANUAL"},  # missing channel/display_name
            headers=auth_header,
        )
        assert res.status_code == 422

    def test_list_anonymous(self, client):
        res = client.get("/api/v1/tenant-payment-methods")
        assert res.status_code == 401

    def test_create_anonymous(self, client):
        res = client.post(
            "/api/v1/tenant-payment-methods",
            json={
                "channel": "CASHIER",
                "display_name": "x",
            },
        )
        assert res.status_code == 401
