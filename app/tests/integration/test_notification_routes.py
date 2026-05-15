# app/tests/integration/test_notification_routes.py
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

class TestNotificationRoutes:
    def test_list_notifications_standard_response(self, client, auth_header):
        """Verify the optimized list endpoint returns the correct structure."""
        response = client.get("/api/v1/notifications/", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "count" in data
        assert "meta" in data
        assert isinstance(data["items"], list)

    def test_dispatch_and_mark_as_read(self, client, auth_header):
        # 1. Dispatch a notification
        dispatch_res = client.post(
            "/api/v1/notifications/dispatch-ad-hoc",
            json={
                "channel": "IN_APP", 
                "subject": "Optimization Test", 
                "body": "Testing fast serialization"
            },
            headers=auth_header,
        )
        assert dispatch_res.status_code == 201
        note_id = dispatch_res.json().get("notification_id")
        
        # 2. Mark it as read
        if note_id:
            response = client.post(f"/api/v1/notifications/{note_id}/mark-read", headers=auth_header)
            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/notifications/")
        assert response.status_code == 401

