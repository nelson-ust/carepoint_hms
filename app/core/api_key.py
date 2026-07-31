# app/core/api_key.py
from __future__ import annotations

"""
API-key generation and verification for third-party integration partners.

Format:  ``chp_<prefix12>_<secret43>``
- ``key_prefix`` = ``chp_<prefix12>`` is stored in cleartext for O(1) lookup.
- ``key_hash``   = SHA-256 of the *full* key is stored; the plaintext is shown
  to the operator once and never persisted.
API keys are high-entropy random strings, so a fast SHA-256 (not bcrypt) is the
appropriate, standard choice.
"""

import hashlib
import hmac
import secrets

_PREFIX = "chp"


def generate_api_key() -> tuple[str, str, str]:
    """Return ``(full_key, key_prefix, key_hash)``. Persist prefix+hash only."""
    prefix = f"{_PREFIX}_{secrets.token_hex(6)}"       # chp_ + 12 hex chars
    secret = secrets.token_urlsafe(32)
    full_key = f"{prefix}_{secret}"
    return full_key, prefix, hash_api_key(full_key)


def hash_api_key(full_key: str) -> str:
    return hashlib.sha256(full_key.strip().encode("utf-8")).hexdigest()


def extract_prefix(full_key: str) -> str | None:
    """Extract the ``chp_<prefix12>`` lookup prefix from a presented key."""
    parts = (full_key or "").strip().split("_")
    if len(parts) < 3 or parts[0] != _PREFIX:
        return None
    return f"{parts[0]}_{parts[1]}"


def verify_api_key(full_key: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_api_key(full_key), stored_hash or "")


# ---------------------------------------------------------------------------
# Generic prefixed-token helpers (used by the developer platform for both the
# data API keys and the dashboard/management tokens). Same hashing scheme as
# the integration keys above; only the human-readable prefix differs.
# ---------------------------------------------------------------------------

def generate_prefixed_key(scheme: str) -> tuple[str, str, str]:
    """Return ``(full_key, key_prefix, key_hash)`` for a token whose lookup
    prefix is ``<scheme>_<12hex>``. ``scheme`` is a short label such as
    ``"cpk"`` (developer data key) or ``"cpm"`` (dashboard mgmt token)."""
    prefix = f"{scheme}_{secrets.token_hex(6)}"
    secret = secrets.token_urlsafe(32)
    full_key = f"{prefix}_{secret}"
    return full_key, prefix, hash_api_key(full_key)


def extract_scheme_prefix(full_key: str) -> str | None:
    """Extract the ``<scheme>_<12hex>`` lookup prefix from any presented token."""
    parts = (full_key or "").strip().split("_")
    if len(parts) < 3:
        return None
    return f"{parts[0]}_{parts[1]}"
