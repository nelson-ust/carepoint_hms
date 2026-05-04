# app/tests/integration/test_bed_routes.py
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
def test_ward(client, auth_header):
    payload = {
        "name": _unique("Bed Ward"),
        "code": _unique("BWRD"),
        "ward_type": "GENERAL"
    }
    res = client.post("/api/v1/wards/", json=payload, headers=auth_header)
    return res.json()

class TestBedRoutes:
    def _create_bed(self, client, auth_header, test_ward):
        payload = {
            "ward_id": test_ward["id"],
            "bed_no": _unique("BED"),
            "bed_status": "AVAILABLE",
            "bed_type": "STANDARD"
        }
        response = client.post("/api/v1/beds/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["bed_no"].upper() == payload["bed_no"].upper()
        assert data["ward_id"] == test_ward["id"]
        return data



    def test_create_bed(self, client, auth_header, test_ward):
        self._create_bed(client, auth_header, test_ward)

    def test_list_beds(self, client, auth_header, test_ward):
        self._create_bed(client, auth_header, test_ward)
        response = client.get("/api/v1/beds/", headers=auth_header)
        assert response.status_code == 200

    def test_get_bed(self, client, auth_header, test_ward):
        bed = self._create_bed(client, auth_header, test_ward)
        bed_id = bed["id"]
        response = client.get(f"/api/v1/beds/{bed_id}", headers=auth_header)
        assert response.status_code == 200
        assert response.json()["id"] == bed_id

    def test_update_bed(self, client, auth_header, test_ward):
        bed = self._create_bed(client, auth_header, test_ward)
        bed_id = bed["id"]
        payload = {"bed_type": "VIP"}
        response = client.put(f"/api/v1/beds/{bed_id}", json=payload, headers=auth_header)
        assert response.status_code == 200
        assert response.json()["bed_type"] == "VIP"

    def test_get_bed_summary(self, client, auth_header, test_ward):
        bed = self._create_bed(client, auth_header, test_ward)
        bed_id = bed["id"]
        response = client.get(f"/api/v1/beds/{bed_id}/summary", headers=auth_header)
        assert response.status_code == 200

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/beds/")
        assert response.status_code == 401
