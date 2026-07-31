# app/dependencies/api_key_auth.py
from __future__ import annotations

"""
Authentication for third-party integration partners via API key.

The partner presents its key in the ``X-API-Key`` header (or ``Authorization:
Bearer <key>``). We resolve the owning tenant from the key and bind it to the
request context so the normal ``get_db`` dependency connects to that tenant's
database — no JWT/session required.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.api_key import extract_prefix, verify_api_key
from app.core.database import get_db, get_master_db_context
from app.core.multitenancy import set_current_tenant


class ApiPartner:
    def __init__(self, partner_id: int, tenant_id: int, name: str, scopes: set[str]) -> None:
        self.id = partner_id
        self.tenant_id = tenant_id
        self.name = name
        self.scopes = scopes


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _presented_key(request: Request, x_api_key: Optional[str]) -> Optional[str]:
    if x_api_key:
        return x_api_key
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def require_api_partner(scope: str = "READ"):
    """Dependency factory. Verifies the key carries ``scope`` and binds the
    partner's tenant to the request context."""

    def _dep(
        request: Request,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ) -> ApiPartner:
        key = _presented_key(request, x_api_key)
        if not key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required.")
        prefix = extract_prefix(key)
        if not prefix:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed API key.")

        from app.models.all_models import IntegrationPartner, Tenant

        with get_master_db_context() as mdb:
            partner = (
                mdb.query(IntegrationPartner)
                .filter(IntegrationPartner.key_prefix == prefix, IntegrationPartner.is_deleted.is_(False))
                .first()
            )
            if partner is None or not partner.is_active or not verify_api_key(key, partner.key_hash):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
            if partner.expires_at is not None and _now() > _as_utc(partner.expires_at):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key has expired.")

            scopes = {s.strip().upper() for s in (partner.scopes or "").split(",") if s.strip()}
            if scope.upper() not in scopes:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"API key lacks the {scope.upper()} scope.")

            tenant = mdb.query(Tenant).filter(Tenant.id == partner.tenant_id).first()
            if tenant is None or not tenant.db_connection_string:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Partner tenant is not reachable.")

            try:
                partner.last_used_at = _now()
                partner.last_used_ip = request.client.host if request.client else None
                mdb.add(partner)
                mdb.commit()
            except Exception:
                mdb.rollback()

            principal = ApiPartner(partner.id, tenant.id, partner.name, scopes)

        # Bind tenant so the subsequently-resolved get_db connects to it.
        set_current_tenant(tenant)
        return principal

    return _dep


# Ordered dependencies: the partner (and tenant binding) resolves BEFORE get_db,
# because FastAPI resolves a dependant's sub-dependencies in signature order.
def integration_read_ctx(
    partner: ApiPartner = Depends(require_api_partner("READ")),
    db: Session = Depends(get_db),
) -> tuple[ApiPartner, Session]:
    return partner, db


def integration_write_ctx(
    partner: ApiPartner = Depends(require_api_partner("WRITE")),
    db: Session = Depends(get_db),
) -> tuple[ApiPartner, Session]:
    return partner, db
