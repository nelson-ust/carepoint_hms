# app/services/entitlement_service.py
from __future__ import annotations

"""
Offline entitlement ("licence lease") validation for on-site hospitals.

Online hospitals keep being validated by the live subscription machinery. An
on-site (edge) hospital instead holds a short, cryptographically SIGNED lease
issued by the cloud licence authority. The edge node carries only the PUBLIC
key, so it can VERIFY a lease but never FORGE one.

Lease = JWT (RS256) with claims:
    sub         tenant code the lease is bound to
    plan        plan code
    modules     list of enabled module/feature names (informational)
    seats       optional {role: limit}
    iat, exp    issued-at / hard expiry
    grace_days  extra days after exp before access is blocked
    node_id     optional EdgeNode binding
    license_id  unique id

Validation is local, cheap and fully offline. Leases auto-renew whenever the
hospital is online; air-gapped sites upload a signed lease file by hand. A
persisted monotonic high-water mark detects system-clock rollback.

This module never raises into a request path for internal errors — it fails
*open* for patient safety (returns "not enforced") rather than blocking care.
"""

import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import jwt, JWTError

from app.core.config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_CLOCK_SLACK = timedelta(days=1)  # tolerate modest clock jitter before alarming


# ---------------------------------------------------------------------------
# Paths / key material
# ---------------------------------------------------------------------------

def _store_dir() -> str:
    base = getattr(settings, "LICENSE_DIR", None)
    if not base:
        from app.utils.storage import uploads_base_dir
        base = os.path.join(uploads_base_dir(), ".license")
    os.makedirs(base, exist_ok=True)
    return base


def _lease_path() -> str:
    return os.path.join(_store_dir(), "lease.jwt")


def _hwm_path() -> str:
    return os.path.join(_store_dir(), "clock.hwm")


def _public_key() -> Optional[str]:
    key = getattr(settings, "LICENSE_PUBLIC_KEY", None)
    if not key:
        return None
    # Allow pointing at a PEM file as well as inlining the PEM.
    if os.path.isfile(key):
        try:
            with open(key, "r", encoding="utf-8") as fh:
                return fh.read()
        except Exception:
            return None
    return key.replace("\\n", "\n")


def _care_safe_features() -> set[str]:
    raw = getattr(settings, "LICENSE_CARE_SAFE_FEATURES", "") or ""
    return {p.strip().lower() for p in raw.split(",") if p.strip()}


# ---------------------------------------------------------------------------
# Clock high-water mark (rollback detection)
# ---------------------------------------------------------------------------

def _read_hwm() -> Optional[datetime]:
    try:
        with open(_hwm_path(), "r", encoding="utf-8") as fh:
            return datetime.fromisoformat(fh.read().strip())
    except Exception:
        return None


