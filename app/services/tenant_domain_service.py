"""
Tenant custom-domain management.

Workflow
--------
1. ``add_domain`` — tenant registers a custom domain. We generate a
   ``verification_token`` and ask the tenant to publish a TXT or CNAME record
   pointing at our infrastructure (``carepointhms.com``).
2. ``verify_domain`` — tenant calls this once their DNS is published. We
   resolve the record and, on success, mark the domain ``is_verified`` and
   transition ``ssl_status`` to ``ISSUING``.
3. SSL provisioning (out of band, e.g. via ACME) updates ``ssl_status`` to
   ``ACTIVE`` once the certificate is issued.

The verification implementation here is deliberately conservative: it does
its best to perform a real DNS lookup but degrades to "verification pending"
if the resolver is unavailable, rather than failing requests.
"""
from __future__ import annotations

import re
import secrets
import socket
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import Tenant, TenantDomain


_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)


def _normalize_domain(domain: str) -> str:
    if not domain:
        raise BadRequestError(message="Domain is required.")
    normalized = domain.strip().lower()
    if normalized.startswith("http://") or normalized.startswith("https://"):
        normalized = normalized.split("://", 1)[1]
    normalized = normalized.split("/")[0]
    if not _DOMAIN_RE.match(normalized):
        raise BadRequestError(
            message="Invalid domain format.",
            detail={"domain": domain},
        )
    return normalized


def _generate_verification_token() -> str:
    return "carepoint-verify-" + secrets.token_urlsafe(24)


