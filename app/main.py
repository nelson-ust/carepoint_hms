from __future__ import annotations

"""
app.main

Main FastAPI application entrypoint for the Carepoint Hospital Management System.

Purpose
-------
This module bootstraps the FastAPI application and wires together:

1. Application metadata (title, version, description).
2. Lifespan startup and shutdown logic.
3. Optional database table creation (controlled by ``AUTO_CREATE_TABLES``).
4. Optional scheduler integration (controlled by ``ENABLE_SCHEDULER``;
   gracefully falls back when the ``app.scheduler`` module is absent).
5. Middleware stack: CORS → rate limiting → auth context → audit.
6. Static-file mounting for the uploads directory (when configured).
7. v1 API router registration (auth, RBAC, patient registration, visits,
   queues, clinical, lab, pharmacy, inpatient admission/discharge,
   billing/invoice/payment, and any future modules registered via
   ``app/api/v1/api.py``).
8. Health, readiness and root endpoints used by load-balancers and on-call dashboards.
9. Custom OpenAPI security configuration with a normalized ``BearerAuth``
   scheme.
10. Custom Swagger UI that auto-captures the ``access_token`` returned by
    the public auth endpoints and applies it to subsequent secured calls.

Design notes
------------
- Database table creation is helpful in early development; production
  deployments should rely on Alembic migrations and disable
  ``AUTO_CREATE_TABLES``.
- Scheduler startup/shutdown is non-fatal: if the scheduler can't import
  or fails to start, the API still serves traffic — the failure surfaces in
  ``/health`` so operators can see it.
- The Swagger UI persists the bearer token in browser ``localStorage`` and
  injects ``Authorization: Bearer <token>`` into subsequent secured
  requests. Public auth endpoints (login, refresh, OTP, 2FA verify, etc.)
  are explicitly skipped in the interceptor.
"""

import os
import asyncio
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_oauth2_redirect_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import (
    check_database_connection,
    create_tables,
)
from app.core.exceptions import register_exception_handlers
from app.core.logger import get_logger
from app.middleware.audit_middleware import AuditMiddleware
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.rate_limit_middleware import RateLimitMiddleware
from app.middleware.security_headers_middleware import SecurityHeadersMiddleware
from app.middleware.tenant_middleware import TenantMiddleware

logger = get_logger(__name__)


# =============================================================================
# Optional scheduler integration
# =============================================================================
#
# We attempt to import the project's scheduler at module-load time. When the
# ``app.scheduler`` module is missing or fails to import, the API still runs
# without scheduled jobs (bed-day rollover, notification dispatch, report
# refresh, etc.). The failure is recorded so it surfaces in ``/health`` and
# operators can investigate without the API itself going down.

start_scheduler = None
shutdown_scheduler = None
SCHEDULER_IMPORT_ERROR: str | None = None

try:
    # Project-specific scheduler bootstrap. Expected to expose:
    #   start_scheduler()   -> None  (idempotent start)
    #   shutdown_scheduler() -> None (graceful stop)
    from app.scheduler import (  # type: ignore[import-not-found]
        shutdown_scheduler,
        start_scheduler,
    )
except Exception as exc:  # pragma: no cover - tested via integration smoke
    SCHEDULER_IMPORT_ERROR = str(exc)
    start_scheduler = None
    shutdown_scheduler = None
    logger.warning(
        "Scheduler module could not be imported from app.scheduler. "
        "The API will continue without scheduler support. error=%s",
        exc,
    )


# =============================================================================
# Environment-driven runtime settings
# =============================================================================
#
# We use ``getattr`` with sensible defaults so the application starts cleanly
# even when ``Settings`` does not yet declare a particular knob. This keeps
# main.py forward-compatible with future config additions.

API_PREFIX = getattr(settings, "API_V1_PREFIX", "/api/v1")
APP_TIMEZONE = getattr(settings, "DEFAULT_TIMEZONE", "Africa/Lagos")
import re

_raw_origins = getattr(settings, "normalized_cors_origins", None) or getattr(
    settings, "BACKEND_CORS_ORIGINS", ["*"]
) or ["*"]

ALLOW_ORIGINS = []
_cors_regex_patterns = []

for origin in _raw_origins:
    if "*" in origin and origin != "*":
        regex_str = "^" + origin.replace(".", r"\.").replace("*", ".*") + "$"
        _cors_regex_patterns.append(regex_str)
    else:
        ALLOW_ORIGINS.append(origin)

ALLOW_ORIGIN_REGEX = "|".join(_cors_regex_patterns) if _cors_regex_patterns else None

if not ALLOW_ORIGINS and not ALLOW_ORIGIN_REGEX:
    ALLOW_ORIGINS = ["*"]

