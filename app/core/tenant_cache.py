# app/core/tenant_cache.py
from __future__ import annotations

"""
Short-TTL, process-local cache for tenant resolution.

Why
---
Every request runs through ``TenantMiddleware`` (and, for authenticated
requests, ``AuthMiddleware``) which resolve the active tenant from the
**master** database — a lookup plus a lazy-load of the tenant's
subscriptions for the lifecycle gate. Under the app's polling UI (queues,
notifications, dashboards) this is one of the largest steady-state sources
of master-DB compute, even though tenant records change very rarely.

This module memoises resolved tenants for a few seconds. The cached
``Tenant`` is detached but has its scalar columns and its ``subscriptions``
relationship eagerly loaded, so the middleware's ``active_subscription`` /
trialing checks run without touching the database.

Safety
------
* TTL is short (default 60s) and configurable via ``TENANT_CACHE_TTL_SECONDS``;
  set it to ``0`` to disable caching entirely.
* Writes that change a tenant (status, domain, subscription lifecycle) should
  call :func:`invalidate` so changes take effect immediately rather than
  waiting out the TTL.
"""

import threading
import time
from typing import Optional

try:
    from app.core.config import settings
except Exception:  # pragma: no cover
    settings = None  # type: ignore[assignment]


def _ttl() -> float:
    try:
        return float(getattr(settings, "TENANT_CACHE_TTL_SECONDS", 60) or 0)
    except Exception:
        return 60.0


# (kind, key) -> (expiry_monotonic, tenant)
_cache: "dict[tuple[str, str], tuple[float, object]]" = {}
_lock = threading.Lock()


def _get(kind: str, key: str):
    ttl = _ttl()
    if ttl <= 0 or not key:
        return None
    now = time.monotonic()
    with _lock:
        entry = _cache.get((kind, key))
        if entry is None:
            return None
        if entry[0] <= now:
            _cache.pop((kind, key), None)
            return None
        return entry[1]


def _put(tenant) -> None:
    ttl = _ttl()
    if ttl <= 0 or tenant is None:
        return
    exp = time.monotonic() + ttl
    with _lock:
        try:
            _cache[("id", str(tenant.id))] = (exp, tenant)
            code = getattr(tenant, "code", None)
            if code:
                _cache[("code", code.strip().lower())] = (exp, tenant)
            for attr in ("domain_url", "custom_domain"):
                dom = getattr(tenant, attr, None)
                if dom:
                    _cache[("domain", dom.strip().lower())] = (exp, tenant)
        except Exception:
            pass


def _prime(db, tenant):
    """Force-load the columns + subscriptions the middleware reads, then
    detach the instance so it is safe to reuse across requests."""
    if tenant is None:
        return None
    try:
        _ = (
            tenant.id, tenant.code, tenant.name, tenant.status,
            tenant.db_connection_string, tenant.is_provisioned,
            tenant.domain_url, tenant.custom_domain,
        )
        # active_subscription is a property over .subscriptions — load it now
        # so the detached instance can evaluate the lifecycle gate offline.
        for sub in (tenant.subscriptions or []):
            _ = (sub.status, sub.is_active)
        db.expunge(tenant)
    except Exception:
        # If priming fails for any reason, don't cache a half-loaded instance.
        return None
    return tenant


def get_tenant_by_code(code: Optional[str]):
    if not code:
        return None
    key = code.strip().lower()
    cached = _get("code", key)
    if cached is not None:
        return cached
    from app.core.database import get_master_db_context
    from app.repositories.tenant_repository import TenantRepository
    with get_master_db_context() as db:
        tenant = _prime(db, TenantRepository(db).get_tenant_by_code(key))
        _put(tenant)
        return tenant


def get_tenant_by_domain(domain: Optional[str]):
    if not domain:
        return None
    key = domain.strip().lower()
    cached = _get("domain", key)
    if cached is not None:
        return cached
    from app.core.database import get_master_db_context
    from app.repositories.tenant_repository import TenantRepository
    with get_master_db_context() as db:
        tenant = _prime(db, TenantRepository(db).get_tenant_by_domain(key))
        _put(tenant)
        return tenant


def get_tenant_by_id(tenant_id: Optional[int]):
    if tenant_id is None:
        return None
    cached = _get("id", str(tenant_id))
    if cached is not None:
        return cached
    from app.core.database import get_master_db_context
    from app.repositories.tenant_repository import TenantRepository
    with get_master_db_context() as db:
        tenant = _prime(db, TenantRepository(db).get_tenant_by_id(tenant_id))
        _put(tenant)
        return tenant


def invalidate(tenant=None, *, tenant_id: Optional[int] = None, code: Optional[str] = None) -> None:
    """Drop cache entries for a tenant. With no arguments, clears everything."""
    with _lock:
        if tenant is None and tenant_id is None and code is None:
            _cache.clear()
            return
        keys: list[tuple[str, str]] = []
        if tenant is not None:
            try:
                keys.append(("id", str(tenant.id)))
                if getattr(tenant, "code", None):
                    keys.append(("code", tenant.code.strip().lower()))
                for attr in ("domain_url", "custom_domain"):
                    dom = getattr(tenant, attr, None)
                    if dom:
                        keys.append(("domain", dom.strip().lower()))
            except Exception:
                pass
        if tenant_id is not None:
            keys.append(("id", str(tenant_id)))
        if code:
            keys.append(("code", code.strip().lower()))
        for k in keys:
            _cache.pop(k, None)
