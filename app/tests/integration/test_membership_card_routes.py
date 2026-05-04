# app/tests/integration/test_membership_card_routes.py
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

@pytest.fixture()
def test_patient(client, auth_header):
    payload = {
        "first_name": _unique("Card"),
        "last_name": "Patient",
        "hospital_number": _unique("CARD-HN"),
        "gender": "MALE"
    }
    res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", json=payload, headers=auth_header)
    return res.json()

@pytest.fixture()
def test_facility_id(client, auth_header):
    """Get or create a facility id to use as issuing_facility_id."""
    res = client.get("/api/v1/facilities/", headers=auth_header)
    # The endpoint returns a list directly, or a dict with items. Handle both.
    data = res.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    
    if isinstance(items, list) and len(items) > 0:
        return items[0]["id"]
    
    # If no facility, create one
    payload = {
        "name": _unique("Test Facility"),
        "code": _unique("TF"),
        "facility_type": "MAIN_HOSPITAL"
    }
    res = client.post("/api/v1/facilities/", json=payload, headers=auth_header)
    if res.status_code == 201:
        return res.json()["id"]
    
    # Debug info if creation fails
    print(f"\nFacility Creation Failed: {res.status_code}")
    print(f"Response: {res.text}")
    
    # If we can't create a facility, the test should fail with a clear message
    pytest.fail(f"Could not create or find a facility for membership card tests. Status: {res.status_code}")

class TestMembershipCardRoutes:
    def _create_card(self, client, auth_header, test_patient, test_facility_id):
        payload = {
            "patient_id": test_patient["patient_id"],
            "card_number": _unique("CARD-NO"),
            "issuing_facility_id": test_facility_id,
            "initial_balance": 0.0,
        }
        response = client.post("/api/v1/membership-cards/", json=payload, headers=auth_header)
        assert response.status_code == 201
        return response.json()

    def test_create_card(self, client, auth_header, test_patient, test_facility_id):
        self._create_card(client, auth_header, test_patient, test_facility_id)

    def test_get_card(self, client, auth_header, test_patient, test_facility_id):
        card = self._create_card(client, auth_header, test_patient, test_facility_id)
        card_id = card["id"]
        response = client.get(f"/api/v1/membership-cards/{card_id}", headers=auth_header)
        if response.status_code != 200:
            print(f"DEBUG: Get Card Failed. ID: {card_id}, Response: {response.text}")
        assert response.status_code == 200

    def test_get_cards_by_patient(self, client, auth_header, test_patient, test_facility_id):
        self._create_card(client, auth_header, test_patient, test_facility_id)
        patient_id = test_patient["patient_id"]
        response = client.get(f"/api/v1/membership-cards/patient/{patient_id}", headers=auth_header)
        assert response.status_code == 200

    def test_reject_anonymous(self, client):
        response = client.post("/api/v1/membership-cards/", json={})
        assert response.status_code == 401
