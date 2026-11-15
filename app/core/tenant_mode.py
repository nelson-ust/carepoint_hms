# app/core/tenant_mode.py
from __future__ import annotations

"""
Per-tenant deployment mode: each hospital opts into **cloud** (online-only),
**onprem** (offline/on-premise) or **hybrid** (on-premise with cloud sync).

The mode lives on the ``Tenant`` row (``deployment_mode``); the tenant
middleware resolves it once per request and stashes it in a context var, so the
storage / 2FA / licensing code can read it cheaply with no extra DB hit. When a
tenant has no explicit mode, a global default is derived from settings, which
preserves the previous behaviour.

Behaviour by mode
-----------------
                    cloud        onprem          hybrid
file storage        AWS S3       MinIO           S3 online / MinIO offline
2FA when offline    enforced     skipped         skipped
licence             live subs    signed lease    signed lease
cross-hospital      online       needs internet  needs internet
"""

import contextvars
from typing import Optional

from app.core.config import settings

CLOUD = "cloud"
ONPREM = "onprem"
HYBRID = "hybrid"
VALID = {CLOUD, ONPREM, HYBRID}

_SYNONYMS = {
    "cloud": CLOUD, "online": CLOUD, "saas": CLOUD,
    "onprem": ONPREM, "on-prem": ONPREM, "on_prem": ONPREM, "on-premise": ONPREM,
    "on_premise": ONPREM, "onpremise": ONPREM, "offline": ONPREM, "dedicated": ONPREM,
    "local": ONPREM,
    "hybrid": HYBRID, "mixed": HYBRID,
}

_current: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "deployment_mode", default=None
)


def normalize(value, default: Optional[str] = None) -> Optional[str]:
    if not value:
        return default
    return _SYNONYMS.get(str(value).strip().lower(), default)


def default_mode() -> str:
    """Global fallback when a tenant has no explicit mode."""
    m = normalize(getattr(settings, "DEFAULT_DEPLOYMENT_MODE", None))
    if m:
        return m
    if getattr(settings, "is_edge", False):
        return HYBRID
    if getattr(settings, "is_dedicated", False):
        return ONPREM
    return CLOUD


def set_current_mode(mode) -> None:
    _current.set(normalize(mode, default_mode()))


def clear_current_mode() -> None:
    _current.set(None)


def current_mode() -> str:
    return _current.get() or default_mode()


def resolve_for_tenant(tenant) -> str:
    m = normalize(getattr(tenant, "deployment_mode", None), None)
    if m:
        return m
    # Fall back to the deployment MODEL when the runtime mode was never persisted
    # (legacy tenants), so storage/backend selection stays consistent.
    model = str(getattr(tenant, "deployment_model", "") or "").strip().upper()
    if model == "ON_PREMISE":
        return ONPREM
    if model in ("CLOUD_PLATFORM", "CLOUD_DEDICATED"):
        return CLOUD
    return default_mode()


# --- behaviour predicates -------------------------------------------------

def offline_capable(mode: Optional[str] = None) -> bool:
    return (mode or current_mode()) in (ONPREM, HYBRID)


def skip_2fa_when_offline(mode: Optional[str] = None) -> bool:
    return (mode or current_mode()) in (ONPREM, HYBRID)


def enforce_lease(mode: Optional[str] = None) -> bool:
    return (mode or current_mode()) in (ONPREM, HYBRID)


def storage_backend_for(mode: Optional[str], online: bool) -> str:
    mode = mode or current_mode()
    if mode == CLOUD:
        return "s3"
    if mode == ONPREM:
        return "minio"
    return "s3" if online else "minio"  # hybrid


def backend_for_tenant(tenant) -> str:
    """Storage backend a tenant should use, chosen by its deployment MODEL (the
    SaaS onboarding choice) first, then its runtime mode:

        Cloud-Platform / Cloud-Dedicated -> AWS S3
        On-Premise                       -> MinIO
    """
    model = str(getattr(tenant, "deployment_model", "") or "").strip().upper()
    if model == "ON_PREMISE":
        return "minio"
    if model in ("CLOUD_PLATFORM", "CLOUD_DEDICATED"):
        return "s3"
    # Legacy tenants with no explicit model: fall back to the runtime mode.
    return "minio" if resolve_for_tenant(tenant) == ONPREM else "s3"
