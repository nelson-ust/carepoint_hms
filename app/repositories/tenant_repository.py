# app/repositories/tenant_repository.py
"""
Master-DB repository for tenant lookup.

Used by:
- TenantMiddleware (to resolve a tenant per request)
- AuthService (to discover a tenant from a login identifier)
- TenantService (CRUD-style operations)

This repository operates against the **master** database. It must never be
called inside a tenant DB session.
"""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.enums import UserStatus
from app.models.all_models import Tenant, TenantDomain


class TenantRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_tenant_by_id(self, tenant_id: int) -> Optional[Tenant]:
        return (
            self.db.query(Tenant)
            .filter(Tenant.id == tenant_id, Tenant.is_deleted.is_(False))
            .first()
        )

    def get_tenant_by_code(self, code: str) -> Optional[Tenant]:
        """
        Resolve a tenant by its short code (used for subdomain resolution and
        the ``X-Tenant-Code`` header).
        """
        if not code:
            return None
        return (
            self.db.query(Tenant)
            .filter(
                Tenant.code == code.strip().lower(),
                Tenant.is_deleted.is_(False),
            )
            .first()
        )

    # Back-compat alias used by older callers (auth_service, etc.).
    def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        return self.get_tenant_by_code(slug)

    def get_tenant_by_domain(self, domain_name: str) -> Optional[Tenant]:
        """
        Resolve a tenant by either:
          * the canonical ``domain_url`` on the Tenant record, or
          * the ``custom_domain`` field on the Tenant, or
          * any verified entry in ``TenantDomain``.
        """
        if not domain_name:
            return None

        normalized = domain_name.strip().lower()

        # Direct match on Tenant.domain_url or Tenant.custom_domain
        tenant = (
            self.db.query(Tenant)
            .filter(
                or_(Tenant.domain_url == normalized, Tenant.custom_domain == normalized),
                Tenant.is_deleted.is_(False),
            )
            .first()
        )
        if tenant:
            return tenant

        # Fall back to TenantDomain table.
        domain = (
            self.db.query(TenantDomain)
            .filter(
                TenantDomain.domain_name == normalized,
                TenantDomain.is_deleted.is_(False),
            )
            .first()
        )
        return domain.tenant if domain else None

    def get_active_tenants(self) -> list[Tenant]:
        return (
            self.db.query(Tenant)
            .filter(
                Tenant.is_deleted.is_(False),
                Tenant.status == UserStatus.ACTIVE,
            )
            .all()
        )

    def list_tenants(self) -> list[Tenant]:
        return self.db.query(Tenant).filter(Tenant.is_deleted.is_(False)).all()

    # ------------------------------------------------------------------
    # DOMAIN MANAGEMENT
    # ------------------------------------------------------------------

    def list_domains_for_tenant(self, tenant_id: int) -> list[TenantDomain]:
        return (
            self.db.query(TenantDomain)
            .filter(
                TenantDomain.tenant_id == tenant_id,
                TenantDomain.is_deleted.is_(False),
            )
            .order_by(TenantDomain.is_primary.desc(), TenantDomain.id.asc())
            .all()
        )

    def get_domain(self, domain_name: str) -> Optional[TenantDomain]:
        if not domain_name:
            return None
        return (
            self.db.query(TenantDomain)
            .filter(
                TenantDomain.domain_name == domain_name.strip().lower(),
                TenantDomain.is_deleted.is_(False),
            )
            .first()
        )

    def add_domain(
        self,
        *,
        tenant_id: int,
        domain_name: str,
        is_primary: bool = False,
        verification_token: Optional[str] = None,
        is_verified: bool = False,
    ) -> TenantDomain:
        domain = TenantDomain(
            tenant_id=tenant_id,
            domain_name=domain_name.strip().lower(),
            is_primary=is_primary,
        )
        # Optional fields are tolerated even if the model does not define them
        # yet (forward-compatible with the SSL/verification migration).
        for field, value in (
            ("verification_token", verification_token),
            ("is_verified", is_verified),
        ):
            if hasattr(domain, field):
                setattr(domain, field, value)

        self.db.add(domain)
        self.db.flush()
        return domain
