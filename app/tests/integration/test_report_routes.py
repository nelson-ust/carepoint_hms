# app/tests/integration/test_report_routes.py
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

class TestReportRoutes:
    def test_financial_summary(self, client, auth_header):
        response = client.get("/api/v1/reports/financial-summary", headers=auth_header)
        assert response.status_code == 200

    def test_operational_summary(self, client, auth_header):
        response = client.get("/api/v1/reports/operational-summary", headers=auth_header)
        assert response.status_code == 200

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/reports/financial-summary")
        assert response.status_code == 401
