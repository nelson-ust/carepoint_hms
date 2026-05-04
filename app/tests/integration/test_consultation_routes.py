# app/tests/integration/test_consultation_routes.py
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
def test_visit(client, auth_header):
    p_payload = {"first_name": _unique("Cons"), "last_name": "Patient", "hospital_number": _unique("C-HN"), "gender": "MALE"}
    p_res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", json=p_payload, headers=auth_header)
    patient_id = p_res.json()["patient_id"]
    sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdp_id = sdp_res.json()["items"][0]["id"]
    v_payload = {"patient_id": patient_id, "first_service_delivery_point_id": sdp_id}
    v_res = client.post("/api/v1/visits/initiate", json=v_payload, headers=auth_header)
    return v_res.json()["visit"]

class TestConsultationRoutes:
    def _create_consultation(self, client, auth_header, test_visit):
        payload = {
            "visit_id": test_visit["id"],
            "subjective_note": "Patient feels tired",
            "objective_note": "Normal vitals",
            "assessment_note": "Likely fatigue",
            "plan_note": "Rest and fluids"
        }
        response = client.post("/api/v1/consultations/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["consultation"]["subjective_note"] == "Patient feels tired"
        return data["consultation"]


    def test_create_consultation(self, client, auth_header, test_visit):
        self._create_consultation(client, auth_header, test_visit)

    def test_get_consultation_by_visit(self, client, auth_header, test_visit):
        self._create_consultation(client, auth_header, test_visit)
        response = client.get(f"/api/v1/consultations/visits/{test_visit['id']}", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) > 0

    def test_update_consultation(self, client, auth_header, test_visit):
        cons = self._create_consultation(client, auth_header, test_visit)
        cons_id = cons["id"]
        payload = {"plan_note": "Updated plan"}
        response = client.put(f"/api/v1/consultations/{cons_id}", json=payload, headers=auth_header)
        assert response.status_code == 200
        assert response.json()["consultation"]["plan_note"] == "Updated plan"

    def test_finalize_consultation(self, client, auth_header, test_visit):
        cons = self._create_consultation(client, auth_header, test_visit)
        cons_id = cons["id"]
        payload = {"is_visit_ended": False}
        response = client.post(f"/api/v1/consultations/{cons_id}/finalize", json=payload, headers=auth_header)
        assert response.status_code == 200
        assert response.json()["consultation"]["status"] in ("COMPLETED", "CLOSED")

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/consultations/visits/1")
        assert response.status_code == 401
