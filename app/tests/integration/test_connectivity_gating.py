"""
Integration tests for offline-resilience gating.

Covers:
* the public connectivity endpoints (probe / status / refresh), and
* that a cross-hospital operation (an inter-facility referral route) is blocked
  with HTTP 503 when the node is offline, while the local clinic flow is not.

The suite is skipped unless a test database is configured (same gate the rest of
the integration suite uses).
"""
from __future__ import annotations

import pytest

from app.tests.conftest import HAS_TEST_DB
from app.tests.integration.test_auth_routes import _login, _bearer_headers

pytestmark = pytest.mark.skipif(
    not HAS_TEST_DB,
    reason="CAREPOINT_HMS_DATABASE_URL not configured for integration tests.",
)


# --------------------------------------------------------------------------
# Public connectivity endpoints
# --------------------------------------------------------------------------

class TestConnectivityEndpoints:
    def test_probe_is_public_and_ok(self, client):
        res = client.get("/api/v1/connectivity/probe")
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert "server_time" in body

    def test_status_shape(self, client):
        res = client.get("/api/v1/connectivity/status")
        assert res.status_code == 200
        body = res.json()
        assert "online" in body and "mode" in body
        assert isinstance(body["gated_operations"], list)
        assert "referral.inter_facility.create" in body["gated_operations"]

    def test_refresh_returns_status(self, client):
        res = client.post("/api/v1/connectivity/refresh")
        assert res.status_code == 200
        assert "online" in res.json()

    def test_status_reflects_forced_offline(self, client, monkeypatch):
        from app.core.config import settings
        import app.services.connectivity_service as cs

        monkeypatch.setattr(settings, "CONNECTIVITY_FORCE_OFFLINE", True, raising=False)
        cs.reset_cache_for_tests()
        res = client.get("/api/v1/connectivity/status")
        assert res.status_code == 200
        assert res.json()["online"] is False


# --------------------------------------------------------------------------
# Cross-hospital gating
# --------------------------------------------------------------------------

@pytest.fixture()
def superuser_header(client, make_user):
    """A superuser bearer header — bypasses permission checks so the online
    gate is the deciding factor on gated routes."""
    password = "Password123!"
    user = make_user(password=password, is_superuser=True)
    res = _login(client, user.username, password)
    if res.status_code != 200:
        pytest.skip(f"login failed: {res.status_code}")
    data = res.json()
    token = data.get("tokens", {}).get("access_token") or data.get("access_token")
    if not token:
        pytest.skip("no access token in login response")
    return _bearer_headers(token)


class TestCrossHospitalGating:
    OUTGOING = "/api/v1/referrals/inter-facility/outgoing"

    def test_inter_facility_blocked_when_offline(self, client, superuser_header, monkeypatch):
        from app.core.config import settings
        import app.services.connectivity_service as cs

        # Confirm the route is reachable for this user when online; otherwise the
        # environment lacks the clinical plan/seed and this assertion is moot.
        monkeypatch.setattr(settings, "CONNECTIVITY_ASSUME_ONLINE", True, raising=False)
        monkeypatch.setattr(settings, "CONNECTIVITY_FORCE_OFFLINE", False, raising=False)
        cs.reset_cache_for_tests()
        online_res = client.get(self.OUTGOING, headers=superuser_header)
        if online_res.status_code in (401, 402, 403):
            pytest.skip(f"route gated by auth/plan in this env ({online_res.status_code}); gate test N/A")
        assert online_res.status_code != 503

        # Now go offline — the same request must be blocked with 503.
        monkeypatch.setattr(settings, "CONNECTIVITY_ASSUME_ONLINE", False, raising=False)
        monkeypatch.setattr(settings, "CONNECTIVITY_FORCE_OFFLINE", True, raising=False)
        cs.reset_cache_for_tests()
        offline_res = client.get(self.OUTGOING, headers=superuser_header)
        assert offline_res.status_code == 503
        assert offline_res.json().get("error_code") == "OFFLINE" or "offline" in str(offline_res.json()).lower()

    def test_local_patient_registry_still_works_offline(self, client, superuser_header, monkeypatch):
        """Sanity: a LOCAL clinic-flow read is NOT gated when offline."""
        from app.core.config import settings
        import app.services.connectivity_service as cs

        monkeypatch.setattr(settings, "CONNECTIVITY_FORCE_OFFLINE", True, raising=False)
        cs.reset_cache_for_tests()
        res = client.get("/api/v1/patients?skip=0&limit=1", headers=superuser_header)
        # Whatever the env, the local route is never blocked for being offline.
        assert res.status_code != 503
