"""
Unit tests for the connectivity service — the decision layer that gates
cross-hospital operations when an on-site deployment is offline.

These are pure (no database, no network): the cloud probe is monkeypatched and
the deployment posture is driven through ``settings``. They run with a plain
``pytest`` invocation.
"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.exceptions import OfflineError
import app.services.connectivity_service as cs


@pytest.fixture(autouse=True)
def _clean_connectivity(monkeypatch):
    """Reset overrides + probe cache around every test."""
    monkeypatch.setattr(settings, "CONNECTIVITY_FORCE_OFFLINE", False, raising=False)
    monkeypatch.setattr(settings, "CONNECTIVITY_ASSUME_ONLINE", False, raising=False)
    monkeypatch.setattr(settings, "CLOUD_BASE_URL", None, raising=False)
    cs.reset_cache_for_tests()
    yield
    cs.reset_cache_for_tests()


def test_central_cloud_is_always_online():
    # No CLOUD_BASE_URL -> this instance IS the cloud -> always online.
    status = cs.get_status()
    assert status["online"] is True
    assert status["mode"] == "cloud"
    assert cs.is_online() is True


def test_assume_online_override_skips_probing(monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_BASE_URL", "https://cloud.example", raising=False)
    monkeypatch.setattr(settings, "CONNECTIVITY_ASSUME_ONLINE", True, raising=False)
    # Probe must never be called when assume-online is set.
    def _boom():
        raise AssertionError("probe should not run under CONNECTIVITY_ASSUME_ONLINE")
    monkeypatch.setattr(cs, "_probe_cloud", _boom)
    assert cs.get_status()["online"] is True


def test_force_offline_override():
    object.__setattr__(settings, "CONNECTIVITY_FORCE_OFFLINE", True)
    try:
        status = cs.get_status()
        assert status["online"] is False
        assert status["mode"] == "forced"
    finally:
        object.__setattr__(settings, "CONNECTIVITY_FORCE_OFFLINE", False)


def test_edge_node_online_when_cloud_reachable(monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_BASE_URL", "https://cloud.example", raising=False)
    monkeypatch.setattr(cs, "_probe_cloud", lambda: (True, "Reached the central cloud.", "2026-11-09T00:00:00Z"))
    status = cs.get_status(force_refresh=True)
    assert status["online"] is True
    assert status["mode"] == "edge"


def test_edge_node_offline_when_cloud_unreachable(monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_BASE_URL", "https://cloud.example", raising=False)
    monkeypatch.setattr(cs, "_probe_cloud", lambda: (False, "Cloud unreachable (ConnectError).", None))
    status = cs.get_status(force_refresh=True)
    assert status["online"] is False
    assert status["mode"] == "edge"
    assert "unreachable" in status["reason"].lower()


def test_probe_result_is_cached(monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_BASE_URL", "https://cloud.example", raising=False)
    monkeypatch.setattr(settings, "CONNECTIVITY_PROBE_TTL_SECONDS", 60, raising=False)
    calls = {"n": 0}

    def _probe():
        calls["n"] += 1
        return True, "ok", None

    monkeypatch.setattr(cs, "_probe_cloud", _probe)
    cs.get_status(force_refresh=True)   # 1st probe
    cs.get_status()                     # cached
    cs.get_status()                     # cached
    assert calls["n"] == 1


def test_require_online_passes_when_online():
    # cloud mode -> online -> no raise
    cs.require_online("referral.inter_facility.create")


def test_require_online_raises_offline_error(monkeypatch):
    object.__setattr__(settings, "CONNECTIVITY_FORCE_OFFLINE", True)
    try:
        with pytest.raises(OfflineError) as exc:
            cs.require_online("interoperability.data_exchange")
        # Message is human + carries the operation in detail.
        assert "internet" in str(exc.value.message).lower()
        assert exc.value.detail["operation"] == "interoperability.data_exchange"
        assert exc.value.status_code == 503
    finally:
        object.__setattr__(settings, "CONNECTIVITY_FORCE_OFFLINE", False)


def test_status_exposes_gated_operations():
    ops = cs.get_status()["gated_operations"]
    assert "referral.inter_facility.create" in ops
    assert "interoperability.data_exchange" in ops
    assert "emergency.cross_hospital" in ops
