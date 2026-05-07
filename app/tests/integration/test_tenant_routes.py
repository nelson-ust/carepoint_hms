# app/tests/integration/test_tenant_routes.py
"""
Integration tests for the SaaS tenant management routes.

Covers:
- Tenant registration (POST /api/v1/tenants/register)
- Tenant listing (GET /api/v1/tenants)
- Tenant detail retrieval (GET /api/v1/tenants/{id})
- Tenant approval / provisioning (POST /api/v1/tenants/{id}/approve)
- Tenant status updates (PUT /api/v1/tenants/{id}/status)
- Anonymous rejection (401)

Email and SMS delivery is mocked to prevent SMTP connection hangs
during tests, since the test environment has no mail server.
"""
from __future__ import annotations

import pytest
from app.tests.conftest import HAS_TEST_DB
from app.tests.integration.test_auth_routes import _login, _bearer_headers, _unique

pytestmark = pytest.mark.skipif(
    not HAS_TEST_DB,
    reason="CAREPOINT_HMS_DATABASE_URL not configured for integration tests.",
)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _mock_email_sms(mocker):
    """
    Prevent all outgoing email / SMS during tenant tests.

    Without this mock, register_tenant → _notify_saas_admins_of_registration
    and _notify_applicant_received would attempt real SMTP connections that
    hang indefinitely in a test environment without a mail server.
    """
    mocker.patch(
        "app.services.tenant_service.send_email",
        return_value={"success": True, "message": "mocked"},
    )
    mocker.patch(
        "app.services.tenant_service.send_sms",
        return_value=None,
    )


@pytest.fixture()
def saas_auth_header(saas_client, saas_admin_user):
    """Authenticate and return bearer headers for SaaS admin routes."""
    login_res = saas_client.post("/api/v1/auth/login", json={
        "identifier": saas_admin_user["email"],
        "password": saas_admin_user["password"],
    })
    if login_res.status_code != 200:
        pytest.skip(f"SaaS admin login failed: {login_res.status_code}")
    data = login_res.json()
    token = data.get("tokens", {}).get("access_token") or data.get("access_token")
    return _bearer_headers(token)


@pytest.fixture()
def subscription_plan(saas_client, saas_auth_header):
    """Ensure a subscription plan exists for tenant registration."""
    # Try listing first
    list_res = saas_client.get("/api/v1/saas/plans", headers=saas_auth_header)
    if list_res.status_code == 200:
        items = list_res.json()
        if items:
            return items[0]["code"]
    # Create one
    plan_payload = {
        "name": "Basic Monthly",
        "code": _unique("BASIC").upper(),
        "billing_cycle": "MONTHLY",
        "price": 99.99,
        "max_users": 10,
        "max_patients": 1000,
        "is_active": True,
    }
    create_res = saas_client.post(
        "/api/v1/saas/plans", json=plan_payload, headers=saas_auth_header
    )
    if create_res.status_code in (200, 201):
        data = create_res.json()
        return data.get("code") or plan_payload["code"]
    # Fallback — just return the code and hope it works
    return plan_payload["code"]


# ── Test Class ────────────────────────────────────────────────────────

class TestTenantRoutes:

    def _register_tenant(self, saas_client, subscription_plan):
        """Helper to register a new tenant and return its ID."""
        code = _unique("clinic")
        payload = {
            "tenant_name": _unique("New Clinic"),
            "tenant_code": code,
            "domain_url": f"{code}.carepointhms.example",
            "plan_code": subscription_plan,
            "admin_email": f"admin@{code}.example",
            "admin_username": f"admin-{code}",
            "admin_password": "ClinicPass123!",
            "admin_first_name": "Clinic",
            "admin_last_name": "Admin",
        }
        response = saas_client.post("/api/v1/tenants/register", json=payload)
        if response.status_code != 201:
            print(
                f"DEBUG: Register Tenant Failed. "
                f"Status: {response.status_code}, Body: {response.text}"
            )
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["tenant_code"] == code.lower()
        assert data["status"] == "PENDING"
        return data["tenant_id"]

    def test_register_tenant(self, saas_client, subscription_plan):
        tid = self._register_tenant(saas_client, subscription_plan)
        assert tid is not None

    def test_list_tenants(self, saas_client, saas_auth_header):
        response = saas_client.get("/api/v1/tenants", headers=saas_auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "tenants" in data
        assert isinstance(data["tenants"], list)

    def test_get_tenant(self, saas_client, saas_auth_header, subscription_plan):
        tid = self._register_tenant(saas_client, subscription_plan)
        response = saas_client.get(
            f"/api/v1/tenants/{tid}", headers=saas_auth_header
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == tid
        assert "code" in data
        assert "status" in data

    def test_approve_tenant(
        self, saas_client, saas_auth_header, subscription_plan, mocker
    ):
        tid = self._register_tenant(saas_client, subscription_plan)

        # Mock the heavy infrastructure operations that require real
        # databases, filesystems, and AWS access.
        mocker.patch("app.services.tenant_service.create_new_database")
        mocker.patch("app.services.tenant_service.run_tenant_initialization")
        mocker.patch(
            "app.services.tenant_service.TenantService._create_tenant_admin"
        )
        mocker.patch(
            "app.services.tenant_service.TenantService._bootstrap_tenant_settings"
        )

        mock_s3 = mocker.patch("app.services.tenant_service.S3Service")
        mock_s3.return_value.create_tenant_bucket.return_value = "test-bucket"

        response = saas_client.post(
            f"/api/v1/tenants/{tid}/approve", headers=saas_auth_header
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "ACTIVE"
        assert data["is_provisioned"] is True

    def test_update_tenant_status(
        self, saas_client, saas_auth_header, subscription_plan
    ):
        tid = self._register_tenant(saas_client, subscription_plan)

        # Suspend tenant
        payload = {"status": "SUSPENDED"}
        response = saas_client.put(
            f"/api/v1/tenants/{tid}/status",
            json=payload,
            headers=saas_auth_header,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "SUSPENDED"

    def test_reject_anonymous(self, saas_client):
        response = saas_client.get("/api/v1/tenants")
        assert response.status_code == 401
