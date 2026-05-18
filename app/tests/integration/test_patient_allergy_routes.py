# app/tests/integration/test_patient_allergy_routes.py
from __future__ import annotations

import pytest
from app.tests.conftest import HAS_TEST_DB
from app.tests.integration.test_auth_routes import _login, _bearer_headers, _unique
from app.tests.integration.test_patient_routes import _create_patient

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
def patient_id(client, auth_header):
    res = _create_patient(client, auth_header)
    return res.json()["patient_id"]

class TestPatientAllergyRoutes:
    def test_allergy_lifecycle(self, client, auth_header, patient_id):
        # 1. Add Allergy
        payload = {
            "allergen_name": "Latex",
            "severity": "MODERATE",
            "reaction": "Skin rash",
            "is_active": True
        }
        response = client.post(
            f"/api/v1/patients/{patient_id}/allergies",
            json=payload,
            headers=auth_header
        )
        assert response.status_code == 201
        allergy_id = response.json()["id"]
        assert response.json()["allergen_name"] == "Latex"

        # 2. List Allergies
        list_res = client.get(
            f"/api/v1/patients/{patient_id}/allergies",
            headers=auth_header
        )
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 1
        assert any(a["id"] == allergy_id for a in list_res.json())

        # 3. Update Allergy
        update_payload = {"severity": "SEVERE"}
        update_res = client.put(
            f"/api/v1/patients/allergies/{allergy_id}",
            json=update_payload,
            headers=auth_header
        )
        assert update_res.status_code == 200
        assert update_res.json()["severity"] == "SEVERE"

        # 4. Delete Allergy (Soft Delete)
        del_res = client.delete(
            f"/api/v1/patients/allergies/{allergy_id}",
            headers=auth_header
        )
        assert del_res.status_code == 200
        assert del_res.json()["success"] is True

        # 5. Verify it's gone from list
        final_list_res = client.get(
            f"/api/v1/patients/{patient_id}/allergies",
            headers=auth_header
        )
        assert not any(a["id"] == allergy_id for a in final_list_res.json())

    def test_patient_detailed_view_includes_allergies(self, client, auth_header, patient_id):
        # Add an allergy first
        client.post(
            f"/api/v1/patients/{patient_id}/allergies",
            json={"allergen_name": "Dust", "severity": "MILD"},
            headers=auth_header
        )
        
        # Fetch detailed patient
        response = client.get(f"/api/v1/patients/{patient_id}", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        
        # Check structured_allergies (aliased from patient_allergies)
        assert "structured_allergies" in data
        assert len(data["structured_allergies"]) >= 1
        assert data["structured_allergies"][0]["allergen_name"] == "Dust"
