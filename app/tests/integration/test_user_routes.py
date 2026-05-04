# app/tests/integration/test_user_routes.py
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

class TestUserRoutes:
    def test_get_me(self, client, auth_header):
        response = client.get("/api/v1/users/me", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "username" in data
        assert "email" in data

    def test_list_users(self, client, auth_header):
        response = client.get("/api/v1/users/", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0

    def test_get_user_sessions(self, client, auth_header, admin_user):
        user_id = admin_user["user"].id
        response = client.get(f"/api/v1/users/{user_id}/sessions", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "items" in data or "sessions" in data

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/users/me")
        assert response.status_code == 401
