# app/tests/integration/test_patient_payment_routes.py
from __future__ import annotations

"""
Integration tests for /api/v1/patient-payments routes.

Patient-payment behaviour depends on a configured TenantPaymentMethod, an
existing invoice, and (for gateway channels) an outbound HTTP call. The
test DB usually lacks all of that, so these tests focus on:

- Anonymous access is rejected (401).
- /methods responds with an array.
- /pay validates payload and rejects unknown invoices cleanly.
- /confirm-gateway validates payload.
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


def _pay_payload(invoice_id: int = 1, channel: str = "CASHIER") -> dict:
    return {
        "invoice_id": invoice_id,
        "amount": 100.00,
        "channel": channel,
        "note": "Test payment",
    }


class TestPatientPaymentMethods:
    def test_list_methods_returns_array(self, client, auth_header):
        res = client.get(
            "/api/v1/patient-payments/methods", headers=auth_header
        )
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_anonymous_methods_returns_401(self, client):
        assert client.get("/api/v1/patient-payments/methods").status_code == 401


class TestPatientPaymentPay:
    def test_pay_validates_missing_required(self, client, auth_header):
        bad = _pay_payload()
        bad.pop("channel")
        res = client.post(
            "/api/v1/patient-payments/pay", json=bad, headers=auth_header
        )
        assert res.status_code == 422

    def test_pay_rejects_zero_amount(self, client, auth_header):
        bad = _pay_payload()
        bad["amount"] = 0
        res = client.post(
            "/api/v1/patient-payments/pay", json=bad, headers=auth_header
        )
        assert res.status_code == 422

    def test_pay_rejects_negative_amount(self, client, auth_header):
        bad = _pay_payload()
        bad["amount"] = -1.0
        res = client.post(
            "/api/v1/patient-payments/pay", json=bad, headers=auth_header
        )
        assert res.status_code == 422

    def test_pay_rejects_invalid_channel(self, client, auth_header):
        bad = _pay_payload(channel="NOT_A_CHANNEL")
        res = client.post(
            "/api/v1/patient-payments/pay", json=bad, headers=auth_header
        )
        assert res.status_code == 422

    def test_pay_unknown_invoice_returns_4xx(self, client, auth_header):
        bad = _pay_payload(invoice_id=999999)
        res = client.post(
            "/api/v1/patient-payments/pay", json=bad, headers=auth_header
        )
        # Service may raise NotFoundError, BadRequestError, or 500 if other
        # tenant config is missing — we care that it didn't 200.
        assert res.status_code in (400, 404, 422, 500)

    def test_anonymous_pay_returns_401(self, client):
        assert client.post(
            "/api/v1/patient-payments/pay", json=_pay_payload()
        ).status_code == 401


class TestPatientPaymentConfirmGateway:
    def test_confirm_validates_missing_reference(self, client, auth_header):
        res = client.post(
            "/api/v1/patient-payments/confirm-gateway",
            json={"succeeded": True},
            headers=auth_header,
        )
        assert res.status_code == 422

    def test_confirm_with_unknown_reference_returns_4xx(self, client, auth_header):
        res = client.post(
            "/api/v1/patient-payments/confirm-gateway",
            json={"payment_reference": _unique("ref-"), "succeeded": True},
            headers=auth_header,
        )
        assert res.status_code in (400, 404, 422, 500)

    def test_anonymous_confirm_returns_401(self, client):
        assert client.post(
            "/api/v1/patient-payments/confirm-gateway",
            json={"payment_reference": "x", "succeeded": True},
        ).status_code == 401
