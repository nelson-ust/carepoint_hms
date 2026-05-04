# app/tests/integration/test_two_factor_routes.py
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
    if login_res.status_code != 200:
        pytest.fail(f"Auth header setup failed: {login_res.text}")
    token = login_res.json()["tokens"]["access_token"]
    return _bearer_headers(token)

class TestTwoFactorRoutes:
    def test_list_challenges(self, client, auth_header):
        response = client.get("/api/v1/two-factor/challenges", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "items" in data

    def test_expire_challenges(self, client, auth_header, admin_user):
        user_id = admin_user["user"].id
        response = client.post(f"/api/v1/two-factor/users/{user_id}/expire-open-challenges", headers=auth_header)
        assert response.status_code == 200
        assert "expired_count" in response.json()

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/two-factor/challenges")
        assert response.status_code == 401
