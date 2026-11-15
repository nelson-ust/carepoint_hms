# app/services/connectivity_service.py
from __future__ import annotations

"""
Connectivity service — decides, at request time, whether THIS deployment can
currently reach the central cloud.

Background
----------
A hospital may run CarePoint on-site ("edge" deployment) with little or no
internet. The local clinic flow — registration, triage, consultation, lab,
pharmacy, billing, the queue — must keep working fully offline. A small set of
operations, however, cross the hospital boundary and genuinely need the central
cloud:

* inter-facility (cross-hospital) referrals — outbound and inbound,
* cross-hospital data exchange (interoperability / medical-record pull),
* the online steps of Accident & Emergency care (pulling another hospital's
  record for the patient, referring out).

Those routes depend on :func:`require_online`, which raises
:class:`~app.core.exceptions.OfflineError` (HTTP 503) when the node is offline.
Registering and stabilising an A&E patient locally is NOT gated — only the
steps that truly need the internet.

How "online" is decided
------------------------
* The central cloud has no ``CLOUD_BASE_URL`` -> always online.
* ``CONNECTIVITY_ASSUME_ONLINE`` -> always online (ops/testing override).
* ``CONNECTIVITY_FORCE_OFFLINE`` -> always offline (ops/testing override).
* Otherwise the edge node probes ``CLOUD_BASE_URL + CONNECTIVITY_PROBE_PATH``
  with a short timeout. The result is cached for
  ``CONNECTIVITY_PROBE_TTL_SECONDS`` so gated requests don't each re-probe.
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.config import settings
from app.core.exceptions import OfflineError

logger = logging.getLogger(__name__)


# Operations that require cloud connectivity, mapped to a human label used in
# error messages and surfaced to the frontend.
GATED_OPERATIONS: dict[str, str] = {
    "referral.inter_facility.create": "Sending a referral to another hospital",
    "referral.inter_facility.respond": "Responding to a referral from another hospital",
    "referral.inter_facility.import": "Accepting a referral from another hospital",
    "referral.inter_facility.read": "Opening an inter-hospital referral record",
    "interoperability.data_exchange": "Exchanging patient records with another hospital",
    "emergency.cross_hospital": "Pulling a cross-hospital record for an A&E patient",
}


@dataclass
class _ProbeCache:
    online: bool = False
    checked_monotonic: float = 0.0
    reason: str = "not yet probed"
    cloud_time: Optional[str] = None


_cache = _ProbeCache()
_lock = threading.Lock()


def _probe_cloud() -> tuple[bool, str, Optional[str]]:
    """Single blocking probe of the cloud's connectivity endpoint."""
    base = (settings.CLOUD_BASE_URL or "").rstrip("/")
    url = base + settings.CONNECTIVITY_PROBE_PATH
    try:
        resp = httpx.get(url, timeout=settings.CONNECTIVITY_PROBE_TIMEOUT_SECONDS)
        if resp.status_code == 200:
            cloud_time = None
            try:
                cloud_time = resp.json().get("server_time")
            except Exception:  # noqa: BLE001 - non-JSON body is still "reachable"
                pass
            return True, "Reached the central cloud.", cloud_time
        return False, f"Cloud probe returned HTTP {resp.status_code}.", None
    except Exception as exc:  # noqa: BLE001 - any network/DNS/timeout error == offline
        logger.debug("Cloud probe failed: %s", exc)
        return False, f"Cloud unreachable ({type(exc).__name__}).", None


def _refresh_if_stale(force: bool = False) -> None:
    ttl = max(0, int(settings.CONNECTIVITY_PROBE_TTL_SECONDS or 0))
    now = time.monotonic()
    with _lock:
        is_fresh = _cache.checked_monotonic > 0 and (now - _cache.checked_monotonic) < ttl
        if is_fresh and not force:
            return
    online, reason, cloud_time = _probe_cloud()
    with _lock:
        _cache.online = online
        _cache.reason = reason
        _cache.cloud_time = cloud_time
        _cache.checked_monotonic = time.monotonic()


def _status(online: bool, reason: str, *, mode: str,
            cloud_time: Optional[str] = None,
            checked_ago: Optional[float] = None) -> dict:
    return {
        "online": bool(online),
        "mode": mode,  # "cloud" | "edge" | "forced"
        "reason": reason,
        "server_time": datetime.now(timezone.utc).isoformat(),
        "cloud_time": cloud_time,
        "last_checked_seconds_ago": checked_ago,
        "cloud_base_url": settings.CLOUD_BASE_URL,
        "gated_operations": sorted(GATED_OPERATIONS.keys()),
    }


def get_status(*, force_refresh: bool = False) -> dict:
    """Return the current connectivity posture of this deployment."""
    if settings.CONNECTIVITY_FORCE_OFFLINE:
        return _status(False, "Forced offline by configuration.", mode="forced")
    if settings.CONNECTIVITY_ASSUME_ONLINE:
        return _status(True, "Assumed online by configuration.", mode="forced")
    if not settings.is_edge:
        # The central cloud itself (no upstream) is always "online".
        return _status(True, "Central cloud deployment.", mode="cloud")

    _refresh_if_stale(force=force_refresh)
    with _lock:
        ago = (round(time.monotonic() - _cache.checked_monotonic, 1)
               if _cache.checked_monotonic else None)
        return _status(_cache.online, _cache.reason, mode="edge",
                       cloud_time=_cache.cloud_time, checked_ago=ago)


def is_online(*, force_refresh: bool = False) -> bool:
    return bool(get_status(force_refresh=force_refresh)["online"])


def require_online(operation: str) -> None:
    """Raise :class:`OfflineError` when this node can't currently reach the cloud.

    ``operation`` is one of :data:`GATED_OPERATIONS`; an unknown key still gates
    (fails safe) with a generic label.
    """
    status = get_status()
    if status["online"]:
        return
    label = GATED_OPERATIONS.get(operation, "This action")
    raise OfflineError(
        message=(
            f"{label} needs an internet connection, but this hospital is "
            f"currently offline ({status['reason']}). It becomes available "
            "again automatically once connectivity is restored."
        ),
        detail={"operation": operation, "connectivity": status},
    )


def reset_cache_for_tests() -> None:
    """Clear the probe cache (used by tests that flip connectivity)."""
    with _lock:
        _cache.online = False
        _cache.checked_monotonic = 0.0
        _cache.reason = "not yet probed"
        _cache.cloud_time = None