APP_NAME = getattr(settings, "APP_NAME", "Carepoint HMS")
APP_VERSION = getattr(settings, "APP_VERSION", "1.0.0")
APP_ENV = getattr(settings, "APP_ENV", None) or getattr(settings, "ENVIRONMENT", "development")
APP_DEBUG = bool(getattr(settings, "APP_DEBUG", None) or getattr(settings, "DEBUG", False))

# Host / port / reload can be overridden with plain environment variables
# (UVICORN_HOST, UVICORN_PORT, UVICORN_RELOAD) so they work even when they are
# not declared as fields on the Settings model. This makes
# ``UVICORN_RELOAD=true python -m app.main`` enable autoreload in development.
def _env_flag(name: str):
    """Return True/False from an env var, or None when the var is unset."""
    raw = os.getenv(name)
    if raw is None:
        return None
    return raw.strip().lower() in {"1", "true", "yes", "on"}


UVICORN_HOST = (
    os.getenv("UVICORN_HOST")
    or getattr(settings, "UVICORN_HOST", None)
    or getattr(settings, "HOST", "127.0.0.1")
)
UVICORN_PORT = int(
    os.getenv("UVICORN_PORT")
    or getattr(settings, "UVICORN_PORT", None)
    or getattr(settings, "PORT", 8000)
)
_reload_override = _env_flag("UVICORN_RELOAD")
UVICORN_RELOAD = (
    _reload_override
    if _reload_override is not None
    else bool(getattr(settings, "UVICORN_RELOAD", False))
)

# Database / static toggles.
AUTO_CREATE_TABLES = bool(getattr(settings, "AUTO_CREATE_TABLES", True))
UPLOADS_DIR = getattr(settings, "UPLOADS_DIR", None)

# Schema sync at startup. Defaults ON outside of production so that adding
# a new model column doesn't require an out-of-band migration step before
# the API can boot. Production deployments should set this to False and
# run ``python -m app.init_db --sync-master`` / ``--sync-tenants`` (or a
# proper Alembic migration) as part of the deploy pipeline.
_default_auto_sync = str(getattr(settings, "ENVIRONMENT", "development")).lower() != "production"
AUTO_SYNC_SCHEMAS_ON_STARTUP = bool(
    getattr(settings, "AUTO_SYNC_SCHEMAS_ON_STARTUP", _default_auto_sync)
)
AUTO_SYNC_TENANT_SCHEMAS = bool(
    getattr(settings, "AUTO_SYNC_TENANT_SCHEMAS", AUTO_SYNC_SCHEMAS_ON_STARTUP)
)

# Middleware toggles.
RATE_LIMIT_ENABLED = bool(getattr(settings, "RATE_LIMIT_ENABLED", True))
RATE_LIMIT_MAX_REQUESTS = int(getattr(settings, "RATE_LIMIT_MAX_REQUESTS", 100))
RATE_LIMIT_WINDOW_SECONDS = int(getattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60))
ENABLE_AUDIT_MIDDLEWARE = bool(getattr(settings, "ENABLE_AUDIT_MIDDLEWARE", True))
ENABLE_AUTH_MIDDLEWARE = bool(getattr(settings, "ENABLE_AUTH_MIDDLEWARE", True))

# Security headers / HTTPS enforcement.
# Default ENFORCE_HTTPS to ON for production-like environments and OFF
# locally. Default CSP is intentionally Swagger-UI-friendly; the docs
# paths are also CSP-exempt so the developer UI keeps rendering even
# when operators tighten the CSP further.
_default_enforce_https = str(APP_ENV).lower() in {"production", "staging"}
ENFORCE_HTTPS = bool(getattr(settings, "ENFORCE_HTTPS", _default_enforce_https))
HSTS_MAX_AGE = int(getattr(settings, "HSTS_MAX_AGE", 60 * 60 * 24 * 365))
HSTS_INCLUDE_SUBDOMAINS = bool(getattr(settings, "HSTS_INCLUDE_SUBDOMAINS", True))
HSTS_PRELOAD = bool(getattr(settings, "HSTS_PRELOAD", False))

# When unset, fall back to the Swagger-friendly default shipped in the
# middleware (DEFAULT_CSP). Set ``CONTENT_SECURITY_POLICY=""`` in your
# environment to disable CSP entirely.
CONTENT_SECURITY_POLICY = getattr(settings, "CONTENT_SECURITY_POLICY", None)

# Scheduler is opt-in; defaults to False so deployments that don't have a
# scheduler module configured don't try to start one.
SCHEDULER_ENABLED = bool(getattr(settings, "ENABLE_SCHEDULER", False))


# =============================================================================
# Public auth endpoint paths
# =============================================================================
#
# These routes are intentionally exposed without bearer-token requirements in
# the OpenAPI schema and are also bypassed by the Swagger token interceptor
# so callers can complete the OTP / 2FA / password-reset flows without first
# possessing a bearer token.

