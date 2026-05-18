# app/core/multitenancy.py
"""
Request-scoped tenant context helpers.

The active tenant is stored in a :class:`contextvars.ContextVar` so it is
isolated per request without leaking between concurrent tasks.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

from app.core.cryptography import decrypt_string
from app.models.all_models import Tenant


_current_tenant: ContextVar[Optional[Tenant]] = ContextVar(
    "current_tenant", default=None
)


def set_current_tenant(tenant: Optional[Tenant]) -> None:
    """Bind ``tenant`` to the current request context."""
    _current_tenant.set(tenant)


def clear_current_tenant() -> None:
    """Remove any tenant binding from the current request context."""
    _current_tenant.set(None)


def get_current_tenant() -> Optional[Tenant]:
    """Return the tenant bound to the current request, if any."""
    return _current_tenant.get()


def get_current_tenant_id() -> Optional[int]:
    tenant = get_current_tenant()
    return tenant.id if tenant else None


def get_current_tenant_code() -> Optional[str]:
    tenant = get_current_tenant()
    return tenant.code if tenant else None


def require_current_tenant() -> Tenant:
    """
    Return the active tenant or raise. Useful inside services that *must*
    operate within a tenant context.
    """
    from app.core.exceptions import ForbiddenError

    tenant = get_current_tenant()
    if tenant is None:
        raise ForbiddenError(message="Tenant context is required for this operation.")
    return tenant


def get_current_tenant_db_url() -> Optional[str]:
    tenant = get_current_tenant()
    if not tenant or not tenant.db_connection_string:
        return None
    return decrypt_string(tenant.db_connection_string)




