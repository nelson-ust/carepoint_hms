# app/tests/integration/test_template_routes.py
from __future__ import annotations

"""
Integration tests for template management routes.

Covers /api/v1/templates/notifications and /api/v1/templates/documents
list/create endpoints.
"""

import pytest

from app.tests.conftest import HAS_TEST_DB
from app.tests.integration.test_auth_routes import _login, _bearer_headers, _unique

pytestmark = pytest.mark.skipif(
    not HAS_TEST_DB,
    reason="CAREPOINT_HMS_DATABASE_URL not configured for integration tests.",
)


@pytest.fixture()
def auth_header(client, admin_user):
    res = _login(client, admin_user["username"], admin_user["password"])
    token = res.json()["tokens"]["access_token"]
    return _bearer_headers(token)


def _notification_payload(channel: str = "EMAIL") -> dict:
    return {
        "name": _unique("Notify Tpl"),
        "code": _unique("NTPL").upper(),
        "channel": channel,
        "subject_template": "Hello {{ patient.name }}",
        "body_template": "Hi {{ patient.name }}, this is a test message.",
    }


def _document_payload(template_type: str = "INVOICE") -> dict:
    return {
        "name": _unique("Doc Tpl"),
        "code": _unique("DTPL").upper(),
        "template_type": template_type,
        "body_html": "<html><body>Hello {{ patient.name }}</body></html>",
        "is_default": False,
    }


class TestNotificationTemplateRoutes:
    def test_list_returns_array(self, client, auth_header):
        res = client.get("/api/v1/templates/notifications", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_create_happy_path(self, client, auth_header):
        res = client.post(
            "/api/v1/templates/notifications",
            json=_notification_payload(),
            headers=auth_header,
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert "id" in body
        assert body["body_template"]

    def test_create_validates_missing_body_template(self, client, auth_header):
        bad = _notification_payload()
        bad.pop("body_template")
        res = client.post(
            "/api/v1/templates/notifications", json=bad, headers=auth_header
        )
        assert res.status_code == 422

    def test_create_rejects_invalid_channel(self, client, auth_header):
        bad = _notification_payload(channel="NOT_A_CHANNEL")
        res = client.post(
            "/api/v1/templates/notifications", json=bad, headers=auth_header
        )
        assert res.status_code == 422

    def test_anonymous_list_returns_401(self, client):
        res = client.get("/api/v1/templates/notifications")
        assert res.status_code == 401

    def test_anonymous_create_returns_401(self, client):
        res = client.post(
            "/api/v1/templates/notifications", json=_notification_payload()
        )
        assert res.status_code == 401


class TestDocumentTemplateRoutes:
    def test_list_returns_array(self, client, auth_header):
        res = client.get("/api/v1/templates/documents", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_create_happy_path(self, client, auth_header):
        res = client.post(
            "/api/v1/templates/documents",
            json=_document_payload(),
            headers=auth_header,
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert "id" in body
        assert body["body_html"]

    def test_create_validates_missing_html(self, client, auth_header):
        bad = _document_payload()
        bad.pop("body_html")
        res = client.post(
            "/api/v1/templates/documents", json=bad, headers=auth_header
        )
        assert res.status_code == 422

    def test_create_rejects_invalid_type(self, client, auth_header):
        bad = _document_payload(template_type="NOT_A_TYPE")
        res = client.post(
            "/api/v1/templates/documents", json=bad, headers=auth_header
        )
        assert res.status_code == 422

    def test_anonymous_list_returns_401(self, client):
        res = client.get("/api/v1/templates/documents")
        assert res.status_code == 401

    def test_anonymous_create_returns_401(self, client):
        res = client.post(
            "/api/v1/templates/documents", json=_document_payload()
        )
        assert res.status_code == 401