_PUBLIC_AUTH_PATHS: set[str] = {
    f"{API_PREFIX}/auth/login",
    f"{API_PREFIX}/auth/refresh",
    f"{API_PREFIX}/auth/forgot-password",
    f"{API_PREFIX}/auth/reset-password",
    f"{API_PREFIX}/auth/otp/verify",
    f"{API_PREFIX}/auth/otp/resend",
    f"{API_PREFIX}/auth/two-factor/verify",
    f"{API_PREFIX}/auth/email-verification/request",
    f"{API_PREFIX}/auth/email-verification/confirm",
    f"{API_PREFIX}/auth/phone-verification/request",
    f"{API_PREFIX}/auth/phone-verification/confirm",
    f"{API_PREFIX}/saas/plans",
    f"{API_PREFIX}/tenants/register",
}


# =============================================================================
# Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Startup tasks
    -------------
    1. Optionally create database tables (``AUTO_CREATE_TABLES``).
    2. Record database connectivity state in ``app.state``.
    3. Optionally start the scheduler (``ENABLE_SCHEDULER``).
    4. Mark startup as completed so ``/ready`` flips to ready.

    Shutdown tasks
    --------------
    1. Optionally stop the scheduler.
    2. Record clean shutdown in logs.

    Notes
    -----
    - Database connectivity failures do **not** raise here — operators see
      ``/health`` reporting the database as disconnected and the
      ``/ready`` probe returns ``ready=False``.
    - Scheduler failures are non-fatal; they surface in ``/health`` only.
    """
    logger.info(
        "[lifespan] Starting app lifespan. timezone=%s auto_create_tables=%s "
        "scheduler_enabled=%s",
        APP_TIMEZONE,
        AUTO_CREATE_TABLES,
        SCHEDULER_ENABLED,
    )

    # Initialize state defaults so health/readiness probes don't 500 if
    # something below this point throws before completing.
    app.state.db_connected = False
    app.state.startup_completed = False
    app.state.scheduler_enabled = bool(SCHEDULER_ENABLED and start_scheduler)
    app.state.scheduler_running = False
    app.state.scheduler_import_error = SCHEDULER_IMPORT_ERROR

    # Optionally create tables. In production we expect Alembic to be in
    # charge — disable AUTO_CREATE_TABLES there.
    if AUTO_CREATE_TABLES:
        logger.info("[lifespan] Ensuring master database tables exist.")
        try:
            # We explicitly pass is_master=True here. Tenant tables should
            # NEVER be created automatically in the default (master) database.
            # They are provisioned dynamically during the tenant onboarding flow.
            create_tables(is_master=True)
        except Exception as exc:  # pragma: no cover
            # Don't crash startup; report via /health. This makes it possible
            # to bring up the API and inspect logs even when the DB is bad.
            logger.exception("[lifespan] create_tables failed: %s", exc)

    # Forward-migrate schemas before the scheduler (or any other tick-based
    # work) starts, so a freshly-deployed model that adds new tables doesn't
    # generate UndefinedTable errors against existing databases.
    if AUTO_SYNC_SCHEMAS_ON_STARTUP:
        try:
            from app.db_sync import sync_master_schema

            master_summary = sync_master_schema()
            if master_summary:
                logger.info("[lifespan] Master schema sync applied: %s", master_summary)
            else:
                logger.info("[lifespan] Master schema is already up to date.")
        except Exception as exc:  # pragma: no cover
            logger.exception("[lifespan] sync_master_schema failed: %s", exc)

    if AUTO_SYNC_TENANT_SCHEMAS:
        try:
            from app.db_sync import sync_tenant_schemas_all

            tenant_results = sync_tenant_schemas_all()
            ok = sum(1 for v in tenant_results.values() if isinstance(v, dict))
            failed = sum(
                1 for v in tenant_results.values()
                if isinstance(v, str) and v.startswith("error")
            )
            for code, summary in tenant_results.items():
                if isinstance(summary, dict) and summary:
                    logger.info("[lifespan] Tenant %s schema sync: %s", code, summary)
                elif isinstance(summary, str):
                    logger.warning("[lifespan] Tenant %s sync: %s", code, summary)
            logger.info(
                "[lifespan] Tenant schema sync complete: ok=%s failed=%s total=%s",
                ok, failed, len(tenant_results),
            )
        except Exception as exc:  # pragma: no cover
            logger.exception("[lifespan] sync_tenant_schemas_all failed: %s", exc)

    # Record connectivity once at startup; ``/health`` and ``/ready`` re-check
    # on demand so they always reflect live state.
    app.state.db_connected = check_database_connection()
    logger.info("[lifespan] Database connectivity state: %s", app.state.db_connected)

    # Scheduler startup. Failure is non-fatal — surfaced via /health.
    if SCHEDULER_ENABLED and start_scheduler is not None:
        try:
            start_scheduler()
            app.state.scheduler_running = True
            logger.info("[lifespan] Scheduler started successfully.")
        except Exception as exc:  # pragma: no cover
            app.state.scheduler_running = False
            logger.exception("[lifespan] Failed to start scheduler: %s", exc)
    elif SCHEDULER_ENABLED and start_scheduler is None:
        logger.warning(
            "[lifespan] Scheduler was enabled in configuration but no scheduler "
            "implementation was available."
        )

    app.state.startup_completed = True

    # Start background monitoring probes
    async def monitoring_loop():
        from app.services.monitoring_service import monitoring_service
        while True:
            try:
                await monitoring_service.run_probe()
            except Exception as e:
                logger.error("[monitoring] Probe loop error: %s", e)
            await asyncio.sleep(60)

    probe_task = asyncio.create_task(monitoring_loop())

    try:
        yield
    finally:
        probe_task.cancel()
        # Best-effort scheduler stop. We only attempt this when we successfully
        # started it earlier so we don't trip on a half-initialized state.
        if (
            SCHEDULER_ENABLED
            and shutdown_scheduler is not None
            and app.state.scheduler_running
        ):
            try:
                shutdown_scheduler()
                app.state.scheduler_running = False
                logger.info("[lifespan] Scheduler shut down successfully.")
            except Exception as exc:  # pragma: no cover
                logger.exception("[lifespan] Failed to shut down scheduler: %s", exc)

        logger.info("[lifespan] App shutdown complete.")


# =============================================================================
# App metadata
# =============================================================================
#
# Description is rendered into the OpenAPI document and shown in Swagger /
# ReDoc. We keep it accurate to the modules wired up in app/api/v1/api.py.

from app.api.v1.endpoints import (
    admission_routes,
    ambulance_routes,
    appointment_routes,
    auth_routes,
    bed_routes,
    billing_routes,
    clinician_routes,
    compliance_routes,
    consultation_routes,
    department_routes,
    diagnosis_routes,
    discharge_routes,
    dispense_routes,
    drug_routes,
    insurance_claim_routes,
    inventory_routes,
    invoice_routes,
    lab_order_routes,
    lab_result_routes,
    lab_routes,
    medical_history_routes,
    membership_card_routes,
    notification_routes,
    patient_portal_routes,
    patient_registration_routes,
    patient_routes,
    payment_routes,
    paystack_webhook_routes,
    permission_routes,
    pharmacy_routes,
    prescription_routes,
    procedure_routes,
    queue_routes,
    radiology_routes,
    referral_routes,
    report_routes,
    role_routes,
    service_delivery_point_routes,
    staff_profile_routes,
    staff_routes,
    stock_movement_routes,
    surgical_routes,
    tenant_routes,
    triage_routes,
    two_factor_routes,
    user_routes,
    visit_flow_routes,
    visit_routes,
    vital_sign_routes,
    ward_routes,
)

base_description = (
    "APIs for managing the Carepoint Hospital Management System including "
    "authentication, RBAC, fine-grained permissions, user management, "
    "facility / multi-branch scoping, patient registration, appointments, "
    "visits, queue routing, clinical workflows (triage, vitals, consultation, "
    "diagnosis), laboratory (catalog, orders, results), pharmacy (drug catalog, "
    "prescriptions, dispensing, inventory, stock movements), inpatient "
    "admission with ward/bed assignment and bed-day billing, discharge, "
    "billing/invoice/payment (charge-to-cash), notifications, compliance, "
    "and reporting."
)

auth_flow_description = f"""
Authentication flow
-------------------
This application uses **JWT bearer authentication**.

