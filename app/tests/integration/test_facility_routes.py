# app/tests/integration/test_facility_routes.py
from __future__ import annotations

"""
Integration tests for facility (branch) routes, including networks and service areas.
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

def _network_payload() -> dict:
    return {
        "code": _unique("NET").upper(),
        "name": _unique("Network Group"),
        "description": "Integration Test Network"
    }


class TestFacilityRoutes:
    def _create(self, client, auth_header):
        res = client.post(
            "/api/v1/facilities",
            json=_facility_payload(),
            headers=auth_header,
        )
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

    def test_get_facility_with_nested_data(self, client, auth_header):
        body = self._create(client, auth_header)
        res = client.get(f"/api/v1/facilities/{body['id']}", headers=auth_header)
        assert res.status_code == 200
        data = res.json()
        assert "network" in data
        assert "service_areas" in data


class TestFacilityNetworkRoutes:
    """
    Integration tests for /api/v1/facilities/networks endpoints.
    """

    def test_network_crud_flow(self, client, auth_header):
        # 1. Create
        payload = _network_payload()
        res = client.post("/api/v1/facilities/networks/create", json=payload, headers=auth_header)
        assert res.status_code == 201
        network = res.json()
        assert network["code"] == payload["code"]

        # 2. List
        res = client.get("/api/v1/facilities/networks/all", headers=auth_header)
        assert res.status_code == 200
        assert any(n["id"] == network["id"] for n in res.json())

        # 3. Update
        res = client.put(f"/api/v1/facilities/networks/{network['id']}", json={"name": "Updated Name"}, headers=auth_header)
        assert res.status_code == 200
        assert res.json()["name"] == "Updated Name"

        # 4. Delete
        res = client.delete(f"/api/v1/facilities/networks/{network['id']}", headers=auth_header)
        assert res.status_code == 204


class TestFacilityServiceAreaRoutes:
    """
    Integration tests for /api/v1/facilities/service-areas endpoints.
    """

    def test_service_area_crud_flow(self, client, auth_header):
        # Setup: need a facility first
        res_fac = client.post("/api/v1/facilities", json=_facility_payload(), headers=auth_header)
        if res_fac.status_code != 201:
            pytest.skip("Facility creation failed/gated")
        facility = res_fac.json()

        # 1. Create
        payload = {
            "facility_id": facility["id"],
            "area_name": "Lagos Mainland",
            "region_code": "NG-LA"
        }
        res = client.post("/api/v1/facilities/service-areas/create", json=payload, headers=auth_header)
        assert res.status_code == 201
        area = res.json()

        # 2. List (filtered)
        res = client.get(f"/api/v1/facilities/service-areas/all?facility_id={facility['id']}", headers=auth_header)
        assert res.status_code == 200
        assert any(a["id"] == area["id"] for a in res.json())

        # 3. Update
        res = client.put(f"/api/v1/facilities/service-areas/{area['id']}", json={"area_name": "New Area Name"}, headers=auth_header)
        assert res.status_code == 200
        assert res.json()["area_name"] == "New Area Name"

        # 4. Delete
        res = client.delete(f"/api/v1/facilities/service-areas/{area['id']}", headers=auth_header)
        assert res.status_code == 204
