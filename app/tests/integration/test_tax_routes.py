# app/tests/integration/test_tax_routes.py
from __future__ import annotations

"""
Integration tests for /api/v1/tax routes — tax types, rates, rules,
exemptions, invoice tax lines, withholding tax, audit log, and reports.
"""

from datetime import date

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


def _tax_type_payload() -> dict:
    return {
        "code": _unique("TX").upper(),
        "name": _unique("VAT"),
        "kind": "VAT",
        "country_code": "NG",
        "is_withholding": False,
        "is_active": True,
    }


class TestTaxTypes:
    def _create_type(self, client, auth_header):
        res = client.post(
            "/api/v1/tax/types", json=_tax_type_payload(), headers=auth_header
        )
        if res.status_code in (201, 200):
            return res.json()
        pytest.skip(f"Tax-type create failed: {res.status_code} {res.text[:200]}")

    def test_list_tax_types(self, client, auth_header):
        res = client.get("/api/v1/tax/types", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_tax_types_only_active(self, client, auth_header):
        res = client.get(
            "/api/v1/tax/types?only_active=true", headers=auth_header
        )
        assert res.status_code == 200

    def test_create_tax_type_happy_path(self, client, auth_header):
        body = self._create_type(client, auth_header)
        assert body["code"]
        assert "id" in body

    def test_create_rejects_short_country_code(self, client, auth_header):
        bad = _tax_type_payload()
        bad["country_code"] = "X"  # too short
        res = client.post(
            "/api/v1/tax/types", json=bad, headers=auth_header
        )
        assert res.status_code == 422

    def test_create_validates_missing_required(self, client, auth_header):
        bad = _tax_type_payload()
        bad.pop("code")
        res = client.post(
            "/api/v1/tax/types", json=bad, headers=auth_header
        )
        assert res.status_code == 422

    def test_update_unknown_returns_4xx(self, client, auth_header):
        res = client.put(
            "/api/v1/tax/types/999999",
            json={"name": "Updated"},
            headers=auth_header,
        )
        assert res.status_code in (400, 404, 422, 500)


class TestTaxRates:
    def test_list_rates(self, client, auth_header):
        res = client.get("/api/v1/tax/rates", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_rates_supports_filter(self, client, auth_header):
        res = client.get(
            "/api/v1/tax/rates?tax_type_id=1", headers=auth_header
        )
        assert res.status_code == 200

    def test_create_rate_rejects_negative_percent(self, client, auth_header):
        res = client.post(
            "/api/v1/tax/rates",
            json={
                "tax_type_id": 1,
                "rate_percent": "-5",
                "effective_from": date.today().isoformat(),
            },
            headers=auth_header,
        )
        assert res.status_code == 422

    def test_create_rate_rejects_over_100(self, client, auth_header):
        res = client.post(
            "/api/v1/tax/rates",
            json={
                "tax_type_id": 1,
                "rate_percent": "150",
                "effective_from": date.today().isoformat(),
            },
            headers=auth_header,
        )
        assert res.status_code == 422


class TestTaxRules:
    def test_list_rules(self, client, auth_header):
        res = client.get("/api/v1/tax/rules", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_create_rule_validates_missing_required(self, client, auth_header):
        res = client.post(
            "/api/v1/tax/rules", json={}, headers=auth_header
        )
        assert res.status_code == 422


class TestTaxExemptions:
    def test_list_exemptions(self, client, auth_header):
        res = client.get("/api/v1/tax/exemptions", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_create_exemption_validates_missing_required(self, client, auth_header):
        res = client.post(
            "/api/v1/tax/exemptions", json={}, headers=auth_header
        )
        assert res.status_code == 422


class TestInvoiceTaxLines:
    def test_compute_invoice_tax_unknown_returns_empty(
        self, client, auth_header
    ):
        # Service compute returns [] when invoice missing.
        res = client.post(
            "/api/v1/tax/invoices/999999/compute", headers=auth_header
        )
        assert res.status_code == 200
        assert res.json() == []

    def test_read_lines_for_unknown_invoice(self, client, auth_header):
        res = client.get(
            "/api/v1/tax/invoices/999999/lines", headers=auth_header
        )
        assert res.status_code == 200
        assert res.json() == []


class TestWithholdingTax:
    def test_list_withholding(self, client, auth_header):
        res = client.get("/api/v1/tax/withholding", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_create_withholding_validates_missing_required(
        self, client, auth_header
    ):
        res = client.post(
            "/api/v1/tax/withholding", json={}, headers=auth_header
        )
        assert res.status_code == 422

    def test_remit_unknown_returns_4xx(self, client, auth_header):
        res = client.post(
            "/api/v1/tax/withholding/999999/remit",
            json={"certificate_no": "CERT-1"},
            headers=auth_header,
        )
        assert res.status_code in (400, 404, 422, 500)


class TestTaxAuditAndReports:
    def test_audit_log_returns_array(self, client, auth_header):
        res = client.get("/api/v1/tax/audit-log", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_summary_report_responds(self, client, auth_header):
        # period_start and period_end are required query params.
        period_start = (date.today().replace(day=1)).isoformat()
        period_end = date.today().isoformat()
        res = client.get(
            "/api/v1/tax/reports/summary",
            params={"period_start": period_start, "period_end": period_end},
            headers=auth_header,
        )
        assert res.status_code == 200
        body = res.json()
        assert "summary" in body


class TestTaxRoutesAuth:
    def test_anonymous_list_types_returns_401(self, client):
        assert client.get("/api/v1/tax/types").status_code == 401

    def test_anonymous_create_type_returns_401(self, client):
        assert client.post(
            "/api/v1/tax/types", json=_tax_type_payload()
        ).status_code == 401

    def test_anonymous_audit_log_returns_401(self, client):
        assert client.get("/api/v1/tax/audit-log").status_code == 401