When 2FA is enabled on a user account, login is a 2-step flow:

1. ``POST {API_PREFIX}/auth/login``
2. If 2FA is required, the response carries ``two_factor_required=true``.
   Call ``POST {API_PREFIX}/auth/two-factor/verify`` (or
   ``POST {API_PREFIX}/auth/otp/verify``) to obtain final tokens.
3. The custom Swagger UI captures the ``access_token`` automatically.
4. Secured endpoints are then called with:

   `Authorization: Bearer <access_token>`

Public auth endpoints (no bearer required):
- ``POST {API_PREFIX}/auth/login``
- ``POST {API_PREFIX}/auth/refresh``
- ``POST {API_PREFIX}/auth/forgot-password``
- ``POST {API_PREFIX}/auth/reset-password``
- ``POST {API_PREFIX}/auth/otp/verify``
- ``POST {API_PREFIX}/auth/otp/resend``
- ``POST {API_PREFIX}/auth/two-factor/verify``
- ``POST {API_PREFIX}/auth/email-verification/request``
- ``POST {API_PREFIX}/auth/email-verification/confirm``
- ``POST {API_PREFIX}/auth/phone-verification/request``
- ``POST {API_PREFIX}/auth/phone-verification/confirm``
""".strip()

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=f"{base_description}\n\n{auth_flow_description}",
    debug=APP_DEBUG,
    lifespan=lifespan,
    # We replace docs_url with a custom Swagger UI further down so we can
    # auto-capture access tokens from public auth responses.
    docs_url=None,
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# =============================================================================
# Exception handlers
# =============================================================================

# Wires AppException + generic-exception handlers so consistent JSON error
# bodies flow back to clients. See app/core/exceptions.py.
register_exception_handlers(app)


# =============================================================================
# Static files
# =============================================================================

# Mount the uploads directory. We resolve (and create) a stable base dir —
# settings.UPLOADS_DIR, or <cwd>/uploads by default — so publicly served
# assets like tenant branding logos and card-funding proofs are always
# reachable at '/uploads/...', even when UPLOADS_DIR isn't explicitly set.
try:
    from app.utils.storage import uploads_base_dir

    _uploads_dir = uploads_base_dir()
    app.mount("/uploads", StaticFiles(directory=_uploads_dir), name="uploads")
    logger.info("Mounted uploads directory at '/uploads' from '%s'.", _uploads_dir)
except Exception as exc:  # never block startup on a static mount
    logger.warning("Could not mount uploads directory at '/uploads': %s", exc)


# =============================================================================
# Middleware
# =============================================================================
#
# Order matters because Starlette runs middlewares in reverse-add order on
# requests and in registration order on responses. We add CORS first so the
# browser preflight pass-through works for everything that follows.

# A wide-open "*" CORS origin combined with allow_credentials=True is
# unsafe; refuse it in production-like environments.
_CORS_ALLOW_CREDENTIALS = True
if APP_ENV.lower() in {"production", "staging"} and (
    ALLOW_ORIGINS == ["*"] or "*" in ALLOW_ORIGINS
):
    logger.warning(
        "CORS configured as '*' in %s; disabling allow_credentials and "
        "request explicit origins via BACKEND_CORS_ORIGINS.",
        APP_ENV,
    )
    _CORS_ALLOW_CREDENTIALS = False

# In non-production environments, also allow any private-LAN origin so the app
# can be opened from another device on the same network via the host's LAN IP
# (e.g. http://192.168.x.x:3000) without enumerating every address in
# BACKEND_CORS_ORIGINS. Intentionally disabled in production/staging, where
# origins must be listed explicitly.
if APP_ENV.lower() not in {"production", "staging"}:
    _LAN_ORIGIN_REGEX = (
        r"^https?://("
        r"localhost|127\.0\.0\.1|\[::1\]|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
        r")(?::\d+)?$"
    )
    ALLOW_ORIGIN_REGEX = (
        f"{ALLOW_ORIGIN_REGEX}|{_LAN_ORIGIN_REGEX}"
        if ALLOW_ORIGIN_REGEX
        else _LAN_ORIGIN_REGEX
    )
    logger.info(
        "Development CORS: private-LAN origins are allowed via regex (%s).",
        APP_ENV,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_origin_regex=ALLOW_ORIGIN_REGEX,
    allow_credentials=_CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Tenant",
        "X-Tenant-Code",
        "X-Tenant-Domain",
        "X-Request-ID",
        "Accept",
        "Origin",
    ],
    expose_headers=["X-Request-ID", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    max_age=600,
)

# HTTPS enforcement + security headers. CSP is Swagger-UI-friendly by
# default, and the docs paths (/docs, /redoc, /openapi.json) are CSP-exempt
# so the developer UI keeps rendering correctly even when operators
# tighten the global CSP.
_security_headers_kwargs: dict[str, Any] = dict(
    enforce_https=ENFORCE_HTTPS,
    hsts_max_age=HSTS_MAX_AGE,
    include_subdomains=HSTS_INCLUDE_SUBDOMAINS,
    preload=HSTS_PRELOAD,
)
if CONTENT_SECURITY_POLICY is not None:
    # Empty string disables CSP entirely; non-empty string overrides the
    # built-in default. Leaving the setting unset uses the middleware's
    # Swagger-friendly default.
    _security_headers_kwargs["csp"] = CONTENT_SECURITY_POLICY or None

app.add_middleware(SecurityHeadersMiddleware, **_security_headers_kwargs)

# Optional rate-limiting. The implementation lives in
# app/middleware/rate_limit_middleware.py and works in-memory by default.
if RATE_LIMIT_ENABLED:
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=RATE_LIMIT_MAX_REQUESTS,
        window_seconds=RATE_LIMIT_WINDOW_SECONDS,
    )

# Audit middleware persists a lightweight AuditLog for mutating requests.
# It is added early so it is INNER to AuthMiddleware.
if ENABLE_AUDIT_MIDDLEWARE:
    app.add_middleware(
        AuditMiddleware,
        audit_mutating_methods_only=True,
        persist_audit_log=True,
    )

# Auth-context middleware attaches the current user (if any) to
# request.state. Route-level authorization continues to run via the
# permission/role dependencies.
if ENABLE_AUTH_MIDDLEWARE:
    app.add_middleware(
        AuthMiddleware,
        attach_user_context=True,
        ignore_invalid_token=True,
    )

# Tenant resolution middleware must be added last so it is the first to run on request
app.add_middleware(TenantMiddleware)


# =============================================================================
# Root / health endpoints
# =============================================================================

@app.get("/", tags=["Root"])
async def read_root() -> dict[str, Any]:
    """
    Lightweight root endpoint for quick application identification.

    Useful as a smoke check without exercising the database.
    """
    return {
        "message": f"Welcome to {APP_NAME}!",
        "app_name": app.title,
        "version": app.version,
        "environment": APP_ENV,
        "timezone": APP_TIMEZONE,
        "api_prefix": API_PREFIX,
        # Reports the *configured* state so a single GET / answers
        # "is scheduler turned on for this process?".
        "scheduler_enabled_in_this_process": bool(getattr(app.state, "scheduler_enabled", False)),
    }


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    """
    General health endpoint enhanced with real-time network connectivity metrics.

    Returns a broad application health snapshot including database state,
    scheduler runtime state, and live network performance metrics from
    the MonitoringService.
    """
    from app.services.monitoring_service import monitoring_service
    
    db_connected = check_database_connection()
    network_metrics = monitoring_service.get_metrics()

    return {
        "status": "ok" if db_connected else "degraded",
        "application": APP_NAME,
        "version": APP_VERSION,
        "environment": APP_ENV,
        "startup_completed": bool(getattr(app.state, "startup_completed", False)),
        "database": {
            "connected": db_connected,
        },
        "scheduler": {
            "configured_enabled": SCHEDULER_ENABLED,
            "available": start_scheduler is not None,
            "running": bool(getattr(app.state, "scheduler_running", False)),
            "import_error": getattr(app.state, "scheduler_import_error", None),
        },
        "network": network_metrics
    }


@app.get("/health/db", tags=["Health"])
async def database_health_check() -> dict[str, Any]:
    """Database-specific health endpoint."""
    return {
        "connected": check_database_connection(),
    }


@app.get("/ready", tags=["Health"])
async def readiness_check() -> dict[str, Any]:
    """
    Readiness endpoint.

    Indicates whether the application is ready to receive traffic. Differs
    from ``/health`` in that it returns False until startup tasks have
    completed AND the database is reachable.
    """
    db_ok = check_database_connection()
    ready = bool(getattr(app.state, "startup_completed", False)) and db_ok

    return {
        "ready": ready,
        "startup_completed": bool(getattr(app.state, "startup_completed", False)),
        "database_connected": db_ok,
    }


# =============================================================================
# Router registration
# =============================================================================
#
# The aggregator in app/api/v1/api.py is responsible for ordering and
# documenting individual routers. We mount the whole bundle under the
# configured ``API_V1_PREFIX``.

app.include_router(api_router, prefix=API_PREFIX)


# =============================================================================
# OpenAPI customization
# =============================================================================

def _replace_operation_security_scheme(
    schema: dict[str, Any],
    old_name: str,
    new_name: str,
) -> None:
    """
    Replace an autogenerated security-scheme name across all operations.

    FastAPI emits ``OAuth2PasswordBearer`` (or similar) names by default;
    we normalize them to a single ``BearerAuth`` scheme so the Swagger UI
    presents a consistent experience to API consumers.
    """
    paths = schema.get("paths", {})
    if not isinstance(paths, dict):
        return

    valid_http_methods = {
        "get", "post", "put", "patch", "delete", "options", "head", "trace",
    }

    # Iterate every path -> method -> operation triple and rewrite the
    # security entry name when present.
    for _, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        for method_name, operation in path_item.items():
            if method_name.lower() not in valid_http_methods:
                continue
            if not isinstance(operation, dict):
                continue

            security = operation.get("security")
            if not isinstance(security, list):
                continue

            updated_security = []
            for requirement in security:
                if not isinstance(requirement, dict):
                    updated_security.append(requirement)
                    continue

                new_requirement = dict(requirement)
                if old_name in new_requirement:
                    scopes = new_requirement.pop(old_name, [])
                    new_requirement[new_name] = scopes if isinstance(scopes, list) else []
                updated_security.append(new_requirement)

            operation["security"] = updated_security


def _patch_public_auth_operations(schema: dict[str, Any]) -> None:
    """
    Mark public auth endpoints as not requiring bearer auth in OpenAPI.

    This is forward-compatible — paths that don't yet exist are silently
    skipped, so the same code works during early bootstrap and steady state.
    """
    valid_http_methods = {
        "get", "post", "put", "patch", "delete", "options", "head", "trace",
    }

    for path in _PUBLIC_AUTH_PATHS:
        path_item = schema.get("paths", {}).get(path)
        if not isinstance(path_item, dict):
            continue

        for method_name, operation in path_item.items():
            if method_name.lower() in valid_http_methods and isinstance(operation, dict):
                # Empty list = no security requirement.
                operation["security"] = []


def custom_openapi() -> dict[str, Any]:
    """
    Build and cache a customized OpenAPI schema.

    Customizations
    --------------
    - Replace autogenerated OAuth2 security-scheme names with ``BearerAuth``.
    - Apply global bearer auth across the document.
    - Mark public auth endpoints as security-free.
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=APP_NAME,
        version=APP_VERSION,
        description=f"{base_description}\n\n{auth_flow_description}",
        routes=app.routes,
    )

    components = openapi_schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})

    # Drop any FastAPI-emitted scheme names so only our normalized one shows.
    security_schemes.pop("OAuth2PasswordBearer", None)
    security_schemes.pop("oauth2", None)

    security_schemes["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": (
            "JWT bearer authentication for secured endpoints. The custom Swagger UI "
            "captures the ``access_token`` returned by the public auth endpoints "
            "and applies it to subsequent requests automatically."
        ),
    }

    # Bearer auth is the default expectation across the API; individual
    # public endpoints are stripped back to ``security: []`` below.
    openapi_schema["security"] = [{"BearerAuth": []}]

    _replace_operation_security_scheme(openapi_schema, "OAuth2PasswordBearer", "BearerAuth")
    _replace_operation_security_scheme(openapi_schema, "oauth2", "BearerAuth")
    _patch_public_auth_operations(openapi_schema)

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# =============================================================================
# Custom Swagger UI
# =============================================================================
#
# We replace the stock /docs page with one that:
# - persists the bearer token in browser localStorage
# - intercepts public auth responses (login, OTP verify, 2FA verify, refresh)
#   and pulls the access_token out automatically
# - skips public auth URLs in the request interceptor so the OTP/2FA flow can
#   be completed before any token is held
# - re-applies a stored token on page reload

