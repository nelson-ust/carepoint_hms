# app/middleware/tenant_middleware.py
"""
Tenant resolution middleware.

Identifies the active tenant for every inbound request using the following
resolution order (first match wins):

    1. ``X-Tenant-Code`` request header        (explicit tenant code)
    2. ``X-Tenant`` request header              (back-compat alias)
    3. ``X-Tenant-Domain`` request header       (explicit custom domain)
    4. Custom domain match on Host header       (e.g. ``portal.acmeclinic.com``)
    5. Subdomain match on Host header           (e.g. ``acme.carepointhms.com``)
    6. Tenant ID embedded in a JWT bearer token (login context fallback)

If a tenant is resolved successfully, it is placed into the request-scoped
context (:func:`app.core.multitenancy.set_current_tenant`) and downstream
DB sessions are routed to the tenant database via :func:`get_db`.

System and SaaS-administration paths bypass tenant resolution because they
operate against the master database.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.database import get_master_db_context
from app.core.enums import SubscriptionStatus
from app.core.multitenancy import set_current_tenant
from app.repositories.tenant_repository import TenantRepository

logger = logging.getLogger(__name__)

try:
    from jose import JWTError, jwt as _jose_jwt
except Exception:  # pragma: no cover - jose is a hard dependency in prod
    _jose_jwt = None
    JWTError = Exception


# ---------------------------------------------------------------------------
# Paths that NEVER need tenant resolution.
# These hit the master DB or are infrastructure endpoints.
# ---------------------------------------------------------------------------
IGNORE_EXACT: set[str] = {
    "/",
    "/favicon.ico",
    "/health",
    "/health/db",
    "/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
}

# Path prefixes that should bypass tenant resolution.
IGNORE_PREFIXES: tuple[str, ...] = (
    "/static",
    "/uploads",
    "/api/v1/health",
    "/api/v1/ready",
    # Edge-node sync uses its own bearer token; tenant context is
    # resolved from the node row, not from the request URL.
    "/api/v1/edge-nodes",
    "/api/v1/sync",
    "/api/v1/connectivity",
    "/api/v1/backups/master",   # Master backups (SaaS level)
    # SaaS tenant administration (register / approve / provision-s3 / list)
    # lives entirely in the MASTER database (the router depends on
    # get_master_db) — tenant resolution is never needed and must never be
    # able to 404 these calls based on the Host header.
    "/api/v1/tenants",
    # Developer platform. Registration / portal management operate on the
    # MASTER database, and the data API resolves the holding tenant itself from
    # the {tenant_code} path segment (via get_tenant_db_context) plus a grant
    # check — so host-based tenant resolution must never gate or 404 these.
    "/api/v1/developer",
    # Partner inbound integration API: the third-party's API key identifies the
    # owning tenant (bound by the api-key dependency), so host-based resolution
    # must not gate it. NOTE: only the key-authed "/integration/v1" surface —
    # the JWT-authed "/integration/partners" admin routes stay tenant-scoped.
    "/api/v1/integration/v1",
    # Consent-gated medical-record sharing PUBLIC surface: patient decisions and
    # the one-time link are token-authenticated and operate on the master DB /
    # an explicitly-resolved holding tenant, so host tenant resolution must not
    # gate them. The staff "/medical-access/requests" routes stay tenant-scoped.
    "/api/v1/medical-access/public",
    # Public membership-card QR verification: token-free, resolves the holding
    # tenant from the ``h`` (hospital code) query param itself.
    "/api/v1/membership-cards/public",
    "/docs",
    "/redoc",
    "/openapi.json",
)

# Hostnames / first-labels that represent the public marketing site, not a
# tenant subdomain. Configurable via settings.PUBLIC_HOSTS.
DEFAULT_RESERVED_LABELS = {
    "www",
    "api",
    "app",
    "admin",
    "saas",
    "carepointhms",
    "carepoint-hms",    # Render root deployment: carepoint-hms.onrender.com
    "localhost",
    "testserver",   # Starlette TestClient default host
    "testclient",   # Starlette TestClient alternate host
    "127",
    "0",
}


def _resolved_base_domain() -> Optional[str]:
    """Return the canonical base domain (e.g. ``carepointhms.com``)."""
    base = getattr(settings, "BASE_DOMAIN", None) or getattr(settings, "APP_BASE_DOMAIN", None)
    if base:
        return str(base).strip().lower()
    return None


def _resolved_reserved_labels() -> set[str]:
    """Return the set of subdomain labels that should be ignored for tenant resolution."""
    extra = getattr(settings, "PUBLIC_HOSTS", None) or []
    return DEFAULT_RESERVED_LABELS | {str(x).strip().lower() for x in extra if x}


def _is_ignored_path(path: str) -> bool:
    if path in IGNORE_EXACT:
        return True
    return any(path == p or path.startswith(p + "/") or path.startswith(p) for p in IGNORE_PREFIXES)


def _extract_tenant_id_from_jwt(request: Request) -> Optional[int]:
    """
    Best-effort extraction of ``tenant_id`` from a bearer token.

    This is intentionally tolerant: signature/expiry validation is the job of
    the auth dependency. The middleware only inspects the token to discover
    which tenant database to bind the request to.
    """
    if _jose_jwt is None:
        return None

    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None

    try:
        payload = _jose_jwt.decode(
            token,
            settings.secret_key_value,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False, "verify_aud": False},
        )
    except JWTError:
        return None
    except Exception:
        return None

    tenant_id = payload.get("tenant_id")
    try:
        return int(tenant_id) if tenant_id is not None else None
    except (TypeError, ValueError):
        return None


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Resolve and bind the active tenant to the request context.

    Resolution strategy is documented at the module level. On success, the
    tenant is stored via :func:`set_current_tenant` and downstream DB
    dependencies will operate against the tenant database.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 1. System / SaaS paths bypass tenant context entirely.
        if _is_ignored_path(path):
            return await call_next(request)

        # 2. Read tenant identification hints.
        host_header = (request.headers.get("host") or "").split(":")[0].strip().lower()
        tenant_code_hdr = (
            request.headers.get("x-tenant-code")
            or request.headers.get("x-tenant")
        )
        tenant_domain_hdr = request.headers.get("x-tenant-domain")
        if tenant_code_hdr:
            tenant_code_hdr = tenant_code_hdr.strip().lower()
        if tenant_domain_hdr:
            tenant_domain_hdr = tenant_domain_hdr.strip().lower()

        # 3. Resolve the tenant from the master database.
        try:
            with get_master_db_context() as db:
                repo = TenantRepository(db)
                tenant = None

                # 3a. Explicit tenant code.
                if tenant_code_hdr:
                    tenant = repo.get_tenant_by_code(tenant_code_hdr)

                # 3b. Explicit custom domain header.
                if tenant is None and tenant_domain_hdr:
                    tenant = repo.get_tenant_by_domain(tenant_domain_hdr)

                # 3c. Custom domain match on Host header.
                if tenant is None and host_header:
                    tenant = repo.get_tenant_by_domain(host_header)

                # 3d. Subdomain match on Host header.
                if tenant is None and host_header:
                    first_label = host_header.split(".")[0]
                    reserved = _resolved_reserved_labels()
                    base_domain = _resolved_base_domain()

                    # If a base domain is configured, only treat hosts that end
                    # with it as candidate tenant subdomains. Otherwise fall back
                    # to the legacy behaviour of taking the first dotted label.
                    is_subdomain_candidate = (
                        bool(first_label)
                        and first_label not in reserved
                        and (base_domain is None or host_header.endswith("." + base_domain))
                    )

                    if is_subdomain_candidate:
                        tenant = repo.get_tenant_by_code(first_label)

                # 3e. JWT login context fallback.
                if tenant is None:
                    tenant_id = _extract_tenant_id_from_jwt(request)
                    if tenant_id is not None:
                        tenant = repo.get_tenant_by_id(tenant_id)

                # 3f. Allow main-site / public access when nothing matches AND
                # the request is reaching the canonical public host. Other
                # unmatched hosts must fail loudly.
                if tenant is None:
                    first_label = host_header.split(".")[0] if host_header else ""
                    if first_label in _resolved_reserved_labels() and not tenant_code_hdr:
                        return await call_next(request)

                    identifier = tenant_code_hdr or tenant_domain_hdr or host_header or "unknown"
                    return JSONResponse(
                        status_code=404,
                        content={
                            "success": False,
                            "detail": f"Tenant '{identifier}' not found.",
                            "tenant_resolution": {
                                "host": host_header,
                                "tenant_code_header": tenant_code_hdr,
                                "tenant_domain_header": tenant_domain_hdr,
                            },
                        },
                    )

                # 4. Subscription / lifecycle gate.
                sub = tenant.active_subscription
                if sub is None:
                    # Trialing tenants should still be allowed if the trial window
                    # has not closed; that decision is made by SubscriptionStatus.
                    trialing = any(
                        s.status == SubscriptionStatus.TRIALING and s.is_active
                        for s in (tenant.subscriptions or [])
                    )
                    if not trialing:
                        return JSONResponse(
                            status_code=403,
                            content={
                                "success": False,
                                "detail": "Tenant subscription is inactive, suspended, or missing.",
                                "tenant_code": tenant.code,
                            },
                        )

                # 5. Bind tenant to the request context.
                set_current_tenant(tenant)

        except OperationalError as exc:
            err_msg = str(exc.orig) if hasattr(exc, "orig") and exc.orig else str(exc)
            logger.error("Database connection failure during tenant resolution: %s", err_msg)

            if "too many clients" in err_msg.lower():
                return JSONResponse(
                    status_code=503,
                    content={
                        "success": False,
                        "message": "The server is currently experiencing high demand. Please try again in a few moments.",
                        "error_code": "DATABASE_CONNECTION_LIMIT",
                        "detail": {
                            "reason": "The database connection pool has been exhausted.",
                            "action": "Please retry your request shortly. If this persists, contact your system administrator.",
                        },
                    },
                )

            # Other OperationalErrors (connection refused, SSL reset, etc.)
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "message": "The service is temporarily unavailable. Please try again shortly.",
                    "error_code": "DATABASE_UNAVAILABLE",
                    "detail": {
                        "action": "If this persists, contact your system administrator.",
                    },
                },
            )

        return await call_next(request)
