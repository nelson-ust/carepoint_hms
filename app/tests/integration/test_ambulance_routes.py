# app/tests/integration/test_ambulance_routes.py
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

class TestAmbulanceRoutes:
    def test_list_ambulances(self, client, auth_header):
        response = client.get("/api/v1/ambulances/", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_create_ambulance(self, client, auth_header):
        payload = {
            "code": _unique("AMB"),
            "plate_number": _unique("PLT"),
            "model": "Toyota Hiace",
        }
        response = client.post("/api/v1/ambulances/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        # Response may be wrapped: {"success": true, "ambulance": {...}}
        amb = data.get("ambulance", data)
        assert amb["code"].upper() == payload["code"].upper()

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/ambulances/")
        assert response.status_code == 401
