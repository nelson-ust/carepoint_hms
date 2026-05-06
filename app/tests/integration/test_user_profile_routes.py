# app/tests/integration/test_user_profile_routes.py
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


class TestUserProfileRoutes:
    def test_read_me(self, client, auth_header, admin_user):
        res = client.get("/api/v1/users/me", headers=auth_header)
        assert res.status_code == 200
        body = res.json()
        assert body["username"] == admin_user["username"]
        assert body["email"] == admin_user["email"]
        assert "profile_completion" in body

    def test_update_me_basic(self, client, auth_header):
        payload = {
            "first_name": "Updated",
            "last_name": "Name",
            "bio": "Hello world.",
        }
        res = client.put("/api/v1/users/me", json=payload, headers=auth_header)
        assert res.status_code == 200
        body = res.json()
        assert body["first_name"] == "Updated"
        assert body["last_name"] == "Name"
        assert body["bio"] == "Hello world."

    def test_update_me_partial(self, client, auth_header):
        res = client.put(
            "/api/v1/users/me",
            json={"job_title": "Senior Doctor"},
            headers=auth_header,
        )
        assert res.status_code == 200
        assert res.json()["job_title"] == "Senior Doctor"

    def test_update_me_with_phone(self, client, auth_header):
        res = client.put(
            "/api/v1/users/me",
            json={"phone_number": "+2348012345678"},
            headers=auth_header,
        )
        assert res.status_code == 200
        assert res.json()["phone_number"] == "+2348012345678"

    def test_update_me_invalid_field(self, client, auth_header):
        # Pydantic ignores extra fields by default unless model is strict;
        # this should still succeed (any extras silently dropped).
        res = client.put(
            "/api/v1/users/me",
            json={"role": "ADMIN"},  # not a permitted self-service field
            headers=auth_header,
        )
        assert res.status_code in (200, 422)

    def test_remove_photo(self, client, auth_header):
        res = client.delete(
            "/api/v1/users/me/photo", headers=auth_header
        )
        assert res.status_code == 200
        assert res.json()["profile_photo_url"] is None

    def test_upload_photo_no_file(self, client, auth_header):
        # Multipart upload without file → 422
        res = client.post("/api/v1/users/me/photo", headers=auth_header)
        assert res.status_code == 422

    def test_read_me_anonymous(self, client):
        res = client.get("/api/v1/users/me")
        assert res.status_code == 401

    def test_update_me_anonymous(self, client):
        res = client.put(
            "/api/v1/users/me", json={"first_name": "x"}
        )
        assert res.status_code == 401

    def test_remove_photo_anonymous(self, client):
        res = client.delete("/api/v1/users/me/photo")
        assert res.status_code == 401
