# app/tests/integration/test_staff_routes.py
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

class TestStaffRoutes:
    def test_list_staff(self, client, auth_header):
        response = client.get("/api/v1/staff/", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0

    def test_get_staff(self, client, auth_header, admin_user):
        user_id = admin_user["user"].id
        response = client.get(f"/api/v1/staff/{user_id}", headers=auth_header)
        assert response.status_code == 200
        assert response.json()["user_id"] == user_id

    def test_update_staff(self, client, auth_header, admin_user):
        user_id = admin_user["user"].id
        payload = {"first_name": "Updated"}
        response = client.patch(f"/api/v1/staff/{user_id}", json=payload, headers=auth_header)
        assert response.status_code == 200
        assert response.json()["first_name"] == "Updated"

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/staff/")
        assert response.status_code == 401
