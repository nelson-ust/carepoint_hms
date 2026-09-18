"""
Grant the Telemedicine permissions to an already-provisioned tenant.

Existing tenants were seeded before the Telemedicine module was added, so its
permission catalog rows and role grants are missing. This idempotent script
inserts the 5 TELEMEDICINE permissions and wires the role -> permission grants.
Safe to re-run; it never deletes or modifies clinical data.

Usage:
    python scripts/grant_telemedicine_permissions.py --tenant STMARY
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.cryptography import decrypt_string
from app.core.database import get_master_engine
from app.core.multitenancy import set_current_tenant
from app.models.all_models import (
    Permission,
    Role,
    RolePermissionAssociation,
    Tenant,
)

TELEMEDICINE_PERMISSIONS = [
    ("TELEMEDICINE_READ", "View telemedicine sessions"),
    ("TELEMEDICINE_CREATE", "Schedule telemedicine sessions"),
    ("TELEMEDICINE_UPDATE", "Update telemedicine sessions"),
    ("TELEMEDICINE_CONDUCT", "Conduct telemedicine sessions and document notes"),
    ("TELEMEDICINE_CANCEL", "Cancel telemedicine sessions"),
]

_ALL = [c for c, _ in TELEMEDICINE_PERMISSIONS]
ROLE_GRANTS = {
    "TENANT_ADMIN": _ALL,
    "ADMIN": _ALL,
    "HOME_HEALTH_COORDINATOR": _ALL,
    "DOCTOR": _ALL,
    "NURSE": ["TELEMEDICINE_READ", "TELEMEDICINE_CONDUCT"],
    "CLINICIAN": ["TELEMEDICINE_READ", "TELEMEDICINE_CONDUCT"],
    "RECEPTIONIST": [
        "TELEMEDICINE_READ", "TELEMEDICINE_CREATE",
        "TELEMEDICINE_UPDATE", "TELEMEDICINE_CANCEL",
    ],
}


def resolve_tenant(master_db: Session, tenant_arg: str) -> Tenant | None:
    q = master_db.query(Tenant)
    if tenant_arg and tenant_arg.isdigit():
        return q.filter(Tenant.id == int(tenant_arg)).first()
    if tenant_arg:
        return q.filter(Tenant.code.ilike(tenant_arg)).first()
    return q.order_by(Tenant.id.asc()).first()


def upsert_permissions(db: Session) -> dict[str, Permission]:
    out: dict[str, Permission] = {}
    for code, name in TELEMEDICINE_PERMISSIONS:
        perm = db.query(Permission).filter(Permission.code == code).first()
        if not perm:
            perm = Permission(code=code, name=name, module="TELEMEDICINE")
            db.add(perm)
            db.flush()
            print(f"  + permission {code}")
        out[code] = perm
    return out


def grant(db: Session, perms: dict[str, Permission]) -> None:
    for role_code, codes in ROLE_GRANTS.items():
        role = db.query(Role).filter(Role.code == role_code).first()
        if not role:
            continue
        for code in codes:
            perm = perms.get(code)
            if not perm:
                continue
            exists = (
                db.query(RolePermissionAssociation)
                .filter(
                    RolePermissionAssociation.role_id == role.id,
                    RolePermissionAssociation.permission_id == perm.id,
                )
                .first()
            )
            if not exists:
                db.add(RolePermissionAssociation(role_id=role.id, permission_id=perm.id))
                print(f"  + grant {role_code} -> {code}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Grant Telemedicine permissions to a tenant.")
    parser.add_argument("--tenant", type=str, default=None, help="Tenant code or id.")
    args = parser.parse_args()

    master_engine = get_master_engine()
    with Session(master_engine) as master_db:
        tenant = resolve_tenant(master_db, args.tenant or "")
        if not tenant:
            print(f"Error: tenant '{args.tenant}' not found.")
            sys.exit(1)
        try:
            db_url = decrypt_string(tenant.db_connection_string)
        except Exception:
            db_url = tenant.db_connection_string
        master_db.expunge(tenant)
        set_current_tenant(tenant)

    print(f"Granting Telemedicine permissions to tenant: {tenant.name} ({tenant.code})")
    engine = create_engine(db_url, poolclass=NullPool, future=True)
    with Session(engine) as db:
        perms = upsert_permissions(db)
        grant(db, perms)
        db.commit()
    engine.dispose()
    print("Done. Telemedicine permissions granted (idempotent).")


if __name__ == "__main__":
    main()
