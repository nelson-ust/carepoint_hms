"""
Unit tests for the offline signed-lease entitlement service. Pure: an RSA
keypair is generated in-test, leases are signed with it, and the public key is
installed via settings. No network, no DB.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from app.core.config import settings
import app.services.entitlement_service as ent


def _keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return priv, pub


@pytest.fixture()
def lease_env(tmp_path, monkeypatch):
    priv, pub = _keypair()
    monkeypatch.setattr(settings, "LICENSE_PUBLIC_KEY", pub, raising=False)
    monkeypatch.setattr(settings, "LICENSE_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "LICENSE_CARE_SAFE_FEATURES", "clinical,emergency", raising=False)
    ent.reset_for_tests()
    yield priv
    ent.reset_for_tests()


def _sign(priv, *, days, grace_days=14, modules=None):
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "stmary", "plan": "standard", "modules": modules or ["clinical", "reports"],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=days)).timestamp()),
        "grace_days": grace_days,
    }
    return jwt.encode(claims, priv, algorithm="RS256")


def test_valid_lease(lease_env):
    ent.install_token(_sign(lease_env, days=60))
    st = ent.status()
    assert st["source"] == "lease" and st["blocked"] is False
    assert "clinical" in st["enabled_modules"]
    assert ent.license_gate("reports") == "ok"


def test_expired_within_grace(lease_env):
    ent.install_token(_sign(lease_env, days=-3, grace_days=14))
    st = ent.status()
    assert st["in_grace"] is True and st["blocked"] is False


def test_expired_past_grace_blocks_non_care(lease_env):
    ent.install_token(_sign(lease_env, days=-30, grace_days=14))
    st = ent.status()
    assert st["blocked"] is True
    assert ent.license_gate("reports") == "block"
    # Care features are never blocked.
    assert ent.license_gate("clinical") == "ok"
    assert ent.license_gate("emergency") == "ok"


def test_tampered_signature_blocks(lease_env):
    other_priv, _ = _keypair()
    ent.install_token(_sign(other_priv, days=60))  # signed by the wrong key
    st = ent.status()
    assert st["blocked"] is True


def test_clock_rollback_blocks_non_care(lease_env):
    ent.install_token(_sign(lease_env, days=60))
    # Pretend we've seen a far-future trusted time, then "now" looks rolled back.
    ent.note_trusted_time(datetime.now(timezone.utc) + timedelta(days=400))
    st = ent.status()
    assert st["clock_ok"] is False and st["blocked"] is True
    assert ent.license_gate("clinical") == "ok"


def test_not_enforced_without_public_key(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LICENSE_PUBLIC_KEY", None, raising=False)
    monkeypatch.setattr(settings, "LICENSE_DIR", str(tmp_path), raising=False)
    ent.reset_for_tests()
    st = ent.status()
    assert st["source"] == "none" and st["blocked"] is False
    assert ent.license_gate("reports") == "ok"