# Build the JS list of public auth URLs from the Python-side set so the two
# stay in sync as endpoints are added/removed.
_PUBLIC_AUTH_PATH_SUFFIXES = sorted(_PUBLIC_AUTH_PATHS)


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html() -> HTMLResponse:
    """
    Custom Swagger UI page.

    Behavior
    --------
    - captures ``access_token`` from the auth response bodies
    - stores it in browser localStorage
    - automatically injects ``Authorization: Bearer <token>`` into subsequent
      secured requests
    - skips public auth URLs in the request interceptor so OTP/2FA flows
      don't accidentally send a bearer token
    """
    openapi_url = app.openapi_url
    title = f"{app.title} - Swagger UI"

    # Render the public-auth-paths set as a JS array literal. Each entry is
    # tested with String.includes() inside the interceptor, so partial
    # matches are intentional.
    public_paths_js_literal = (
        "[" + ", ".join(f'"{p}"' for p in _PUBLIC_AUTH_PATH_SUFFIXES) + "]"
    )

    swagger_html = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>{title}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <div style="position: fixed; bottom: 20px; right: 20px; z-index: 9999; background: #fff; padding: 10px; border-radius: 8px; border: 1px solid #ddd; box-shadow: 0 4px 6px rgba(0,0,0,0.1); font-family: sans-serif;">
    <label for="tenant-code-input" style="display: block; font-size: 12px; font-weight: bold; margin-bottom: 4px; color: #3b4151;">Active Tenant Code</label>
    <input type="text" id="tenant-code-input" placeholder="e.g. ACME" style="padding: 6px 8px; border: 1px solid #d9d9d9; border-radius: 4px; width: 150px; font-size: 13px;" />
  </div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
  <script>
    // localStorage keys.
    const TOKEN_STORAGE_KEY = "carepoint_hms_swagger_access_token_v1";
    const TENANT_STORAGE_KEY = "carepoint_hms_swagger_tenant_code_v1";

    // Public auth path suffixes computed from the Python-side set above.
    // Used to skip the auth-injection request interceptor.
    const PUBLIC_AUTH_PATHS = {public_paths_js_literal};

    const tenantInput = document.getElementById("tenant-code-input");
    
    function saveToken(token) {
      // Trim defensively: APIs sometimes return whitespace-padded tokens.
      if (typeof token === "string" && token.trim()) {
        window.localStorage.setItem(TOKEN_STORAGE_KEY, token.trim());
      }
    }

    function loadToken() {
      return window.localStorage.getItem(TOKEN_STORAGE_KEY);
    }

    function saveTenantCode(code) {
      if (typeof code === "string") {
        window.localStorage.setItem(TENANT_STORAGE_KEY, code.trim().toUpperCase());
      }
    }

    function loadTenantCode() {
      return window.localStorage.getItem(TENANT_STORAGE_KEY);
    }

    // Initialize tenant input from storage
    tenantInput.value = loadTenantCode() || "";
    tenantInput.addEventListener("input", (e) => saveTenantCode(e.target.value));

    function applySwaggerAuthorization(ui, token) {
      if (!ui || !token) return;
      try {
        // Apply the captured token to the BearerAuth scheme so the lock icons
        // in the UI flip to authorized.
        ui.authActions.authorize({ BearerAuth: { value: token } });
      } catch (err) {
        console.warn("Swagger authorize warning:", err);
      }
    }

    function isPublicAuthUrl(url) {
      // String.includes is tolerant of differing host/origin prefixes.
      if (!url) return false;
      for (const path of PUBLIC_AUTH_PATHS) {
        if (url.includes(path)) return true;
      }
      return false;
    }

    function extractAccessToken(parsed) {
      // Auth responses live at one of two shapes:
      //   1) { access_token: "..." }                    (refresh)
      //   2) { tokens: { access_token: "..." }, ... } (login / 2FA verify)
      if (!parsed || typeof parsed !== "object") return null;
      if (typeof parsed.access_token === "string" && parsed.access_token.trim()) {
        return parsed.access_token.trim();
      }
      if (parsed.tokens && typeof parsed.tokens.access_token === "string") {
        const candidate = parsed.tokens.access_token.trim();
        if (candidate) return candidate;
      }
      return null;
    }

    const ui = SwaggerUIBundle({
      url: "{openapi_url}",
      dom_id: "#swagger-ui",
      deepLinking: true,
      // We persist the token ourselves so we can scope it to the same key
      // used by the rest of the app.
      persistAuthorization: false,
      presets: [
        SwaggerUIBundle.presets.apis,
        SwaggerUIStandalonePreset
      ],
      layout: "BaseLayout",

      requestInterceptor: (req) => {
        const token = loadToken();
        const tenantCode = loadTenantCode();
        
        req.headers = req.headers || {};
        
        // Inject Tenant Code if set
        if (tenantCode) {
          req.headers["X-Tenant-Code"] = tenantCode;
        }

        // ``loadSpec`` is true when SwaggerUI is fetching the OpenAPI doc
        // itself; never inject a bearer token into that request.
        if (token && !req.loadSpec && !isPublicAuthUrl(req.url)) {
          req.headers["Authorization"] = `Bearer ${token}`;
        }
        return req;
      },

      responseInterceptor: (res) => {
        // Auto-capture token from successful public-auth responses so the
        // analyst doesn't have to copy/paste it into the Authorize dialog.
        try {
          if (
            res &&
            typeof res.url === "string" &&
            isPublicAuthUrl(res.url) &&
            res.status === 200
          ) {
            let parsed = null;
            if (typeof res.body === "string") {
              try { parsed = JSON.parse(res.body); } catch (e) { parsed = null; }
            } else if (res.body && typeof res.body === "object") {
              parsed = res.body;
            }

            const token = extractAccessToken(parsed);
            if (token) {
              saveToken(token);
              // Defer slightly so the SwaggerUI auth-store has time to
              // hydrate before we call authorize().
              setTimeout(() => applySwaggerAuthorization(ui, token), 0);
            }
          }
        } catch (err) {
          console.warn("Token capture failed:", err);
        }
        return res;
      },
    });

    // Re-apply any previously stored token on page reload so the analyst
    // can keep working across browser sessions.
    const existingToken = loadToken();
    if (existingToken) {
      setTimeout(() => applySwaggerAuthorization(ui, existingToken), 300);
    }

    // Expose a manual-save hook in case external tooling wants to push a
    // token (e.g. a developer console snippet).
    window.saveSwaggerBearerToken = saveToken;
  </script>
</body>
</html>
""".replace("{title}", title).replace("{public_paths_js_literal}", public_paths_js_literal).replace("{openapi_url}", openapi_url)
    return HTMLResponse(swagger_html)


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect() -> HTMLResponse:
    """Swagger OAuth2 redirect helper endpoint."""
    return get_swagger_ui_oauth2_redirect_html()


# =============================================================================
# Uvicorn entrypoint
# =============================================================================

if __name__ == "__main__":
    # Allow ``python -m app.main`` style invocation. In production we expect
    # an external process supervisor (uvicorn / gunicorn / systemd / k8s) to
    # run the app, so reload defaults to False.
    logger.info(
        "Starting Uvicorn server on %s:%s (reload=%s)",
        UVICORN_HOST,
        UVICORN_PORT,
        UVICORN_RELOAD,
    )
    uvicorn.run(
        "app.main:app",
        host=UVICORN_HOST,
        port=UVICORN_PORT,
        reload=UVICORN_RELOAD,
    )



'''
curl -X 'POST' \
  'http://0.0.0.0:8005/api/v1/auth/login' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-Code: stnicholas' \
  -d '{
  "identifier": "nelson.attah@live.com",
  "password": "S3cure!Password2026",
  "remember_me": false
}'
'''