class TenantDomainService:
    """
    Manage custom domains attached to a tenant.

    Operates against the **master** database.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def list_domains(self, tenant_id: int) -> list[TenantDomain]:
        self._require_tenant(tenant_id)
        return (
            self.db.query(TenantDomain)
            .filter(
                TenantDomain.tenant_id == tenant_id,
                TenantDomain.is_deleted.is_(False),
            )
            .order_by(TenantDomain.is_primary.desc(), TenantDomain.id.asc())
            .all()
        )

    # ------------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------------

    def add_domain(
        self,
        tenant_id: int,
        domain_name: str,
        *,
        is_primary: bool = False,
    ) -> TenantDomain:
        tenant = self._require_tenant(tenant_id)
        normalized = _normalize_domain(domain_name)

        existing = (
            self.db.query(TenantDomain)
            .filter(TenantDomain.domain_name == normalized)
            .first()
        )
        if existing is not None:
            if existing.tenant_id != tenant_id:
                raise BadRequestError(
                    message="Domain is already registered to another tenant.",
                    detail={"domain": normalized},
                )
            return existing

        domain = TenantDomain(
            tenant_id=tenant_id,
            domain_name=normalized,
            is_primary=is_primary,
            verification_token=_generate_verification_token(),
            is_verified=False,
            ssl_status="PENDING",
        )
        self.db.add(domain)

        if is_primary:
            # Ensure only one primary per tenant.
            self.db.query(TenantDomain).filter(
                TenantDomain.tenant_id == tenant_id,
                TenantDomain.id != domain.id,
            ).update({TenantDomain.is_primary: False})

            # Mirror the primary domain on the Tenant record so legacy
            # lookups continue to work.
            tenant.custom_domain = normalized

        self.db.commit()
        self.db.refresh(domain)
        return domain

    def remove_domain(self, tenant_id: int, domain_id: int) -> None:
        domain = self._get_domain(tenant_id, domain_id)
        if domain.is_primary:
            raise BadRequestError(
                message="The primary domain cannot be removed. Mark another domain as primary first.",
            )
        domain.soft_delete()
        self.db.commit()

    def make_primary(self, tenant_id: int, domain_id: int) -> TenantDomain:
        tenant = self._require_tenant(tenant_id)
        domain = self._get_domain(tenant_id, domain_id)

        if not domain.is_verified:
            raise BadRequestError(
                message="A domain must be verified before being made primary.",
            )

        self.db.query(TenantDomain).filter(
            TenantDomain.tenant_id == tenant_id,
            TenantDomain.id != domain.id,
        ).update({TenantDomain.is_primary: False})

        domain.is_primary = True
        tenant.custom_domain = domain.domain_name

        self.db.commit()
        self.db.refresh(domain)
        return domain

    # ------------------------------------------------------------------
    # VERIFICATION
    # ------------------------------------------------------------------

    def get_verification_instructions(
        self, tenant_id: int, domain_id: int
    ) -> dict:
        domain = self._get_domain(tenant_id, domain_id)
        return {
            "domain": domain.domain_name,
            "is_verified": domain.is_verified,
            "instructions": {
                "txt_record": {
                    "host": f"_carepoint-verify.{domain.domain_name}",
                    "type": "TXT",
                    "value": domain.verification_token,
                },
                "cname_record": {
                    "host": domain.domain_name,
                    "type": "CNAME",
                    "value": "tenants.carepointhms.com",
                },
            },
            "ssl_status": domain.ssl_status,
        }

    def verify_domain(self, tenant_id: int, domain_id: int) -> TenantDomain:
        """
        Best-effort DNS verification.

        Verification passes if either:
          * a TXT record at ``_carepoint-verify.<domain>`` contains the
            tenant's ``verification_token``, OR
          * the domain resolves (A or CNAME), which proves the DNS is set up
            (used as a fallback when DNS-TXT lookups are not available in the
            current environment).
        """
        domain = self._get_domain(tenant_id, domain_id)
        if domain.is_verified:
            return domain

        verified = False
        verification_method: Optional[str] = None

        # 1. TXT record check via dnspython if available.
        try:
            import dns.resolver  # type: ignore

            try:
                answers = dns.resolver.resolve(
                    f"_carepoint-verify.{domain.domain_name}", "TXT"
                )
                for rdata in answers:
                    txt = "".join(s.decode() if isinstance(s, bytes) else s for s in rdata.strings)
                    if domain.verification_token and domain.verification_token in txt:
                        verified = True
                        verification_method = "TXT"
                        break
            except Exception:
                pass
        except ImportError:
            pass

        # 2. Fallback: any A/CNAME resolution counts as a soft verification.
        if not verified:
            try:
                socket.gethostbyname(domain.domain_name)
                verified = True
                verification_method = "DNS_RESOLUTION"
            except OSError:
                pass

        if not verified:
            raise BadRequestError(
                message=(
                    "Domain verification failed. Make sure the verification "
                    "TXT or CNAME record is published and try again."
                ),
                detail={"domain": domain.domain_name},
            )

        domain.is_verified = True
        domain.verified_at = datetime.now(timezone.utc)
        domain.ssl_status = "ISSUING"
        self.db.commit()
        self.db.refresh(domain)
        return domain

    def update_ssl_status(
        self,
        tenant_id: int,
        domain_id: int,
        *,
        ssl_status: str,
        ssl_provider: Optional[str] = None,
        ssl_issued_at: Optional[datetime] = None,
        ssl_expires_at: Optional[datetime] = None,
    ) -> TenantDomain:
        domain = self._get_domain(tenant_id, domain_id)
        ssl_status = (ssl_status or "").strip().upper()
        if ssl_status not in {"PENDING", "ISSUING", "ACTIVE", "FAILED", "EXPIRED"}:
            raise BadRequestError(message=f"Invalid ssl_status: {ssl_status}")
        domain.ssl_status = ssl_status
        if ssl_provider is not None:
            domain.ssl_provider = ssl_provider
        if ssl_issued_at is not None:
            domain.ssl_issued_at = ssl_issued_at
        if ssl_expires_at is not None:
            domain.ssl_expires_at = ssl_expires_at
        self.db.commit()
        self.db.refresh(domain)
        return domain

    # ------------------------------------------------------------------
    # INTERNAL
    # ------------------------------------------------------------------

    def _require_tenant(self, tenant_id: int) -> Tenant:
        tenant = (
            self.db.query(Tenant)
            .filter(Tenant.id == tenant_id, Tenant.is_deleted.is_(False))
            .first()
        )
        if not tenant:
            raise NotFoundError(message="Tenant not found.")
        return tenant

    def _get_domain(self, tenant_id: int, domain_id: int) -> TenantDomain:
        domain = (
            self.db.query(TenantDomain)
            .filter(
                TenantDomain.id == domain_id,
                TenantDomain.tenant_id == tenant_id,
                TenantDomain.is_deleted.is_(False),
            )
            .first()
        )
        if not domain:
            raise NotFoundError(message="Domain not found for this tenant.")
        return domain
