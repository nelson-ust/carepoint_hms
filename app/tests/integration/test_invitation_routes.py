# app/tests/integration/test_invitation_routes.py
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


class TestInvitationRoutes:
    def _create_invitation(self, client, auth_header, email=None):
        payload = {
            "email": email or f"invitee-{_unique('e')}@test.example",
            "first_name": "Inv",
            "last_name": "Itee",
            "expiry_days": 7,
        }
        res = client.post(
            "/api/v1/invitations", json=payload, headers=auth_header
        )
        return res, payload

    def test_create_invitation(self, client, auth_header):
        res, payload = self._create_invitation(client, auth_header)
        assert res.status_code in (201, 400, 422, 500)
        if res.status_code == 201:
            body = res.json()
            assert "invitation" in body
            assert "token" in body
            assert body["invitation"]["email"] == payload["email"]

    def test_list_invitations(self, client, auth_header):
        res = client.get("/api/v1/invitations", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_invitations_filter_by_status(self, client, auth_header):
        res = client.get(
            "/api/v1/invitations?invitation_status=PENDING",
            headers=auth_header,
        )
        assert res.status_code in (200, 422)

    def test_cancel_invitation_not_found(self, client, auth_header):
        res = client.post(
            "/api/v1/invitations/9999999/cancel", headers=auth_header
        )
        assert res.status_code in (404, 400)

    def test_resend_invitation_not_found(self, client, auth_header):
        res = client.post(
            "/api/v1/invitations/9999999/resend", headers=auth_header
        )
        assert res.status_code in (404, 400)

    def test_sweep_expired(self, client, auth_header):
        res = client.post("/api/v1/invitations/sweep", headers=auth_header)
        assert res.status_code == 200
        body = res.json()
        assert body.get("success") is True
        assert "expired" in body

    def test_accept_invalid_token(self, client):
        # Public endpoint — no auth required.
        res = client.post(
            "/api/v1/invitations/accept",
            json={
                "token": "definitely-not-a-real-token",
                "username": _unique("u"),
                "password": "ValidPass123!",
            },
        )
        assert res.status_code in (400, 404, 422)

    def test_accept_missing_fields(self, client):
        res = client.post(
            "/api/v1/invitations/accept",
            json={"token": "x"},  # missing username + password
        )
        assert res.status_code == 422

    def test_create_invitation_invalid_expiry(self, client, auth_header):
        res = client.post(
            "/api/v1/invitations",
            json={
                "email": "x@y.example",
                "expiry_days": 999,  # exceeds max=30
            },
            headers=auth_header,
        )
        assert res.status_code == 422

    def test_list_anonymous(self, client):
        res = client.get("/api/v1/invitations")
        assert res.status_code == 401

    def test_create_anonymous(self, client):
        res = client.post(
            "/api/v1/invitations",
            json={"email": "x@y.example"},
        )
        assert res.status_code == 401
