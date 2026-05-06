# app/tests/integration/test_tenant_dashboard_routes.py
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


class TestTenantDashboardRoutes:
    def test_overview(self, client, auth_header):
        res = client.get("/api/v1/dashboard/overview", headers=auth_header)
        assert res.status_code == 200
        body = res.json()
        assert body.get("success") is True
        assert "data" in body

    def test_today(self, client, auth_header):
        res = client.get("/api/v1/dashboard/today", headers=auth_header)
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_patients(self, client, auth_header):
        res = client.get("/api/v1/dashboard/patients", headers=auth_header)
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_visits(self, client, auth_header):
        res = client.get("/api/v1/dashboard/visits", headers=auth_header)
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_appointments(self, client, auth_header):
        res = client.get(
            "/api/v1/dashboard/appointments", headers=auth_header
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_inpatient(self, client, auth_header):
        res = client.get("/api/v1/dashboard/inpatient", headers=auth_header)
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_billing(self, client, auth_header):
        res = client.get("/api/v1/dashboard/billing", headers=auth_header)
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_lab_pharmacy_backlog(self, client, auth_header):
        res = client.get(
            "/api/v1/dashboard/lab-pharmacy-backlog", headers=auth_header
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_inventory_alerts(self, client, auth_header):
        res = client.get(
            "/api/v1/dashboard/inventory-alerts", headers=auth_header
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_hr(self, client, auth_header):
        res = client.get("/api/v1/dashboard/hr", headers=auth_header)
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_medication_adherence(self, client, auth_header):
        res = client.get(
            "/api/v1/dashboard/medication-adherence", headers=auth_header
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_recent_activity(self, client, auth_header):
        res = client.get(
            "/api/v1/dashboard/recent-activity?limit=5", headers=auth_header
        )
        assert res.status_code == 200
        assert res.json().get("success") is True

    def test_overview_anonymous(self, client):
        res = client.get("/api/v1/dashboard/overview")
        assert res.status_code == 401

    def test_today_anonymous(self, client):
        res = client.get("/api/v1/dashboard/today")
        assert res.status_code == 401
