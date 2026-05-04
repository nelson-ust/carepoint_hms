# app/tests/integration/test_lab_routes.py
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

class TestLabRoutes:
    def test_list_lab_tests(self, client, auth_header):
        response = client.get("/api/v1/lab/tests/", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_create_lab_test(self, client, auth_header):
        payload = {
            "name": _unique("Lab Test"),
            "code": _unique("LT"),
            "category": "BIOCHEMISTRY",
            "base_price": 50.0
        }
        response = client.post("/api/v1/lab/tests/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        # Response wrapped: {"success": true, "lab_test": {...}}
        lab_test = data.get("lab_test", data)
        assert lab_test["code"].upper() == payload["code"].upper()

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/lab/tests/")
        assert response.status_code == 401