def note_trusted_time(ts: datetime) -> None:
    """Advance the high-water mark from a TRUSTED timestamp (a lease iat or a
    cloud server_time). Never advanced from the local clock alone."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    try:
        with _lock:
            cur = _read_hwm()
            if cur is None or ts > cur:
                with open(_hwm_path(), "w", encoding="utf-8") as fh:
                    fh.write(ts.isoformat())
    except Exception as exc:  # pragma: no cover - best effort
        logger.debug("Could not persist clock high-water mark: %s", exc)


def _clock_ok(now: datetime) -> bool:
    hwm = _read_hwm()
    if hwm is None:
        return True
    return now >= (hwm - _CLOCK_SLACK)


# ---------------------------------------------------------------------------
# Token verify / install / load
# ---------------------------------------------------------------------------

def verify_token(token: str) -> dict:
    """Verify signature + structure, returning claims. Expiry is checked by the
    caller (so we can apply the grace window). Raises JWTError on bad token."""
    pub = _public_key()
    if not pub:
        raise JWTError("No LICENSE_PUBLIC_KEY configured.")
    return jwt.decode(
        token, pub, algorithms=["RS256"],
        options={"verify_exp": False, "verify_aud": False, "verify_iss": False},
    )


def install_token(token: str) -> dict:
    """Verify and persist a lease (used by refresh + manual activation)."""
    claims = verify_token(token)
    with _lock:
        with open(_lease_path(), "w", encoding="utf-8") as fh:
            fh.write(token.strip())
    iat = claims.get("iat")
    if iat:
        try:
            note_trusted_time(datetime.fromtimestamp(int(iat), tz=timezone.utc))
        except Exception:
            pass
    return claims


def load_token() -> Optional[str]:
    try:
        with open(_lease_path(), "r", encoding="utf-8") as fh:
            return fh.read().strip() or None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Status / gating
# ---------------------------------------------------------------------------

def _not_enforced(reason: str) -> dict:
    return {
        "source": "none", "blocked": False, "in_grace": False,
        "licensed_until": None, "days_left": None, "plan": None,
        "enabled_modules": [], "clock_ok": True, "message": None, "reason": reason,
    }


def status() -> dict:
    """Current licence posture for this install. Fails OPEN (not enforced) on any
    internal/configuration problem so care is never blocked by a bug."""
    try:
        if not _public_key():
            return _not_enforced("no public key configured")
        token = load_token()
        if not token:
            return _not_enforced("no lease installed")

        try:
            claims = verify_token(token)
        except JWTError as exc:
            return {**_not_enforced("invalid signature"),
                    "source": "lease", "blocked": True,
                    "message": f"Licence is invalid ({exc}). Contact your vendor to re-activate."}

        now = datetime.now(timezone.utc)
        exp_ts = claims.get("exp")
        exp = datetime.fromtimestamp(int(exp_ts), tz=timezone.utc) if exp_ts else None
        grace_days = int(claims.get("grace_days", getattr(settings, "LICENSE_GRACE_DAYS", 14)) or 0)
        plan = claims.get("plan")
        modules = claims.get("modules") or []
        clock_ok = _clock_ok(now)

        out = {
            "source": "lease",
            "plan": plan,
            "enabled_modules": modules,
            "licensed_until": exp.date().isoformat() if exp else None,
            "clock_ok": clock_ok,
            "in_grace": False,
            "blocked": False,
            "days_left": None,
            "message": None,
        }

        if not clock_ok:
            out["blocked"] = True
            out["message"] = ("The system clock appears to have been set back. "
                              "Licence checks are paused until the time is corrected "
                              "or the hospital reconnects.")
            return out

        if exp is None:
            return out  # perpetual lease

        days_left = (exp.date() - now.date()).days
        out["days_left"] = days_left
        if days_left < 0:
            overdue = -days_left
            if overdue <= grace_days:
                out["in_grace"] = True
                out["message"] = (f"Licence expired on {exp.date().isoformat()}. "
                                  f"{grace_days - overdue} grace day(s) remain — reconnect to renew.")
            else:
                out["blocked"] = True
                out["message"] = (f"Licence expired on {exp.date().isoformat()} and the grace period "
                                  "has ended. Reconnect or upload a new licence to restore full access. "
                                  "Patient care remains available.")
        elif days_left <= 14:
            out["message"] = f"Licence renews in {days_left} day(s) — reconnect when possible."
        return out
    except Exception as exc:  # pragma: no cover - never block on a bug
        logger.warning("Entitlement status check failed open: %s", exc)
        return _not_enforced("status error")


def enabled_modules() -> list[str]:
    return status().get("enabled_modules") or []


def license_gate(feature_name: str) -> str:
    """Return "ok" or "block" for a feature on an offline install.

    Never blocks care-safe (clinical/emergency) features. Only blocks when the
    lease is definitively lapsed-past-grace or tampered.
    """
    st = status()
    if st.get("source") != "lease" or not st.get("blocked"):
        return "ok"
    if (feature_name or "").strip().lower() in _care_safe_features():
        return "ok"
    return "block"


# ---------------------------------------------------------------------------
# Renewal
# ---------------------------------------------------------------------------

def refresh_from_cloud() -> dict:
    """Fetch a fresh lease from the cloud authority when online. Best-effort."""
    from app.services import connectivity_service

    if not connectivity_service.is_online():
        return {"refreshed": False, "reason": "offline"}
    base = getattr(settings, "CLOUD_BASE_URL", None)
    if not base:
        return {"refreshed": False, "reason": "no CLOUD_BASE_URL"}
    try:
        import httpx

        tenant = getattr(settings, "DEDICATED_TENANT_CODE", None) or "main"
        url = base.rstrip("/") + f"/api/v1/licenses/issue?tenant={tenant}"
        resp = httpx.get(url, timeout=getattr(settings, "CONNECTIVITY_PROBE_TIMEOUT_SECONDS", 5))
        if resp.status_code == 200 and resp.json().get("token"):
            install_token(resp.json()["token"])
            return {"refreshed": True}
        return {"refreshed": False, "reason": f"HTTP {resp.status_code}"}
    except Exception as exc:
        logger.info("Licence refresh failed: %s", exc)
        return {"refreshed": False, "reason": str(exc)}


def refresh_async() -> None:
    def _run():
        try:
            refresh_from_cloud()
        except Exception as exc:  # pragma: no cover
            logger.debug("async licence refresh error: %s", exc)
    threading.Thread(target=_run, daemon=True).start()


# ---------------------------------------------------------------------------
# Authority (cloud) — sign a lease. Only works where a PRIVATE key is set.
# ---------------------------------------------------------------------------

def sign_lease(*, tenant: str, plan: str, modules: list[str],
               lease_days: Optional[int] = None, grace_days: Optional[int] = None,
               node_id: Optional[str] = None, seats: Optional[dict] = None) -> str:
    priv = getattr(settings, "LICENSE_PRIVATE_KEY", None)
    priv = priv.get_secret_value() if hasattr(priv, "get_secret_value") else priv
    if not priv:
        raise RuntimeError("LICENSE_PRIVATE_KEY is not configured on this node.")
    priv = priv.replace("\\n", "\n") if isinstance(priv, str) else priv
    now = datetime.now(timezone.utc)
    days = int(lease_days or getattr(settings, "LICENSE_LEASE_DAYS", 60))
    import uuid as _uuid
    claims = {
        "sub": tenant,
        "plan": plan,
        "modules": modules,
        "seats": seats or {},
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=days)).timestamp()),
        "grace_days": int(grace_days if grace_days is not None else getattr(settings, "LICENSE_GRACE_DAYS", 14)),
        "node_id": node_id,
        "license_id": _uuid.uuid4().hex,
    }
    return jwt.encode(claims, priv, algorithm="RS256")


def reset_for_tests() -> None:
    try:
        for p in (_lease_path(), _hwm_path()):
            if os.path.exists(p):
                os.remove(p)
    except Exception:
        pass
