# app/tests/unit/test_dedicated_mode.py
"""
Dedicated (single-hospital) deployment mode: licence math, SaaS-path
blocking, and the middleware's dedicated dispatch.
"""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core import deployment
from app.core.config import settings


@pytest.fixture()
def dedicated(monkeypatch):
    monkeypatch.setattr(settings, "DEPLOYMENT_MODE", "dedicated")
    monkeypatch.setattr(settings, "LICENSE_GRACE_DAYS", 30)
    yield


# ---------------- licence math ----------------

def test_license_unenforced_without_date(dedicated, monkeypatch):
    monkeypatch.setattr(settings, "LICENSE_EXPIRES_AT", None)
    s = deployment.license_status()
    assert s["mode"] == "dedicated"
    assert s["blocked"] is False and s["in_grace"] is False


def test_license_warning_inside_30_days(dedicated, monkeypatch):
    monkeypatch.setattr(settings, "LICENSE_EXPIRES_AT", date.today() + timedelta(days=10))
    s = deployment.license_status()
    assert s["blocked"] is False
    assert s["days_left"] == 10
    assert "10 day" in s["message"]


def test_license_grace_then_block(dedicated, monkeypatch):
    monkeypatch.setattr(settings, "LICENSE_EXPIRES_AT", date.today() - timedelta(days=5))
    s = deployment.license_status()
    assert s["in_grace"] is True and s["blocked"] is False

    monkeypatch.setattr(settings, "LICENSE_EXPIRES_AT", date.today() - timedelta(days=31))
    s = deployment.license_status()
    assert s["blocked"] is True
    assert "renew" in s["message"].lower()


def test_saas_mode_never_blocks(monkeypatch):
    monkeypatch.setattr(settings, "DEPLOYMENT_MODE", "saas")
    monkeypatch.setattr(settings, "LICENSE_EXPIRES_AT", date.today() - timedelta(days=400))
    s = deployment.license_status()
    assert s["mode"] == "saas" and s["blocked"] is False


def test_saas_only_paths(dedicated):
    for p in ("/api/v1/saas/dashboard", "/api/v1/tenants",
              "/api/v1/subscription-billing/invoices",
              "/api/v1/developer/portal/apps", "/api/v1/backups/master"):
        assert deployment.is_saas_only_path(p), p
    for p in ("/api/v1/hmo/providers", "/api/v1/patients/",
              "/api/v1/tenant-modules", "/api/v1/accounting/journal-entries"):
        assert not deployment.is_saas_only_path(p), p


# ---------------- middleware behaviour ----------------

@pytest.fixture()
def dedicated_client(dedicated, monkeypatch):
    import app.middleware.tenant_middleware as tm
    from app.main import app

    class _FakeTenant:
        id = 1
        code = "main"
        name = "Test Hospital"
        db_connection_string = None

    from contextlib import contextmanager

    @contextmanager
    def _null_db():
        yield None

    monkeypatch.setattr(tm, "get_master_db_context", _null_db)
    monkeypatch.setattr(deployment, "get_or_create_dedicated_tenant",
                        lambda _db: _FakeTenant())
    monkeypatch.setattr(tm, "_DEDICATED_TENANT_CACHE", None)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_dedicated_hides_saas_surfaces(dedicated_client, monkeypatch):
    monkeypatch.setattr(settings, "LICENSE_EXPIRES_AT", None)
    r = dedicated_client.get("/api/v1/saas/dashboard/summary")
    assert r.status_code == 404
    assert "dedicated" in r.json()["detail"].lower()
    r = dedicated_client.get("/api/v1/tenants")
    assert r.status_code == 404


def test_dedicated_blocks_after_grace(dedicated_client, monkeypatch):
    monkeypatch.setattr(settings, "LICENSE_EXPIRES_AT",
                        date.today() - timedelta(days=90))
    r = dedicated_client.get("/api/v1/hmo/providers")
    assert r.status_code == 402
    assert r.json()["error_code"] == "LICENSE_EXPIRED"
    # health stays reachable so operators can diagnose
    r = dedicated_client.get("/health")
    assert r.status_code in (200, 404)  # whatever /health returns, never 402


def test_dedicated_warns_in_grace_with_headers(dedicated_client, monkeypatch):
    monkeypatch.setattr(settings, "LICENSE_EXPIRES_AT",
                        date.today() - timedelta(days=3))
    r = dedicated_client.get("/api/v1/system/deployment-info")
    assert r.status_code == 200
    assert r.headers.get("X-License-Notice")
    body = r.json()
    assert body["mode"] == "dedicated"
    assert body["license"]["in_grace"] is True


def test_deployment_info_in_saas_mode(monkeypatch):
    from app.main import app
    monkeypatch.setattr(settings, "DEPLOYMENT_MODE", "saas")
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/api/v1/system/deployment-info")
        assert r.status_code == 200
        assert r.json()["mode"] == "saas"
        assert r.json()["license"] is None
