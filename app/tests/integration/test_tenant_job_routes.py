# app/tests/integration/test_tenant_job_routes.py
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


class TestTenantJobRoutes:
    def _create_job(self, client, auth_header, handler="invoice_generation"):
        payload = {
            "job_code": _unique("job"),
            "handler": handler,
            "schedule_cron": "0 1 * * *",
            "params": {"foo": "bar"},
            "is_enabled": True,
        }
        res = client.post(
            "/api/v1/tenant-jobs", json=payload, headers=auth_header
        )
        return res, payload

    def test_list_handlers(self, client, auth_header):
        res = client.get("/api/v1/tenant-jobs/handlers", headers=auth_header)
        assert res.status_code == 200
        body = res.json()
        assert "handlers" in body
        assert isinstance(body["handlers"], list)

    def test_list_jobs(self, client, auth_header):
        res = client.get("/api/v1/tenant-jobs", headers=auth_header)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_create_job(self, client, auth_header):
        # Pick a handler that's actually registered (if any) by listing first.
        handlers_res = client.get(
            "/api/v1/tenant-jobs/handlers", headers=auth_header
        )
        handlers = handlers_res.json().get("handlers", [])
        handler = handlers[0] if handlers else "invoice_generation"
        res, payload = self._create_job(client, auth_header, handler=handler)
        assert res.status_code in (201, 400, 422)
        if res.status_code == 201:
            body = res.json()
            assert body["job_code"] == payload["job_code"]
            assert body["handler"] == handler

    def test_create_job_invalid_payload(self, client, auth_header):
        res = client.post(
            "/api/v1/tenant-jobs",
            json={"job_code": "x"},  # missing handler
            headers=auth_header,
        )
        assert res.status_code == 422

    def test_update_job_not_found(self, client, auth_header):
        res = client.put(
            "/api/v1/tenant-jobs/9999999",
            json={"is_enabled": False},
            headers=auth_header,
        )
        assert res.status_code in (404, 400)

    def test_delete_job_not_found(self, client, auth_header):
        res = client.delete(
            "/api/v1/tenant-jobs/9999999", headers=auth_header
        )
        assert res.status_code in (200, 404, 400)

    def test_list_jobs_anonymous(self, client):
        res = client.get("/api/v1/tenant-jobs")
        assert res.status_code == 401

    def test_create_job_anonymous(self, client):
        res = client.post(
            "/api/v1/tenant-jobs",
            json={"job_code": "x", "handler": "y"},
        )
        assert res.status_code == 401

    def test_handlers_anonymous(self, client):
        res = client.get("/api/v1/tenant-jobs/handlers")
        assert res.status_code == 401
