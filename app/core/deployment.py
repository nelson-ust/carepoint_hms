# app/core/deployment.py
from __future__ import annotations

"""
Deployment-mode helpers: SaaS platform vs dedicated single-hospital install.

In **dedicated** mode the whole application serves exactly one hospital:

* Master + tenant tables live in ONE database (``DATABASE_URL``); the master
  engine already falls back to it when ``MASTER_DATABASE_URL`` is unset.
* One ``Tenant`` row (code = ``DEDICATED_TENANT_CODE``) represents the
  hospital and is bound to every request by the tenant middleware, so all
  tenant-scoped code paths work unchanged.
* There is no subscription: access is governed by an **annual licence**
  (``LICENSE_EXPIRES_AT`` + ``LICENSE_GRACE_DAYS``). Inside the grace window
  requests carry warning headers; after it, mutating access is blocked with
  a clear 402-style message until the licence date is extended.
* SaaS-platform surfaces (tenant provisioning, SaaS admin portal,
  subscription billing, developer platform, master backups) are not exposed.
"""

from datetime import date
from typing import Optional

from app.core.config import settings

#: API path prefixes that only make sense on the multi-tenant platform.
SAAS_ONLY_PATH_PREFIXES: tuple[str, ...] = (
    "/api/v1/saas",
    "/api/v1/subscription-billing",
    "/api/v1/tenants",
    "/api/v1/tenant-domains",
    "/api/v1/developer",
    "/api/v1/backups/master",
)


def is_dedicated() -> bool:
    return settings.is_dedicated


def is_saas_only_path(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") or path.startswith(p + "?")
               or path.startswith(p) for p in SAAS_ONLY_PATH_PREFIXES)


def license_status(today: Optional[date] = None) -> dict:
    """Current licence posture for a dedicated install.

    Returns ``{mode, licensed_until, days_left, in_grace, blocked, message}``.
    ``days_left`` is negative once past the licence date. When no licence
    date is configured the licence is treated as unenforced (never blocked).
    """
    today = today or date.today()
    expires = settings.LICENSE_EXPIRES_AT
    grace = max(0, int(settings.LICENSE_GRACE_DAYS or 0))
    out = {
        "mode": "dedicated" if settings.is_dedicated else "saas",
        "licensed_until": expires.isoformat() if expires else None,
        "days_left": None,
        "in_grace": False,
        "blocked": False,
        "message": None,
    }
    if not settings.is_dedicated or expires is None:
        return out
    days_left = (expires - today).days
    out["days_left"] = days_left
    if days_left < 0:
        overdue = -days_left
        if overdue <= grace:
            out["in_grace"] = True
            out["message"] = (
                f"The annual licence expired on {expires.isoformat()}. "
                f"{grace - overdue} grace day(s) remain; please renew.")
        else:
            out["blocked"] = True
            out["message"] = (
                f"The annual licence expired on {expires.isoformat()} and the "
                f"{grace}-day grace period has ended. Contact your vendor to "
                "renew; access resumes as soon as LICENSE_EXPIRES_AT is extended.")
    elif days_left <= 30:
        out["message"] = (
            f"The annual licence ends on {expires.isoformat()} "
            f"({days_left} day(s) left).")
    return out


def get_or_create_dedicated_tenant(db):
    """Return (creating if needed) the single Tenant row of a dedicated
    install, its connection string pointing back at the same database."""
    from sqlalchemy.engine import make_url

    from app.core.cryptography import encrypt_string
    from app.models.all_models import Tenant

    code = settings.DEDICATED_TENANT_CODE.strip().lower()
    tenant = (db.query(Tenant)
              .filter(Tenant.code == code, Tenant.is_deleted.is_(False))
              .first())
    if tenant is not None:
        return tenant
    try:
        db_name = make_url(settings.DATABASE_URL).database
    except Exception:
        db_name = None
    tenant = Tenant(
        code=code,
        name=settings.DEDICATED_TENANT_NAME,
        # domain_url is NOT NULL + unique on the platform; a dedicated install
        # has no subdomain routing, so a synthetic local domain satisfies it.
        domain_url=f"{code}.dedicated.local",
        db_name=db_name,
        db_connection_string=encrypt_string(settings.DATABASE_URL),
        is_active=True,
        is_provisioned=True,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant
