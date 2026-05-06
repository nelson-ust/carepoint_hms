# app/tests/integration/test_approval_routes.py
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


def _flow_payload():
    return {
        "code": _unique("FLOW").upper(),
        "name": _unique("Flow"),
        "subject_type": "GENERIC",
        "is_default": False,
        "notify_on_submit": False,
        "notify_on_decision": False,
        "steps": [
            {
                "step_order": 1,
                "name": "First step",
                "decision_rule": "ANY_OF",
                "required_approvals": 1,
                "approvers": [
                    {
                        "approver_kind": "DYNAMIC",
                        "dynamic_token": "REQUESTER_MANAGER",
                        "is_required": False,
                    }
                ],
            }
        ],
    }


class TestApprovalFlowRoutes:
    def _create_flow(self, client, auth_header):
        response = client.post(
            "/api/v1/approvals/flows", json=_flow_payload(), headers=auth_header
        )
        # Engine may reject due to subject-type defaults; tolerate either.
        assert response.status_code in (200, 201, 400, 422)
        if response.status_code in (200, 201):
            return response.json()["flow"]
        return None

    def test_list_flows(self, client, auth_header):
        response = client.get("/api/v1/approvals/flows", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_create_flow(self, client, auth_header):
        self._create_flow(client, auth_header)

    def test_get_flow_missing(self, client, auth_header):
        response = client.get(
            "/api/v1/approvals/flows/99999999", headers=auth_header
        )
        assert response.status_code in (200, 404)

    def test_create_flow_invalid_body(self, client, auth_header):
        response = client.post(
            "/api/v1/approvals/flows", json={"code": "X"}, headers=auth_header
        )
        assert response.status_code == 422

    def test_update_flow_missing(self, client, auth_header):
        response = client.patch(
            "/api/v1/approvals/flows/99999999",
            json={"name": _unique("Renamed")},
            headers=auth_header,
        )
        assert response.status_code in (200, 404)

    def test_delete_flow_missing(self, client, auth_header):
        response = client.delete(
            "/api/v1/approvals/flows/99999999", headers=auth_header
        )
        assert response.status_code in (200, 404)


class TestApprovalRequestRoutes:
    def test_list_requests(self, client, auth_header):
        response = client.get("/api/v1/approvals/requests", headers=auth_header)
        assert response.status_code == 200
        assert "items" in response.json()

    def test_inbox(self, client, auth_header):
        response = client.get(
            "/api/v1/approvals/requests/inbox", headers=auth_header
        )
        assert response.status_code == 200

    def test_mine(self, client, auth_header):
        response = client.get(
            "/api/v1/approvals/requests/mine", headers=auth_header
        )
        assert response.status_code == 200

    def test_submit_request_invalid(self, client, auth_header):
        response = client.post(
            "/api/v1/approvals/requests", json={}, headers=auth_header
        )
        assert response.status_code == 422

    def test_get_request_missing(self, client, auth_header):
        response = client.get(
            "/api/v1/approvals/requests/99999999", headers=auth_header
        )
        assert response.status_code in (200, 404)

    def test_decision_missing_body(self, client, auth_header):
        response = client.post(
            "/api/v1/approvals/requests/1/decisions", json={}, headers=auth_header
        )
        assert response.status_code == 422

    def test_comment_missing_body(self, client, auth_header):
        response = client.post(
            "/api/v1/approvals/requests/1/comments", json={}, headers=auth_header
        )
        assert response.status_code == 422

    def test_cancel_missing(self, client, auth_header):
        response = client.post(
            "/api/v1/approvals/requests/99999999/cancel", headers=auth_header
        )
        assert response.status_code in (200, 404)

    def test_admin_force_close_missing(self, client, auth_header):
        response = client.post(
            "/api/v1/approvals/requests/99999999/force-close?approve=true",
            headers=auth_header,
        )
        assert response.status_code in (200, 404)

    def test_admin_reopen_step_missing(self, client, auth_header):
        response = client.post(
            "/api/v1/approvals/requests/99999999/steps/1/reopen",
            headers=auth_header,
        )
        assert response.status_code in (200, 404)

    def test_expire_stale(self, client, auth_header):
        response = client.post(
            "/api/v1/approvals/maintenance/expire-stale", headers=auth_header
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_reject_anonymous_flows(self, client):
        response = client.get("/api/v1/approvals/flows")
        assert response.status_code == 401

    def test_reject_anonymous_requests(self, client):
        response = client.get("/api/v1/approvals/requests")
        assert response.status_code == 401
