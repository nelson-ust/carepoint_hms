# app/tests/integration/test_permission_routes.py
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

class TestPermissionRoutes:
    def test_list_permissions(self, client, auth_header):
        response = client.get("/api/v1/permissions/", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0

    def test_get_me_permissions(self, client, auth_header):
        response = client.get("/api/v1/permissions/me", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "permissions" in data
        assert "is_superuser" in data

    def test_list_modules(self, client, auth_header):
        response = client.get("/api/v1/permissions/modules", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["modules"], list)
        assert len(data["modules"]) > 0

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/permissions/")
        assert response.status_code in (401, 403)
