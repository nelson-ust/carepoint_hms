# app/tests/integration/test_department_routes.py
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

class TestDepartmentRoutes:
    def _create_department(self, client, auth_header):
        payload = {
            "name": _unique("Department"),
            "code": _unique("DEPT"),
            "description": "Integration test department"
        }
        response = client.post("/api/v1/departments/", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == payload["name"]
        assert data["code"] == payload["code"]
        return data


    def test_create_department(self, client, auth_header):
        self._create_department(client, auth_header)

    def test_list_departments(self, client, auth_header):
        # Ensure at least one exists
        self._create_department(client, auth_header)
        
        response = client.get("/api/v1/departments/", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0

    def test_get_department(self, client, auth_header):
        dept = self._create_department(client, auth_header)
        dept_id = dept["id"]
        
        response = client.get(f"/api/v1/departments/{dept_id}", headers=auth_header)
        assert response.status_code == 200
        assert response.json()["id"] == dept_id

    def test_update_department(self, client, auth_header):
        dept = self._create_department(client, auth_header)
        dept_id = dept["id"]
        
        payload = {"name": _unique("Updated Name")}
        response = client.patch(f"/api/v1/departments/{dept_id}", json=payload, headers=auth_header)
        assert response.status_code == 200
        assert response.json()["name"] == payload["name"]

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/departments/")
        assert response.status_code == 401
