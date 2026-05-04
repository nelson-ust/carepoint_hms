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
from app.models.all_models import AuditLog
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
        """
        if not self.persist_audit_log:
            return False

        if get_current_tenant() is None:
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

    def _extract_actor_user_id(self, request: Request) -> Optional[int]:
        """
        Best-effort extraction of authenticated user ID from request.state.

        This relies on route/dependency code placing the current user on
        `request.state.current_user` when available.
        """
        current_user = getattr(request.state, "current_user", None)
        if current_user is None:
            return None

        user_id = getattr(current_user, "id", None)
        try:
            return int(user_id) if user_id is not None else None
        except (TypeError, ValueError):
            return None

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
        from app.core.database import get_session
        db: Session = get_session()
        try:
            action = request.method.upper()
            entity_name = self._derive_entity_name(request.url.path)

            audit_log = AuditLog(
                actor_user_id=self._extract_actor_user_id(request),
                action=action,
                entity_name=entity_name,
                entity_id=None,
                request_id=request_id,
                ip_address=client_ip,
                user_agent=user_agent,
                before_data=None,
                after_data=None,
                extra_metadata={
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "query_params": dict(request.query_params),
                },
            )

            db.add(audit_log)
            db.commit()
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