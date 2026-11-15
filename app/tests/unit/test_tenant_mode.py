"""Per-tenant deployment mode resolution + behaviour predicates (pure)."""
from __future__ import annotations

import pytest

from app.core.config import settings
import app.core.tenant_mode as tm


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(settings, "DEFAULT_DEPLOYMENT_MODE", None, raising=False)
    tm.clear_current_mode()
    yield
    tm.clear_current_mode()


def test_normalize_synonyms():
    assert tm.normalize("online") == tm.CLOUD
    assert tm.normalize("offline") == tm.ONPREM
    assert tm.normalize("on-premise") == tm.ONPREM
    assert tm.normalize("hybrid") == tm.HYBRID
    assert tm.normalize("", "cloud") == "cloud"
    assert tm.normalize("nonsense", tm.CLOUD) == tm.CLOUD


def test_default_mode_from_setting(monkeypatch):
    monkeypatch.setattr(settings, "DEFAULT_DEPLOYMENT_MODE", "hybrid", raising=False)
    assert tm.default_mode() == tm.HYBRID


def test_resolve_for_tenant_prefers_tenant_value(monkeypatch):
    monkeypatch.setattr(settings, "DEFAULT_DEPLOYMENT_MODE", "cloud", raising=False)

    class T:
        deployment_mode = "offline"

    assert tm.resolve_for_tenant(T()) == tm.ONPREM

    class U:
        deployment_mode = None

    assert tm.resolve_for_tenant(U()) == tm.CLOUD  # falls back to default


def test_storage_backend_by_mode():
    assert tm.storage_backend_for(tm.CLOUD, online=False) == "s3"
    assert tm.storage_backend_for(tm.ONPREM, online=True) == "minio"
    assert tm.storage_backend_for(tm.HYBRID, online=True) == "s3"
    assert tm.storage_backend_for(tm.HYBRID, online=False) == "minio"


def test_predicates_by_mode():
    assert tm.skip_2fa_when_offline(tm.CLOUD) is False
    assert tm.skip_2fa_when_offline(tm.ONPREM) is True
    assert tm.enforce_lease(tm.HYBRID) is True
    assert tm.enforce_lease(tm.CLOUD) is False


def test_current_mode_contextvar():
    tm.set_current_mode("onprem")
    assert tm.current_mode() == tm.ONPREM
    tm.clear_current_mode()
    # back to default (cloud, since no setting + not edge in test env)
    assert tm.current_mode() in tm.VALID
