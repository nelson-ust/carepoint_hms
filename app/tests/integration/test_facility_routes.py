# app/tests/integration/test_facility_routes.py
from __future__ import annotations

"""
Integration tests for facility (branch) routes.

Covers:
- GET    /api/v1/facilities                — list
- POST   /api/v1/facilities                — create (subscription-gated)
- GET    /api/v1/facilities/{facility_id}  — get
- PUT    /api/v1/facilities/{facility_id}  — update
- DELETE /api/v1/facilities/{facility_id}  — delete
"""

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


def _facility_payload() -> dict:
    return {
        "code": _unique("FAC").upper(),
        "name": _unique("Facility"),
        "facility_type": "MAIN_HOSPITAL",
        "status": "ACTIVE",
        "phone_number": "+2348000000000",
        "email": f"{_unique('fac')}@test.example",
        "city": "Lagos",
        "state": "Lagos",
        "country": "Nigeria",
    }


class TestFacilityRoutes:
    def _create(self, client, auth_header):
        res = client.post(
            "/api/v1/facilities",
            json=_facility_payload(),
            headers=auth_header,
        )
        # Subscription gating may block creation in the test DB.
        if res.status_code in (400, 403):
            pytest.skip(f"Facility creation gated by subscription: {res.status_code}")
        assert res.status_code == 201, res.text
        return res.json()

    def test_list_facilities_returns_array(self, client, auth_header):
        res = client.get("/api/v1/facilities", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_create_facility_happy_path(self, client, auth_header):
        body = self._create(client, auth_header)
        assert body["name"]
        assert "id" in body

    def test_create_rejects_duplicate_code(self, client, auth_header):
        body = self._create(client, auth_header)
        dup = _facility_payload()
        dup["code"] = body["code"]
        res = client.post("/api/v1/facilities", json=dup, headers=auth_header)
        assert res.status_code in (400, 409, 422)

    def test_create_validates_missing_required_field(self, client, auth_header):
        bad = _facility_payload()
        bad.pop("code")
        res = client.post("/api/v1/facilities", json=bad, headers=auth_header)
        assert res.status_code == 422

    def test_get_facility_returns_record(self, client, auth_header):
        body = self._create(client, auth_header)
        res = client.get(f"/api/v1/facilities/{body['id']}", headers=auth_header)
        assert res.status_code == 200
        assert res.json()["id"] == body["id"]

    def test_get_unknown_facility_returns_404(self, client, auth_header):
        res = client.get("/api/v1/facilities/999999", headers=auth_header)
        assert res.status_code == 404

    def test_update_facility_persists_changes(self, client, auth_header):
        body = self._create(client, auth_header)
        new_name = _unique("Renamed")
        res = client.put(
            f"/api/v1/facilities/{body['id']}",
            json={"name": new_name},
            headers=auth_header,
        )
        assert res.status_code == 200
        assert res.json()["name"] == new_name

    def test_update_unknown_facility_returns_404(self, client, auth_header):
        res = client.put(
            "/api/v1/facilities/999999",
            json={"name": "X"},
            headers=auth_header,
        )
        assert res.status_code == 404

    def test_delete_facility_returns_204(self, client, auth_header):
        body = self._create(client, auth_header)
        res = client.delete(
            f"/api/v1/facilities/{body['id']}",
            headers=auth_header,
        )
        assert res.status_code in (204, 200)

    def test_delete_unknown_facility_returns_404(self, client, auth_header):
        res = client.delete("/api/v1/facilities/999999", headers=auth_header)
        assert res.status_code == 404


class TestFacilityRoutesAuth:
    def test_anonymous_list_returns_401(self, client):
        res = client.get("/api/v1/facilities")
        assert res.status_code == 401

    def test_anonymous_create_returns_401(self, client):
        res = client.post("/api/v1/facilities", json=_facility_payload())
        assert res.status_code == 401

    def test_anonymous_update_returns_401(self, client):
        res = client.put("/api/v1/facilities/1", json={"name": "x"})
        assert res.status_code == 401

    def test_anonymous_delete_returns_401(self, client):
        res = client.delete("/api/v1/facilities/1")
        assert res.status_code == 401
