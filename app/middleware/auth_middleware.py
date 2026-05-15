# carepoint_hms/app/middleware/auth_middleware.py
from __future__ import annotations

"""
Authentication middleware for Carepoint HMS.

Purpose
-------
This middleware performs lightweight bearer-token parsing and user resolution,
then attaches the authenticated user and token payload to `request.state`.

What it does
------------
- reads Authorization: Bearer <token>
- decodes the JWT using app.core.security
- looks up the user in the database
- attaches:
  - request.state.token_payload
  - request.state.current_user
  - request.state.current_session_jti

What it does NOT do
-------------------
- it does not reject unauthenticated requests globally by default
- it does not replace route-level authorization dependencies
- it does not enforce roles or 2FA; those belong in dependencies

This middleware is best used to make user context available for:
- audit logging
- request logging
- optional route behavior
"""

from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from sqlalchemy.orm import Session, joinedload

from app.core.database import SessionLocal
from app.core.logger import get_request_logger
from app.core.security import decode_token
from app.models.all_models import User, UserRoleAssociation


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Lightweight authentication context middleware.
    """

    def __init__(
        self,
        app,
        *,
        attach_user_context: bool = True,
        ignore_invalid_token: bool = True,
    ) -> None:
        super().__init__(app)
        self.attach_user_context = attach_user_context
        self.ignore_invalid_token = ignore_invalid_token

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Parse bearer token and attach user context to request.state.
        """
        request_id = getattr(request.state, "request_id", None)
        logger = get_request_logger(__name__, request_id=request_id)

        # Initialize state so downstream code can rely on these attributes.
        request.state.token_payload = None
        request.state.current_user = None
        request.state.current_session_jti = None

        if self.attach_user_context:
            auth_header = request.headers.get("Authorization")
            token = self._extract_bearer_token(auth_header)

            if token:
                try:
                    payload = decode_token(token)
                    request.state.token_payload = payload
                    request.state.current_session_jti = payload.get("jti")

                    # Resolve tenant context from JWT if present
                    tenant_id = payload.get("tenant_id")
                    if tenant_id:
                        from app.core.multitenancy import set_current_tenant
                        from app.repositories.tenant_repository import TenantRepository
                        from app.core.database import get_master_db_context
                        
                        with get_master_db_context() as db:
                            repo = TenantRepository(db)
                            tenant = repo.get_tenant_by_id(tenant_id)
                            if tenant:
                                set_current_tenant(tenant)

                    user_id = payload.get("sub")
                    if user_id is not None:
                        # Skip loading tenant User for SaaS admins
                        if payload.get("is_saas_admin"):
                            pass
                        else:
                            user = self._load_user(user_id)
                            request.state.current_user = user

                except Exception as exc:
                    # Middleware should usually avoid breaking public/optional
                    # endpoints unless explicitly configured otherwise.
                    print(f"DEBUG: AuthMiddleware caught exception: {exc}")
                    logger.debug(f"AuthMiddleware exception: {exc}, ignore_invalid_token: {self.ignore_invalid_token}")
                    if not self.ignore_invalid_token:
                        raise

                    # An expired/malformed token on a route that doesn't
                    # require auth (e.g. ``/tenants/register``,
                    # ``/auth/refresh``, public callbacks) is not actionable
                    # for operators — log at DEBUG so prod logs stay clean.
                    # Route-level dependencies still reject the token when
                    # the endpoint actually needs auth.
                    logger.debug(
                        "Invalid bearer token ignored in middleware: %s",
                        exc,
                        extra={"request_id": request_id},
                    )

        response = await call_next(request)
        return response

    def _extract_bearer_token(self, authorization_header: Optional[str]) -> Optional[str]:
        """
        Extract the bearer token from an Authorization header.
        """
        if not authorization_header:
            return None

        parts = authorization_header.strip().split()
        if len(parts) != 2:
            return None

        scheme, token = parts
        if scheme.lower() != "bearer":
            return None

        return token.strip()

    def _load_user(self, user_id: str | int) -> Optional[User]:
        """
        Load the authenticated user and eager-load roles.
        """
        from app.core.database import get_session
        db: Session = get_session()
        try:
            user = (
                db.query(User)
                .options(joinedload(User.user_roles).joinedload(UserRoleAssociation.role))
                .filter(
                    User.id == int(user_id),
                    User.is_deleted.is_(False),
                )
                .first()
            )
            if user:
                # Detach from session so it can be used after session closure
                db.expunge(user)
            return user
        finally:
            db.close()