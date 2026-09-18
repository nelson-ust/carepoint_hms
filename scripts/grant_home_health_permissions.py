"""
Grant the Home Health permissions to an already-provisioned tenant.

Existing tenants were seeded before the Home Health module was added, so its
permission catalog rows and role grants are missing. This idempotent script
inserts the 16 HOME_HEALTH permissions, ensures the HOME_HEALTH_COORDINATOR
role exists, and wires the role -> permission grants. Safe to re-run; it never
deletes or modifies clinical data.

Usage:
    python scripts/grant_home_health_permissions.py --tenant STMARY
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

HOME_HEALTH_PERMISSIONS = [
    ("HOME_VISIT_READ", "View home visits"),
    ("HOME_VISIT_CREATE", "Request/schedule home visits"),
    ("HOME_VISIT_UPDATE", "Update home visits"),
    ("HOME_VISIT_ASSIGN", "Assign home-visit caregivers"),
    ("HOME_VISIT_DOCUMENT", "Document home visits"),
    ("HOME_VISIT_CANCEL", "Cancel home visits"),
    ("CARE_PLAN_READ", "View care plans"),
    ("CARE_PLAN_CREATE", "Create care plans"),
    ("CARE_PLAN_UPDATE", "Update care plans"),
    ("CARE_PLAN_MANAGE", "Manage care-plan goals, interventions, tasks and reviews"),
    ("REMOTE_MONITORING_READ", "View remote monitoring data"),
    ("REMOTE_MONITORING_RECORD", "Record remote monitoring readings"),
    ("REMOTE_MONITORING_MANAGE", "Manage monitoring devices and thresholds"),
    ("CLINICAL_ALERT_READ", "View clinical alerts"),
    ("CLINICAL_ALERT_MANAGE", "Acknowledge, resolve and escalate clinical alerts"),
    ("ALERT_RULE_MANAGE", "Manage early-warning rules"),
]

_ALL = [c for c, _ in HOME_HEALTH_PERMISSIONS]
ROLE_GRANTS = {
    "TENANT_ADMIN": _ALL,
    "ADMIN": _ALL,
    "HOME_HEALTH_COORDINATOR": _ALL,
    "DOCTOR": _ALL,
    "NURSE": [
        "HOME_VISIT_READ", "HOME_VISIT_UPDATE", "HOME_VISIT_DOCUMENT",
        "CARE_PLAN_READ", "CARE_PLAN_MANAGE",
        "REMOTE_MONITORING_READ", "REMOTE_MONITORING_RECORD",
        "CLINICAL_ALERT_READ", "CLINICAL_ALERT_MANAGE",
    ],
    "CLINICIAN": [
        "HOME_VISIT_READ", "HOME_VISIT_DOCUMENT", "CARE_PLAN_READ",
        "REMOTE_MONITORING_READ", "REMOTE_MONITORING_RECORD", "CLINICAL_ALERT_READ",
    ],
    "RECEPTIONIST": [
        "HOME_VISIT_READ", "HOME_VISIT_CREATE", "HOME_VISIT_UPDATE",
        "HOME_VISIT_ASSIGN", "HOME_VISIT_CANCEL", "CARE_PLAN_READ",
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
    for code, name in HOME_HEALTH_PERMISSIONS:
        perm = db.query(Permission).filter(Permission.code == code).first()
        if not perm:
            perm = Permission(code=code, name=name, module="HOME_HEALTH")
            db.add(perm)
            db.flush()
            print(f"  + permission {code}")
        out[code] = perm
    return out


def ensure_role(db: Session, code: str, name: str, description: str) -> Role:
    role = db.query(Role).filter(Role.code == code).first()
    if not role:
        role = Role(code=code, name=name, description=description, is_system=True)
        db.add(role)
        db.flush()
        print(f"  + role {code}")
    return role


def grant(db: Session, perms: dict[str, Permission]) -> None:
    ensure_role(db, "HOME_HEALTH_COORDINATOR", "Home Health Coordinator",
                "Coordinates home visits, care plans and remote monitoring.")
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
    parser = argparse.ArgumentParser(description="Grant Home Health permissions to a tenant.")
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

    print(f"Granting Home Health permissions to tenant: {tenant.name} ({tenant.code})")
    engine = create_engine(db_url, poolclass=NullPool, future=True)
    with Session(engine) as db:
        perms = upsert_permissions(db)
        grant(db, perms)
        db.commit()
    engine.dispose()
    print("Done. Home Health permissions granted (idempotent).")


if __name__ == "__main__":
    main()
