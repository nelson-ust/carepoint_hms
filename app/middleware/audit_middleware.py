# carepoint_hms/app/middleware/audit_middleware.py
from __future__ import annotations

"""
Audit middleware for Carepoint HMS.

Purpose
-------
This middleware attaches request metadata to `request.state` and optionally
persists an audit log for mutating requests after a response is generated.

What it does
------------
- generates or reuses a request ID
- captures request path, method, client IP, and user agent
- stores audit context on `request.state`
- optionally writes a lightweight AuditLog record for create/update/delete-like actions
- adds the request ID to the response headers

Notes
-----
- This middleware is intentionally conservative. It only attempts to persist
  audit records for mutating methods by default.
- It does not try to serialize request bodies automatically, because uploaded
  files and large payloads may not be safe or practical to log.
- Repository/service code can still create richer audit entries using
  `utils.audit_util.build_audit_payload(...)`.
"""

from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logger import get_logger
from fastapi.responses import Response
from app.models.all_models import AuditLog, SaaSAdmin
from app.core.multitenancy import get_current_tenant, get_current_tenant_id
from app.services.tenant_usage_service import TenantUsageService
from app.utils.helpers import generate_uuid_str

logger = get_logger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware that prepares per-request audit context and optionally persists
    simple audit log records for mutating requests.
    """

    def __init__(
        self,
        app,
        *,
        audit_mutating_methods_only: bool = True,
        persist_audit_log: bool = True,
    ) -> None:
        super().__init__(app)
        self.audit_mutating_methods_only = audit_mutating_methods_only
        self.persist_audit_log = persist_audit_log
        self.mutating_methods = {"POST", "PUT", "PATCH", "DELETE"}
        self.method_action = {"POST": "CREATE", "PUT": "UPDATE", "PATCH": "UPDATE", "DELETE": "DELETE"}
        # Login/logout/refresh are logged explicitly by the auth services with
        # the resolved actor, so the middleware skips them to avoid duplicates.
        self.excluded_prefixes = (
            "/api/v1/auth/login",
            "/api/v1/auth/logout",
            "/api/v1/auth/refresh",
            "/api/v1/saas/auth/login",
            "/api/v1/saas/auth/logout",
            "/api/v1/health",
            "/api/v1/ready",
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process the request, attach audit context, and optionally persist a log.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware or route handler.

        Returns:
            Response: Outgoing HTTP response.
        """
        # Reuse an upstream request ID if present, otherwise generate one.
        request_id = request.headers.get("X-Request-ID") or generate_uuid_str()

        # Resolve client metadata safely.
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")

        # Store shared request context for later use by routes/services.
        request.state.request_id = request_id
        request.state.client_ip = client_ip
        request.state.user_agent = user_agent
        request.state.audit_context = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_ip": client_ip,
            "user_agent": user_agent,
        }

        # Run downstream handlers.
        response = await call_next(request)

        # Always expose request ID to the client for traceability.
        response.headers["X-Request-ID"] = request_id

        # Persist a lightweight audit record where appropriate.
        if self._should_audit(request):
            try:
                self._persist_audit_log(
                    request=request,
                    response=response,
                    request_id=request_id,
                    client_ip=client_ip,
                    user_agent=user_agent,
                )
            except Exception as exc:  # pragma: no cover
                logger.exception(
                    "Audit persistence failed.",
                    extra={"request_id": request_id},
                )

        # Track API usage for the tenant
        tenant_id = get_current_tenant_id()
        if tenant_id:
            try:
                TenantUsageService.increment_api_usage(tenant_id)
            except Exception as exc:
                logger.warning(f"Failed to increment API usage for tenant {tenant_id}: {exc}")

        return response

    def _should_audit(self, request: Request) -> bool:
        """
        Decide whether the request should produce an audit record.

        Mutating requests are audited for BOTH tenant and SaaS/master
        operations. Tenant context is no longer required — when absent the
        entry is written to the master SaaSAuditLog instead.
        """
        if not self.persist_audit_log:
            return False

        path = request.url.path
        if any(path.startswith(p) for p in self.excluded_prefixes):
            return False

        if self.audit_mutating_methods_only:
            return request.method.upper() in self.mutating_methods

        return True

    def _get_client_ip(self, request: Request) -> str:
        """
        Resolve the best-effort client IP address.
        """
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # X-Forwarded-For may contain a chain of IPs; use the first one.
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

        if request.client and request.client.host:
            return request.client.host

        return "unknown"

    def _actor_context(self, request: Request) -> dict:
        """
        Resolve the acting principal from request.state (set by AuthMiddleware).

        Returns a dict with: id, label, type, is_saas, tenant_id, tenant_code.
        """
        current_user = getattr(request.state, "current_user", None)
        payload = getattr(request.state, "token_payload", None) or {}

        actor_id: Optional[int] = None
        label: Optional[str] = None
        is_saas = bool(payload.get("is_saas_admin")) or isinstance(current_user, SaaSAdmin)

        if current_user is not None:
            raw_id = getattr(current_user, "id", None)
            try:
                actor_id = int(raw_id) if raw_id is not None else None
            except (TypeError, ValueError):
                actor_id = None
            label = (
                getattr(current_user, "email", None)
                or getattr(current_user, "username", None)
                or (f"#{actor_id}" if actor_id else None)
            )

        return {
            "id": actor_id,
            "label": label,
            "type": "SAAS_ADMIN" if is_saas else "USER",
            "is_saas": is_saas,
            "tenant_id": payload.get("tenant_id"),
            "tenant_code": payload.get("tenant_code"),
        }

    def _persist_audit_log(
        self,
        *,
        request: Request,
        response: Response,
        request_id: str,
        client_ip: str,
        user_agent: str,
    ) -> None:
        """
        Persist a lightweight AuditLog row.

        The current AuditLog model supports:
        - actor_user_id
        - action
        - entity_name
        - entity_id
        - request_id
        - ip_address
        - user_agent
        - before_data / after_data / extra_metadata
        """
        from app.services import audit_service

        actor = self._actor_context(request)
        action = self.method_action.get(request.method.upper(), request.method.upper())
        entity_name = self._derive_entity_name(request.url.path)
        extra = {"query_params": dict(request.query_params)}

        # SaaS / master operation (no tenant bound) → master SaaSAuditLog.
        if get_current_tenant() is None or actor.get("is_saas"):
            audit_service.write_saas_audit_autocommit(
                action=action,
                entity_name=entity_name,
                actor_admin_id=actor["id"] if actor.get("is_saas") else None,
                actor_label=actor["label"],
                actor_type=actor["type"],
                request_id=request_id,
                ip_address=client_ip,
                user_agent=user_agent,
                http_method=request.method.upper(),
                path=request.url.path,
                status_code=response.status_code,
                extra_metadata=extra,
            )
            return

        # Tenant operation → tenant AuditLog (its own short session).
        from app.core.database import get_session

        db: Session = get_session()
        try:
            audit_service.write_tenant_audit(
                db,
                action=action,
                entity_name=entity_name,
                actor_user_id=actor["id"],
                actor_label=actor["label"],
                actor_type=actor["type"],
                request_id=request_id,
                ip_address=client_ip,
                user_agent=user_agent,
                http_method=request.method.upper(),
                path=request.url.path,
                status_code=response.status_code,
                extra_metadata=extra,
            )
        finally:
            db.close()

    def _derive_entity_name(self, path: str) -> str:
        """
        Derive a coarse entity name from the URL path.

        Example:
            /api/v1/patients/12 -> PATIENTS
        """
        parts = [part for part in path.strip("/").split("/") if part]
        if not parts:
            return "ROOT"

        # Try to skip common API prefixes like /api/v1/.
        filtered = [p for p in parts if p.lower() not in {"api", "v1", "v2"}]
        if not filtered:
            return parts[-1].upper()

        return filtered[0].upper()