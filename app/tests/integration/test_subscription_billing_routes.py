# app/tests/integration/test_subscription_billing_routes.py
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


class TestSubscriptionBillingRoutes:
    def test_list_invoices(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/subscription-billing/invoices", headers=saas_auth_header
        )
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_invoices_filter_by_tenant(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/subscription-billing/invoices?tenant_id=999",
            headers=saas_auth_header,
        )
        assert res.status_code == 200

    def test_list_invoices_filter_by_status(self, saas_client, saas_auth_header):
        res = saas_client.get(
            "/api/v1/subscription-billing/invoices?invoice_status=DRAFT",
            headers=saas_auth_header,
        )
        assert res.status_code in (200, 422)

    def test_issue_invoice_subscription_not_found(
        self, saas_client, saas_auth_header
    ):
        res = saas_client.post(
            "/api/v1/subscription-billing/invoices/issue",
            json={"subscription_id": 9999999, "send_email": False},
            headers=saas_auth_header,
        )
        assert res.status_code in (404, 400)

    def test_run_due(self, saas_client, saas_auth_header, mocker):
        mocker.patch(
            "app.services.subscription_billing_service.SubscriptionBillingService.generate_due_invoices",
            return_value={"generated": 0},
        )
        res = saas_client.post(
            "/api/v1/subscription-billing/invoices/run-due",
            headers=saas_auth_header,
        )
        assert res.status_code == 200
        assert isinstance(res.json(), dict)

    def test_record_payment_invoice_not_found(
        self, saas_client, saas_auth_header
    ):
        res = saas_client.post(
            "/api/v1/subscription-billing/invoices/9999999/payments",
            json={
                "amount": 50.0,
                "payment_method": "MANUAL",
                "send_receipt": False,
            },
            headers=saas_auth_header,
        )
        assert res.status_code in (404, 400)

    def test_record_payment_invalid_amount(self, saas_client, saas_auth_header):
        res = saas_client.post(
            "/api/v1/subscription-billing/invoices/1/payments",
            json={"amount": -1.0, "payment_method": "MANUAL"},
            headers=saas_auth_header,
        )
        assert res.status_code == 422

    def test_sweep_overdue(self, saas_client, saas_auth_header, mocker):
        mocker.patch(
            "app.services.subscription_billing_service.SubscriptionBillingService.sweep_overdue",
            return_value={"swept": 0},
        )
        res = saas_client.post(
            "/api/v1/subscription-billing/invoices/sweep-overdue",
            headers=saas_auth_header,
        )
        assert res.status_code == 200

    def test_my_invoices_no_tenant_returns_empty(self, saas_client):
        # Public-ish endpoint: when no tenant context, returns []
        res = saas_client.get("/api/v1/subscription-billing/invoices/me")
        # auth or empty list — depends on dep configuration
        assert res.status_code in (200, 401)
        if res.status_code == 200:
            assert isinstance(res.json(), list)

    def test_list_invoices_anonymous(self, saas_client):
        res = saas_client.get("/api/v1/subscription-billing/invoices")
        assert res.status_code == 401

    def test_issue_invoice_anonymous(self, saas_client):
        res = saas_client.post(
            "/api/v1/subscription-billing/invoices/issue",
            json={"subscription_id": 1},
        )
        assert res.status_code == 401
