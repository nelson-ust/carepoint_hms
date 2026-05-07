# app/tests/integration/test_advanced_features.py
"""
Integration tests for the advanced feature modules:
- Patient Identity (PatientIdentifier, InsuranceProvider)
- Procurement P2P (RFQ, Purchase Order)
- HR Payroll Configuration (AllowanceType)
- Loyalty Program Configuration (LoyaltyProgram)

These tests verify that the newly implemented endpoints work end-to-end
with the test database.
"""
from __future__ import annotations

import uuid

import pytest

from app.tests.conftest import HAS_TEST_DB
from app.tests.integration.test_auth_routes import _login, _bearer_headers, _unique

pytestmark = pytest.mark.skipif(
    not HAS_TEST_DB,
    reason="CAREPOINT_HMS_DATABASE_URL not configured for integration tests.",
)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def admin_token_headers(client, admin_user):
    """
    Authenticate the admin user and return ready-made Authorization headers.

    This fixture resolves the gap where test_advanced_features used
    ``admin_token_headers`` but no conftest ever defined it.
    """
    response = _login(client, admin_user["username"], admin_user["password"])
    assert response.status_code == 200, (
        f"Admin login failed ({response.status_code}): {response.text}"
    )
    token = response.json()["tokens"]["access_token"]
    return _bearer_headers(token)


# ── Patient Identity ─────────────────────────────────────────────────

def test_patient_identity_create_insurance_provider(client, admin_token_headers):
    """Create an insurance provider via /patient-master."""
    resp = client.post(
        "/api/v1/patient-master/insurance-providers",
        headers=admin_token_headers,
        json={
            "name": f"Reliance HMO {uuid.uuid4().hex[:6]}",
            "code": f"REL-{uuid.uuid4().hex[:6].upper()}",
            "contact_person": "John Doe",
        },
    )
    # Accept 200 or 201 depending on route implementation
    assert resp.status_code in (200, 201), (
        f"InsuranceProvider creation failed ({resp.status_code}): {resp.text}"
    )
    data = resp.json()
    assert "id" in data



# ── Procurement P2P ──────────────────────────────────────────────────

def test_procurement_create_requisition(client, admin_token_headers):
    """Create a purchase requisition via /procurements."""
    resp = client.post(
        "/api/v1/procurements/requisitions",
        headers=admin_token_headers,
        json={
            "facility_id": 1,
            "requested_by_staff_id": 1,
            "items": [
                {
                    "item_name": "Paracetamol 500mg",
                    "quantity_requested": 100,
                    "estimated_unit_price": 10.50,
                }
            ],
        },
    )
    assert resp.status_code in (200, 201), (
        f"Requisition creation failed ({resp.status_code}): {resp.text}"
    )


# ── HR Payroll Config ────────────────────────────────────────────────

def test_hr_payroll_create_allowance_type(client, admin_token_headers):
    """Create an allowance type via /hr/payroll-config."""
    code = f"HOU-{uuid.uuid4().hex[:6].upper()}"
    resp = client.post(
        "/api/v1/hr/payroll-config/allowance-types",
        headers=admin_token_headers,
        json={
            "name": "Housing Allowance",
            "code": code,
            "default_amount": 50000,
        },
    )
    assert resp.status_code in (200, 201), (
        f"AllowanceType creation failed ({resp.status_code}): {resp.text}"
    )
    data = resp.json()
    assert data["code"] == code


def test_hr_payroll_list_allowance_types(client, admin_token_headers):
    """List allowance types via /hr/payroll-config."""
    resp = client.get(
        "/api/v1/hr/payroll-config/allowance-types",
        headers=admin_token_headers,
    )
    assert resp.status_code == 200


# ── Loyalty Program ──────────────────────────────────────────────────

def test_loyalty_create_program(client, admin_token_headers):
    """Create a loyalty program via /loyalty-network."""
    code = f"PLAT-{uuid.uuid4().hex[:6].upper()}"
    resp = client.post(
        "/api/v1/loyalty-network/programs",
        headers=admin_token_headers,
        json={
            "name": f"Platinum Patient {uuid.uuid4().hex[:4]}",
            "code": code,
            "points_per_currency_unit": 0.05,
        },
    )
    assert resp.status_code in (200, 201), (
        f"LoyaltyProgram creation failed ({resp.status_code}): {resp.text}"
    )


def test_loyalty_list_programs(client, admin_token_headers):
    """List loyalty programs via /loyalty-network."""
    resp = client.get(
        "/api/v1/loyalty-network/programs",
        headers=admin_token_headers,
    )
    assert resp.status_code == 200
