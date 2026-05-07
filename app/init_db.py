from __future__ import annotations

"""
app.init_db

Database reset, initialization, and seed script for Carepoint HMS.

Purpose
-------
This script bootstraps the database for local development, test resets,
demos, and controlled first-time setup.

It can perform the following:
1. Check database connectivity
2. Optionally drop and recreate the PostgreSQL database itself
3. Drop and recreate all SQLAlchemy tables
4. Seed default roles
5. Seed default permissions
6. Seed default role-permission mappings
7. Seed default departments
8. Seed default service delivery points
9. Optionally create a default admin user
10. Optionally create a default admin staff profile

Important notes
---------------
- This script is intended for development, demos, tests, and controlled setup.
- In production, schema changes should be managed with Alembic migrations.
- Database recreation is destructive and will erase all data in the target DB.
- Actual database recreation is implemented for PostgreSQL URLs only.
"""

import argparse
import logging
from contextlib import contextmanager
from typing import Any, Generator

from sqlalchemy import create_engine, or_, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import get_logger
from app.core.database import (
    DATABASE_URL,
    MASTER_DATABASE_URL,
    SessionLocal,
    check_database_connection,
    create_tables,
    drop_tables,
)
from app.core.enums import ServicePointType, UserStatus, SubscriptionInterval, SubscriptionStatus
from app.core.security import get_password_hash
from app.models.all_models import (
    Department,
    Permission,
    Role,
    RolePermissionAssociation,
    ServiceDeliveryPoint,
    StaffProfile,
    User,
    UserRoleAssociation,
    SubscriptionPlan,
    Tenant,
    TenantDomain,
    TenantSubscription,
    SaaSAdmin,
)
from app.models.base import MasterBase, TenantBase, BaseTable

logger = get_logger()


def check_production_safety(destructive: bool = False) -> None:
    """
    Prevent accidental data loss in production environments.
    """
    if settings.ENVIRONMENT == "production":
        if destructive:
            logger.critical("DESTRUCTIVE OPERATION ATTEMPTED IN PRODUCTION! BLOCKING.")
            raise RuntimeError("Destructive database operations are strictly forbidden in production.")
        else:
            logger.warning("Running initialization in PRODUCTION environment.")


# =============================================================================
# Seed data definitions
# =============================================================================

ROLE_SEEDS: list[dict[str, Any]] = [
    {
        "name": "TENANT_ADMIN",
        "code": "TENANT_ADMIN",
        "description": "System super administrator with full platform access.",
    },
    {
        "name": "ADMIN",
        "code": "ADMIN",
        "description": "Hospital administrator with broad operational access.",
    },
    {
        "name": "REGISTRAR",
        "code": "REGISTRAR",
        "description": "Registration/front desk officer.",
    },
    {
        "name": "CLINICIAN",
        "code": "CLINICIAN",
        "description": "Generic clinical practitioner role.",
    },
    {
        "name": "DOCTOR",
        "code": "DOCTOR",
        "description": "Medical doctor role.",
    },
    {
        "name": "NURSE",
        "code": "NURSE",
        "description": "Nursing staff role.",
    },
    {
        "name": "LAB_SCIENTIST",
        "code": "LAB_SCIENTIST",
        "description": "Laboratory scientist role.",
    },
    {
        "name": "LAB_TECHNICIAN",
        "code": "LAB_TECHNICIAN",
        "description": "Laboratory technician role.",
    },
    {
        "name": "PHARMACIST",
        "code": "PHARMACIST",
        "description": "Pharmacy role.",
    },
    {
        "name": "BILLING_OFFICER",
        "code": "BILLING_OFFICER",
        "description": "Billing and invoice management role.",
    },
    {
        "name": "CASHIER",
        "code": "CASHIER",
        "description": "Payment collection role.",
    },
    {
        "name": "HR_MANAGER",
        "code": "HR_MANAGER",
        "description": "Human resources manager role.",
    },
    {
        "name": "HR_OFFICER",
        "code": "HR_OFFICER",
        "description": "Human resources operations role.",
    },
]

PERMISSION_SEEDS: list[dict[str, Any]] = [
    # Dashboard
    {"name": "View Dashboard", "code": "dashboard:view", "module": "DASHBOARD", "description": "View dashboard"},

    # Users (action-level)
    {"name": "View Users", "code": "users:view", "module": "USERS", "description": "View users"},
    {"name": "Create Users", "code": "users:create", "module": "USERS", "description": "Create new users"},
    {"name": "Update Users", "code": "users:update", "module": "USERS", "description": "Update existing users"},
    {"name": "Delete Users", "code": "users:delete", "module": "USERS", "description": "Soft-delete users"},
    {"name": "Manage Users", "code": "users:manage", "module": "USERS", "description": "Full user administration"},
    {"name": "Invite Users", "code": "users:invite", "module": "USERS", "description": "Invite users to the tenant"},
    {"name": "Lock/Unlock Users", "code": "users:lock", "module": "USERS", "description": "Lock or unlock user accounts"},

    # RBAC
    {"name": "View Roles", "code": "roles:view", "module": "RBAC", "description": "View roles"},
    {"name": "Manage Roles", "code": "roles:manage", "module": "RBAC", "description": "Create, update, and assign roles"},
    {"name": "View Permissions", "code": "permissions:view", "module": "RBAC", "description": "View permissions"},
    {"name": "Manage Permissions", "code": "permissions:manage", "module": "RBAC", "description": "Manage permissions"},

    # Patients
    {"name": "Register Patient", "code": "patients:register", "module": "PATIENTS", "description": "Register patients"},
    {"name": "View Patients", "code": "patients:view", "module": "PATIENTS", "description": "View patient records"},
    {"name": "Manage Patients", "code": "patients:manage", "module": "PATIENTS", "description": "Manage patient records"},

    # Appointments
    {"name": "View Appointments", "code": "appointments:view", "module": "APPOINTMENTS", "description": "View appointments"},
    {"name": "Manage Appointments", "code": "appointments:manage", "module": "APPOINTMENTS", "description": "Manage appointments"},

    # Visits / Queue
    {"name": "Initiate Visit", "code": "visits:initiate", "module": "VISITS", "description": "Initiate patient visits"},
    {"name": "Manage Queue", "code": "queue:manage", "module": "QUEUE", "description": "Manage service point queues"},

    # Clinical
    {"name": "Manage Consultation", "code": "consultations:manage", "module": "CLINICAL", "description": "Create and update consultation records"},
    {"name": "Manage Diagnoses", "code": "diagnoses:manage", "module": "CLINICAL", "description": "Manage clinical diagnoses"},

    # Lab
    {"name": "Order Lab Tests", "code": "lab:order", "module": "LAB", "description": "Order lab tests"},
    {"name": "Manage Lab", "code": "lab:manage", "module": "LAB", "description": "Manage lab orders and results"},

    # Pharmacy
    {"name": "Prescribe Medication", "code": "pharmacy:prescribe", "module": "PHARMACY", "description": "Prescribe medication"},
    {"name": "Dispense Medication", "code": "pharmacy:dispense", "module": "PHARMACY", "description": "Dispense medication"},
    {"name": "Manage Pharmacy", "code": "pharmacy:manage", "module": "PHARMACY", "description": "Manage prescriptions and dispenses"},

    # Billing
    {"name": "Manage Billing", "code": "billing:manage", "module": "BILLING", "description": "Manage billing and invoices"},
    {"name": "Receive Payments", "code": "payments:receive", "module": "BILLING", "description": "Record payments"},

    # Inpatient
    {"name": "Manage Admission", "code": "admission:manage", "module": "ADMISSION", "description": "Manage admissions and discharges"},

    # Inventory
    {"name": "Manage Inventory", "code": "inventory:manage", "module": "INVENTORY", "description": "Manage inventory and stock"},

    # Ambulance
    {"name": "Manage Ambulance", "code": "ambulance:manage", "module": "AMBULANCE", "description": "Manage ambulance operations"},

    # HR
    {"name": "Manage HR", "code": "hr:manage", "module": "HR", "description": "Manage employee HR records"},

    # Reports
    {"name": "View Reports", "code": "reports:view", "module": "REPORTS", "description": "View reports"},

    # Tenant settings (self-service)
    {"name": "Manage Tenant Settings", "code": "tenant:settings:manage", "module": "TENANT", "description": "Manage tenant-level settings, branding and modules"},
]

ROLE_PERMISSION_MAP: dict[str, list[str]] = {
    "TENANT_ADMIN": [item["code"] for item in PERMISSION_SEEDS],
    "ADMIN": [
        "dashboard:view",
        "users:manage",
        "roles:manage",
        "patients:register",
        "patients:manage",
        "appointments:manage",
        "visits:initiate",
        "queue:manage",
        "consultations:manage",
        "lab:manage",
        "pharmacy:manage",
        "billing:manage",
        "payments:receive",
        "admission:manage",
        "inventory:manage",
        "ambulance:manage",
        "hr:manage",
        "reports:view",
    ],
    "REGISTRAR": [
        "dashboard:view",
        "patients:register",
        "patients:view",
        "patients:manage",
        "appointments:view",
        "appointments:manage",
        "visits:initiate",
        "queue:manage",
    ],
    "DOCTOR": [
        "dashboard:view",
        "patients:view",
        "patients:manage",
        "visits:initiate",
        "consultations:manage",
        "diagnoses:manage",
        "lab:order",
        "lab:manage",
        "pharmacy:prescribe",
        "pharmacy:manage",
        "admission:manage",
        "reports:view",
    ],
    "CLINICIAN": [
        "dashboard:view",
        "patients:view",
        "patients:manage",
        "visits:initiate",
        "consultations:manage",
        "diagnoses:manage",
        "lab:order",
        "pharmacy:prescribe",
    ],
    "NURSE": [
        "dashboard:view",
        "patients:view",
        "patients:manage",
        "queue:manage",
        "consultations:manage",
        "admission:manage",
    ],
    "LAB_SCIENTIST": [
        "dashboard:view",
        "lab:manage",
        "reports:view",
    ],
    "LAB_TECHNICIAN": [
        "dashboard:view",
        "lab:manage",
    ],
    "PHARMACIST": [
        "dashboard:view",
        "pharmacy:manage",
        "inventory:manage",
        "reports:view",
    ],
    "BILLING_OFFICER": [
        "dashboard:view",
        "billing:manage",
        "payments:receive",
        "reports:view",
    ],
    "CASHIER": [
        "dashboard:view",
        "payments:receive",
    ],
    "HR_MANAGER": [
        "dashboard:view",
        "hr:manage",
        "reports:view",
    ],
    "HR_OFFICER": [
        "dashboard:view",
        "hr:manage",
    ],
}

DEPARTMENT_SEEDS: list[dict[str, str]] = [
    {"name": "Administration", "code": "ADMIN", "description": "Hospital administration"},
    {"name": "Records", "code": "RECORDS", "description": "Patient registration and records"},
    {"name": "Outpatient", "code": "OPD", "description": "Outpatient services"},
    {"name": "Nursing", "code": "NURSING", "description": "Nursing department"},
    {"name": "Laboratory", "code": "LAB", "description": "Laboratory department"},
    {"name": "Pharmacy", "code": "PHARM", "description": "Pharmacy department"},
    {"name": "Billing", "code": "BILLING", "description": "Billing and cashiering"},
    {"name": "HR", "code": "HR", "description": "Human resources department"},
    {"name": "Emergency", "code": "ER", "description": "Emergency services"},
]

PLAN_SEEDS: list[dict[str, Any]] = [
    {
        "name": "Trial",
        "code": "TRIAL",
        "description": "Free trial of the platform for new tenants.",
        "price": 0.00,
        "trial_days": 30,
        "max_facilities": 1,
        "max_branches": 1,
        "max_users": 5,
        "max_patients": 500,
        "storage_limit_bytes": 1 * 1024 * 1024 * 1024,  # 1 GiB
        "has_clinical": True,
        "has_billing": True,
        "has_appointments": True,
    },
    {
        "name": "Basic",
        "code": "BASIC",
        "description": "Essential features for small clinics.",
        "price": 10000.00,
        "max_facilities": 1,
        "max_branches": 1,
        "max_users": 5,
        "storage_limit_bytes": 5 * 1024 * 1024 * 1024,  # 5 GiB
        "has_clinical": True,
        "has_billing": True,
        "has_appointments": True,
    },
    {
        "name": "Professional",
        "code": "PROFESSIONAL",
        "description": "Standard package for single hospitals.",
        "price": 25000.00,
        "max_facilities": 1,
        "max_branches": 3,
        "max_users": 50,
        "storage_limit_bytes": 25 * 1024 * 1024 * 1024,  # 25 GiB
        "has_clinical": True,
        "has_billing": True,
        "has_laboratory": True,
        "has_pharmacy": True,
        "has_inventory": True,
        "has_appointments": True,
        "has_patient_portal": True,
        "has_reporting": True,
    },
    {
        "name": "Enterprise",
        "code": "ENTERPRISE",
        "description": "Multi-facility and group hospitals with full module access.",
        "price": 75000.00,
        "max_facilities": 10,
        "max_branches": 25,
        "max_users": 500,
        "storage_limit_bytes": None,  # unlimited
        "has_clinical": True,
        "has_billing": True,
        "has_laboratory": True,
        "has_pharmacy": True,
        "has_inventory": True,
        "has_inpatient": True,
        "has_reporting": True,
        "has_appointments": True,
        "has_patient_portal": True,
        "has_insurance": True,
        "has_radiology": True,
        "has_surgical": True,
        "has_hr": True,
    },
]

SERVICE_DELIVERY_POINT_SEEDS: list[dict[str, Any]] = [
    {
        "name": "Front Desk Registration",
        "code": "REG",
        "service_point_type": "REGISTRATION",
        "department_code": "RECORDS",
        "location_description": "Front desk",
        "queue_prefix": "REG",
        "supports_appointments": True,
        "supports_walk_in": True,
    },
    {
        "name": "Triage",
        "code": "TRIAGE",
        "service_point_type": "TRIAGE",
        "department_code": "NURSING",
        "location_description": "Nursing triage point",
        "queue_prefix": "TRI",
        "supports_appointments": False,
        "supports_walk_in": True,
    },
    {
        "name": "Consultation Room",
        "code": "CONS",
        "service_point_type": "CLINIC",
        "department_code": "OPD",
        "location_description": "Outpatient consultation area",
        "queue_prefix": "CLI",
        "supports_appointments": True,
        "supports_walk_in": True,
    },
    {
        "name": "Laboratory Desk",
        "code": "LAB-DESK",
        "service_point_type": "LABORATORY",
        "department_code": "LAB",
        "location_description": "Main laboratory",
        "queue_prefix": "LAB",
        "supports_appointments": False,
        "supports_walk_in": True,
    },
    {
        "name": "Pharmacy Counter",
        "code": "PHARM-CTR",
        "service_point_type": "PHARMACY",
        "department_code": "PHARM",
        "location_description": "Main pharmacy counter",
        "queue_prefix": "PHA",
        "supports_appointments": False,
        "supports_walk_in": True,
    },
    {
        "name": "Billing Desk",
        "code": "BILL-CTR",
        "service_point_type": "CASHIER",
        "department_code": "BILLING",
        "location_description": "Main billing desk",
        "queue_prefix": "BIL",
        "supports_appointments": False,
        "supports_walk_in": True,
    },
]


# =============================================================================
# Database helpers
# =============================================================================

@contextmanager
def db_session_scope() -> Generator[Session, None, None]:
    """
    Provide a transactional scope around a series of operations.

    This function is used with a `with` statement, so it must be a proper
    context manager.
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _quote_identifier(identifier: str) -> str:
    """
    Quote a PostgreSQL identifier safely.
    """
    return '"' + identifier.replace('"', '""') + '"'


def _get_database_name(db_url: str) -> str:
    """
    Extract the database name from a connection URI.
    """
    url = make_url(db_url)
    if not url.database:
        raise ValueError(f"No database name could be resolved from {db_url}")
    return url.database


def _build_postgres_admin_uri(db_url: str) -> str:
    """
    Build an admin connection URI pointing to the PostgreSQL maintenance DB.
    """
    url = make_url(db_url)
    backend = url.get_backend_name()

    if backend != "postgresql":
        raise ValueError("Actual database recreation is only implemented for PostgreSQL URLs.")

    return str(url.set(database="postgres"))


def recreate_database(db_url: str) -> None:
    """
    Drop and recreate a PostgreSQL database.
    """
    check_production_safety(destructive=True)
    
    target_db_name = _get_database_name(db_url)
    admin_uri = _build_postgres_admin_uri(db_url)
    target_identifier = _quote_identifier(target_db_name)

    logger.info(f"Dropping and recreating PostgreSQL database: {target_db_name}")

    admin_engine = create_engine(
        admin_uri,
        isolation_level="AUTOCOMMIT",
        future=True,
    )

    try:
        with admin_engine.connect() as conn:
            conn.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :database_name
                      AND pid <> pg_backend_pid()
                    """
                ),
                {"database_name": target_db_name},
            )
            conn.execute(text(f"DROP DATABASE IF EXISTS {target_identifier}"))
            conn.execute(text(f"CREATE DATABASE {target_identifier}"))
    finally:
        admin_engine.dispose()


def create_new_database(db_name: str, base_url: str = DATABASE_URL) -> None:
    """
    Ensure a tenant database (or schema) exists.

    Strategy
    --------
    1. **Self-hosted / local Postgres** — attempt ``CREATE DATABASE``.
       This is the preferred isolation model (one DB per tenant).
    2. **Managed Postgres** (Render, Railway, Supabase, etc.) — the user
       account typically lacks ``CREATEDB`` privileges.  When a
       ``CREATE DATABASE`` fails with an authentication or privilege error
       we fall back to creating a *schema* inside the master database
       instead.  The tenant's ``db_connection_string`` already carries the
       correct host/credentials, so only the ``search_path`` differs at
       query time.

    The caller (``TenantService.approve_tenant``) does not need to change
    because ``run_tenant_initialization`` connects via the tenant's stored
    URL; the tables will land in whatever database/schema exists.
    """
    check_production_safety(destructive=False)

    logger.info("Ensuring tenant database / schema exists: %s", db_name)

    # ── Attempt 1: CREATE DATABASE (works on self-hosted Postgres) ───────────
    try:
        admin_uri = _build_postgres_admin_uri(base_url)
        target_identifier = _quote_identifier(db_name)
        admin_engine = create_engine(
            admin_uri,
            isolation_level="AUTOCOMMIT",
            future=True,
        )
        try:
            with admin_engine.connect() as conn:
                result = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                    {"db_name": db_name},
                ).first()
                if not result:
                    conn.execute(text(f"CREATE DATABASE {target_identifier}"))
                    logger.info("Database '%s' created successfully.", db_name)
                else:
                    logger.info("Database '%s' already exists.", db_name)
            return  # success — nothing more to do
        finally:
            admin_engine.dispose()

    except Exception as create_err:
        # Detect privilege / auth failures that indicate managed hosting.
        err_msg = str(create_err).lower()
        is_privilege_error = any(
            kw in err_msg
            for kw in (
                "must be superuser",
                "permission denied",
                "insufficient privilege",
                "password authentication failed",
                "pg_hba.conf",
                "createdb",
            )
        )
        if not is_privilege_error:
            # Unexpected error — propagate so the caller surfaces it.
            raise

        logger.warning(
            "CREATE DATABASE not permitted (%s). "
            "Falling back to schema-per-tenant inside the master database.",
            type(create_err).__name__,
        )

    # ── Attempt 2: CREATE SCHEMA (managed Postgres fallback) ─────────────────
    # Use the master DB connection (base_url) directly — we are already on it.
    schema_name = _quote_identifier(db_name)
    fallback_engine = create_engine(base_url, future=True)
    try:
        with fallback_engine.connect() as conn:
            conn.execute(
                text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            )
            conn.commit()
        logger.info(
            "Schema '%s' created inside the master database (managed-PG mode).",
            db_name,
        )
    except Exception as schema_err:
        logger.error("Schema fallback also failed: %s", schema_err)
        raise
    finally:
        fallback_engine.dispose()



# =============================================================================
# Seed helpers
# =============================================================================

def seed_roles(db: Session) -> None:
    """
    Seed default system roles.
    """
    for item in ROLE_SEEDS:
        existing = db.query(Role).filter(Role.code == item["code"]).first()
        if existing:
            continue

        db.add(
            Role(
                name=item["name"],
                code=item["code"],
                description=item["description"],
            )
        )

    db.flush()


def seed_permissions(db: Session) -> None:
    """
    Seed default permissions.
    """
    for item in PERMISSION_SEEDS:
        existing = db.query(Permission).filter(Permission.code == item["code"]).first()
        if existing:
            continue

        db.add(
            Permission(
                name=item["name"],
                code=item["code"],
                module=item["module"],
                description=item["description"],
            )
        )

    db.flush()


def seed_role_permissions(db: Session) -> None:
    """
    Seed default role-permission relationships.
    """
    roles = {role.code: role for role in db.query(Role).all()}
    permissions = {perm.code: perm for perm in db.query(Permission).all()}

    for role_code, permission_codes in ROLE_PERMISSION_MAP.items():
        role = roles.get(role_code)
        if not role:
            continue

        for permission_code in permission_codes:
            permission = permissions.get(permission_code)
            if not permission:
                continue

            existing = (
                db.query(RolePermissionAssociation)
                .filter(
                    RolePermissionAssociation.role_id == role.id,
                    RolePermissionAssociation.permission_id == permission.id,
                )
                .first()
            )
            if existing:
                continue

            db.add(
                RolePermissionAssociation(
                    role_id=role.id,
                    permission_id=permission.id,
                )
            )

    db.flush()


def seed_departments(db: Session) -> None:
    """
    Seed default departments.
    """
    for item in DEPARTMENT_SEEDS:
        existing = db.query(Department).filter(Department.code == item["code"]).first()
        if existing:
            continue

        db.add(
            Department(
                name=item["name"],
                code=item["code"],
                description=item["description"],
            )
        )

    db.flush()


def seed_plans(db: Session) -> None:
    """
    Seed default subscription plans.

    Each plan supplies the limits (users / branches / storage) and the
    has_* feature flags that gate modules. Missing flags default to ``False``
    so we can add new modules without breaking older seed data.
    """
    bool_features = (
        "has_clinical",
        "has_inpatient",
        "has_laboratory",
        "has_pharmacy",
        "has_inventory",
        "has_billing",
        "has_reporting",
        "has_appointments",
        "has_patient_portal",
        "has_insurance",
        "has_radiology",
        "has_surgical",
        "has_hr",
    )

    for item in PLAN_SEEDS:
        existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == item["code"]).first()
        kwargs = {
            "name": item["name"],
            "code": item["code"],
            "description": item["description"],
            "price": item["price"],
            "currency": item.get("currency", "NGN"),
            "interval": item.get("interval", SubscriptionInterval.MONTHLY),
            "trial_days": item.get("trial_days", 0),
            "max_facilities": item["max_facilities"],
            "max_branches": item.get("max_branches", item["max_facilities"]),
            "max_users": item["max_users"],
            "max_patients": item.get("max_patients"),
            "storage_limit_bytes": item.get("storage_limit_bytes"),
        }
        for flag in bool_features:
            kwargs[flag] = item.get(flag, False)

        if existing:
            for k, v in kwargs.items():
                # Don't overwrite display name/code on update.
                if k in {"name", "code"}:
                    continue
                setattr(existing, k, v)
        else:
            db.add(SubscriptionPlan(**kwargs))

    db.flush()


# def _resolve_service_point_type(value: str) -> ServicePointType:
#     """
#     Resolve service point type string against the ServicePointType enum.
#     """
#     try:
#         return ServicePointType[value]
#     except Exception:
#         for member in ServicePointType:
#             if str(member.value).upper() == value.upper():
#                 return member
#         raise ValueError(f"Unsupported ServicePointType value: {value}")

def _resolve_service_point_type(value: str) -> ServicePointType:
    """
    Resolve a string value to the ServicePointType enum.

    Supports both enum member names and enum values.
    """
    normalized = value.strip().upper()

    try:
        return ServicePointType[normalized]
    except KeyError:
        for member in ServicePointType:
            if str(member.value).strip().upper() == normalized:
                return member

    allowed = ", ".join(member.name for member in ServicePointType)
    raise ValueError(
        f"Unsupported ServicePointType value: {value}. Allowed values: {allowed}"
    )


def seed_service_delivery_points(db: Session) -> None:
    """
    Seed default service delivery points.
    """
    departments = {dept.code: dept for dept in db.query(Department).all()}

    for item in SERVICE_DELIVERY_POINT_SEEDS:
        existing = (
            db.query(ServiceDeliveryPoint)
            .filter(ServiceDeliveryPoint.code == item["code"])
            .first()
        )
        if existing:
            continue

        department = departments.get(item["department_code"])
        if not department:
            continue

        db.add(
            ServiceDeliveryPoint(
                name=item["name"],
                code=item["code"],
                service_point_type=_resolve_service_point_type(item["service_point_type"]),
                department_id=department.id,
                location_description=item.get("location_description"),
                queue_prefix=item.get("queue_prefix"),
                supports_appointments=item.get("supports_appointments", False),
                supports_walk_in=item.get("supports_walk_in", True),
            )
        )

    db.flush()


def ensure_user_role_link(db: Session, user: User, role: Role) -> None:
    """
    Ensure the user-role link exists in UserRoleAssociation.
    """
    existing = (
        db.query(UserRoleAssociation)
        .filter(
            UserRoleAssociation.user_id == user.id,
            UserRoleAssociation.role_id == role.id,
        )
        .first()
    )
    if existing:
        return

    db.add(UserRoleAssociation(user_id=user.id, role_id=role.id))
    db.flush()


def seed_default_admin_user(
    db: Session,
    *,
    email: str = "nelson.attah@live.com",
    username: str = "superadmin",
    phone_number: str | None = None,
    password: str = "Admin12345",
    create_staff_profile: bool = True,
) -> None:
    """
    Seed a default administrator user if one does not already exist.

    Change the default password immediately after first login in real use.
    """
    admin_role = db.query(Role).filter(Role.code == "TENANT_ADMIN").first()
    if not admin_role:
        raise ValueError("TENANT_ADMIN role must exist before seeding the default admin user.")

    existing = (
        db.query(User)
        .filter(
            or_(
                User.email == email,
                User.username == username,
            )
        )
        .first()
    )

    if existing:
        ensure_user_role_link(db, existing, admin_role)
        return

    admin_user = User(
        first_name="System",
        last_name="Administrator",
        middle_name=None,
        email=email,
        username=username,
        phone_number=phone_number,
        password_hash=get_password_hash(password),
        status=UserStatus.ACTIVE,
        is_superuser=True,
        is_email_verified=True,
        is_phone_verified=False,
        is_two_factor_enabled=False,
    )

    db.add(admin_user)
    db.flush()

    ensure_user_role_link(db, admin_user, admin_role)

    if create_staff_profile and not admin_user.staff_profile:
        admin_department = db.query(Department).filter(Department.code == "ADMIN").first()
        admin_service_point = db.query(ServiceDeliveryPoint).filter(ServiceDeliveryPoint.code == "REG").first()

        db.add(
            StaffProfile(
                user_id=admin_user.id,
                department_id=admin_department.id if admin_department else None,
                service_delivery_point_id=admin_service_point.id if admin_service_point else None,
                staff_no="STAFF-ADMIN-0001",
                job_title="System Administrator",
                professional_license_no=None,
                specialty="Administration",
            )
        )
        db.flush()

def seed_saas_admin(db: Session) -> None:
    """
    Seed a default SaaS Admin in the Master Database if none exists.
    """
    admin_exists = db.query(SaaSAdmin).first()
    if not admin_exists:
        logger.info("Seeding default SaaS Admin...")
        default_admin = SaaSAdmin(
            first_name="Super",
            last_name="Admin",
            email="superadmin@carepointhms.com",
            password_hash=get_password_hash("SuperAdmin123!"),
            status=UserStatus.ACTIVE,
            is_superuser=True,
        )
        db.add(default_admin)
        db.flush()
        logger.info("Default SaaS Admin seeded successfully.")


def backfill_missing_user_role_links(db: Session) -> None:
    """
    Backfill missing user-role links for superusers/admin users based on simple rules.

    Since the current User model does not store a direct role_id, this helper
    infers missing TENANT_ADMIN links for superusers.
    """
    super_admin_role = db.query(Role).filter(Role.code == "TENANT_ADMIN").first()
    admin_role = db.query(Role).filter(Role.code == "ADMIN").first()

    users = db.query(User).all()
    for user in users:
        if user.is_superuser and super_admin_role:
            ensure_user_role_link(db, user, super_admin_role)
        elif admin_role and user.username and user.username.lower() == "admin":
            ensure_user_role_link(db, user, admin_role)

    db.flush()


def seed_all(db: Session, *, create_default_admin: bool = True) -> None:
    """
    Run all seed steps in the correct order.
    """
    seed_roles(db)
    seed_permissions(db)
    seed_role_permissions(db)
    seed_departments(db)
    seed_service_delivery_points(db)
    backfill_missing_user_role_links(db)

    if create_default_admin:
        seed_default_admin_user(db)


# =============================================================================
# Initialization orchestration
# =============================================================================

def run_master_initialization(
    recreate: bool = True,
    *,
    physical_recreate: bool = False,
) -> None:
    """
    Initialise the shared/master database.

    Reset modes
    -----------
    ``recreate=True`` (default) performs a **schema-level reset**:
    ``DROP SCHEMA public CASCADE; CREATE SCHEMA public;`` is executed on
    the master DB, then ``MasterBase.metadata.create_all`` rebuilds the
    16 master tables from scratch and the seed pass writes default
    subscription plans + the default SaaS admin
    (``superadmin@carepointhms.com`` / ``SuperAdmin123!``). This works
    on any PostgreSQL deployment because it only needs ownership of the
    ``public`` schema — it does NOT need superuser. Use this on managed
    Postgres providers (Render, RDS, Cloud SQL, Neon, Supabase, ...) and
    locally.

    ``physical_recreate=True`` performs a **database-level reset**:
    connects to the ``postgres`` admin DB, terminates active sessions,
    and issues ``DROP DATABASE`` / ``CREATE DATABASE``. This requires
    superuser-equivalent privileges and is typically NOT available on
    managed Postgres. Reach for it only on bare-metal local Postgres.

    Pass both flags False (e.g. ``--no-recreate-master``) to skip the
    destructive reset entirely; ``sync_master_schema`` will still run
    as an idempotent forward-migrate that preserves existing rows.
    """
    check_production_safety(destructive=recreate or physical_recreate)

    if not MASTER_DATABASE_URL:
        logger.warning("MASTER_DATABASE_URL not set. Skipping master DB initialization.")
        return

    # Database-level reset (rare; needs superuser).
    if physical_recreate:
        try:
            recreate_database(MASTER_DATABASE_URL)
        except Exception as exc:
            logger.error(
                "Physical database recreate failed: %s. On managed Postgres "
                "(Render, RDS, Cloud SQL, ...) the application user is "
                "usually not allowed to DROP/CREATE DATABASE. Re-run with "
                "--recreate-master (schema-level reset) or "
                "--no-recreate-master (forward-migrate only) instead.",
                exc,
            )
            raise

    logger.info(f"Initializing Master Database: {MASTER_DATABASE_URL}")
    master_engine = create_engine(MASTER_DATABASE_URL, future=True)

    try:
        # Schema-level reset (default destructive mode). Skipped when
        # we just did a physical recreate (the database is already
        # empty), and skipped entirely when the operator passed
        # --no-recreate-master.
        if recreate and not physical_recreate:
            logger.info(
                "Resetting master schema (DROP SCHEMA public CASCADE; "
                "CREATE SCHEMA public)..."
            )
            try:
                drop_tables(bind_engine=master_engine, is_master=True)
            except Exception as exc:
                logger.error(
                    "Schema-level reset failed: %s. The database user "
                    "must own the 'public' schema. If this database is "
                    "shared and you cannot drop the schema, re-run with "
                    "--no-recreate-master to do an idempotent forward-"
                    "migrate that preserves existing rows.",
                    exc,
                )
                raise

        # Forward-migrate the master schema:
        #   - create any new tables / new enum types,
        #   - add any model columns missing from existing tables,
        #   - extend any pre-existing enums with new values.
        # After a destructive reset above, this is what actually creates
        # the 16 master tables. Without a reset it just adds anything
        # that's missing and is idempotent.
        try:
            from app.db_sync import sync_master_schema

            summary = sync_master_schema(engine=master_engine)
            if summary:
                logger.info("Master schema sync applied: %s", summary)
        except Exception as exc:
            logger.exception("Master schema sync failed: %s", exc)
            raise

        # Seed plans and SaaS Admin. Both seeders are idempotent — they
        # short-circuit when the row already exists, so the same call
        # is safe on a fresh DB and on an existing one.
        with Session(master_engine) as db:
            seed_plans(db)
            seed_saas_admin(db)
            db.commit()
    finally:
        master_engine.dispose()

    logger.info("Master Database initialized and seeded.")


def run_tenant_initialization(
    db_url: str,
    *,
    create_default_admin: bool = True,
) -> None:
    """
    Initialize a specific tenant's database.

    Idempotent: the schema-sync step adds any missing columns and tables
    so this function can be re-run on existing tenant databases without
    losing data.
    """
    check_production_safety(destructive=False)

    logger.info(f"Initializing Tenant Database: {db_url}")

    # Forward-migrate the tenant schema before doing any other work so
    # subsequent ORM queries (e.g. seed lookups) see the new columns.
    try:
        from app.db_sync import sync_tenant_schema

        summary = sync_tenant_schema(db_url)
        if summary:
            logger.info("Tenant schema sync applied: %s", summary)
    except Exception as exc:
        logger.exception("Tenant schema sync failed for %s: %s", db_url, exc)
        raise

    tenant_engine = create_engine(db_url, future=True)

    # Create all tables in tenant DB (Tenant metadata)
    create_tables(bind_engine=tenant_engine, is_master=False)
    
    # Seed tenant data
    with Session(tenant_engine) as db:
        seed_all(db, create_default_admin=create_default_admin)
        db.commit()
    
    logger.info("Tenant Database initialized and seeded.")


def run_initialization(
    *,
    recreate_master_database: bool = True,
    physical_recreate_master_database: bool = False,
    init_master: bool = True,
    # The flags below are kept for backwards-compat with shell scripts /
    # CI jobs that pass them; they are no-ops now and ignored with a
    # warning *only when explicitly set*. Tenant tables NEVER live in
    # the central database.
    recreate_entire_database: bool = False,
    drop_and_recreate_all_tables: bool = False,
    create_default_admin: bool = False,
) -> None:
    """
    Run the default ``python -m app.init_db`` flow.

    Multi-tenancy contract
    ----------------------
    Carepoint HMS is strictly multi-tenant. Two kinds of databases exist:

    * the **central / master DB** (``MASTER_DATABASE_URL``) holds only
      :class:`~app.models.base.MasterTable` rows — Tenant, TenantDomain,
      SubscriptionPlan, TenantSubscription, SaaSAdmin, etc.
    * each **tenant DB** holds every :class:`~app.models.base.TenantTable`
      row for that tenant. There is no "default" or "shared" tenant DB.

    Accordingly, this entry point now initialises only the master
    database. Tenant tables are created inside their own per-tenant
    database via either the API tenant-registration flow or the
    ``--provision-tenant`` / ``--init-tenant`` CLI options.

    Default behaviour
    -----------------
    With no flags, ``python -m app.init_db`` performs a **schema-level**
    destructive master reset that works on any PostgreSQL deployment
    (including managed Postgres on Render / RDS / Cloud SQL / Neon /
    Supabase, where the application user lacks superuser):

      1. ``DROP SCHEMA public CASCADE; CREATE SCHEMA public;`` against
         the master DB at ``MASTER_DATABASE_URL`` (e.g.
         ``carepoint_hms_master``).
      2. ``MasterBase.metadata.create_all`` rebuilds the 16 master
         tables.
      3. Seed the default subscription plans.
      4. Seed the default SaaS Admin
         (``superadmin@carepointhms.com`` / ``SuperAdmin123!``) when no
         SaaS admin row exists.

    Tenant tables are NEVER touched here. A tenant database is
    provisioned automatically when ``TenantService.approve_registration``
    runs at registration approval time; the script's
    ``--init-tenant <url>`` and ``--provision-tenant <code>`` flags
    exist only as edge-case escape hatches.

    Variants
    --------
    * ``--no-recreate-master`` — preserve existing rows, run only
      ``sync_master_schema`` to forward-migrate (add new tables /
      columns / enum values).
    * ``--recreate-master-database`` — ALSO drop and recreate the
      physical PostgreSQL database (``DROP DATABASE`` / ``CREATE
      DATABASE``). Requires superuser-equivalent privileges; not
      available on most managed Postgres.

    The destructive path is blocked automatically when
    ``settings.ENVIRONMENT == "production"`` via
    :func:`check_production_safety`.

    Backwards-compat
    ----------------
    The old ``recreate_entire_database`` / ``drop_and_recreate_all_tables``
    / ``create_default_admin`` arguments used to drop ``DATABASE_URL`` and
    spray all 230+ tenant tables into it. That was wrong for a strict
    per-tenant-DB layout. They are accepted here for call-site
    compatibility but ignored with a warning.
    """
    # Surface the old flags so anyone with stale wrapper scripts learns
    # immediately that the behaviour changed. Only fire when the
    # operator explicitly passed at least one of them — the dispatcher
    # below no longer auto-forwards anything, so a bare invocation
    # never trips this warning.
    if recreate_entire_database or drop_and_recreate_all_tables or create_default_admin:
        logger.warning(
            "init_db: ignoring legacy flags (recreate_entire_database=%s, "
            "drop_and_recreate_all_tables=%s, create_default_admin=%s). "
            "Tenant tables only live in tenant databases — they are "
            "auto-provisioned at tenant-registration approval. Use "
            "--init-tenant <url> or --provision-tenant <code> only as an "
            "escape hatch.",
            recreate_entire_database,
            drop_and_recreate_all_tables,
            create_default_admin,
        )

    if init_master:
        run_master_initialization(
            recreate=recreate_master_database,
            physical_recreate=physical_recreate_master_database,
        )
    else:
        logger.info("init_master=False — skipping master DB initialization.")

    logger.info(
        "Master DB initialization complete. Tenant databases are "
        "provisioned automatically when TenantService.approve_registration "
        "runs at registration approval time."
    )


# =============================================================================
# CLI entry point
# =============================================================================

def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for database reset/initialization.
    """
    parser = argparse.ArgumentParser(
        description="Reset, initialize, and seed the Carepoint HMS database."
    )
    # ``--recreate-db`` and ``--recreate-master`` default to TRUE so a bare
    # ``python -m app.init_db`` performs the canonical "wipe everything,
    # recreate, and reseed" reset most operators expect. Use the matching
    # ``--no-recreate-*`` flags to opt out (e.g. when running on a long-
    # lived dev DB that already has data you want to preserve).
    # Legacy flags kept for backwards-compat. The default flow no longer
    # touches DATABASE_URL — tenant tables only live in tenant DBs.
    parser.add_argument(
        "--recreate-db",
        dest="recreate_db",
        action="store_true",
        default=False,
        help=(
            "(Legacy / no-op) Used to drop the operational DATABASE_URL "
            "DB. Tenant tables now only live in tenant DBs; ignored."
        ),
    )
    parser.add_argument(
        "--no-recreate-db",
        dest="recreate_db",
        action="store_false",
        help="(Legacy / no-op) Ignored.",
    )
    parser.add_argument(
        "--recreate-master",
        dest="recreate_master",
        action="store_true",
        default=True,
        help=(
            "Schema-level reset of the master DB (default): "
            "DROP SCHEMA public CASCADE; CREATE SCHEMA public; followed "
            "by MasterBase.metadata.create_all and re-seed of "
            "subscription plans + the default SaaS admin "
            "(superadmin@carepointhms.com / SuperAdmin123!). Works on "
            "managed Postgres because it does not need superuser. "
            "Blocked in production by check_production_safety."
        ),
    )
    parser.add_argument(
        "--no-recreate-master",
        dest="recreate_master",
        action="store_false",
        help=(
            "Skip the destructive reset. Falls back to an idempotent "
            "forward-migrate via sync_master_schema; existing rows "
            "(including any SaaS admins) are preserved."
        ),
    )
    parser.add_argument(
        "--recreate-master-database",
        dest="recreate_master_database",
        action="store_true",
        default=False,
        help=(
            "ALSO drop and recreate the master database at the "
            "PostgreSQL level (DROP DATABASE / CREATE DATABASE). "
            "Requires superuser-equivalent privileges; usually NOT "
            "available on managed Postgres (Render/RDS/Cloud SQL/Neon/"
            "Supabase). Reach for this only on bare-metal local PG."
        ),
    )
    parser.add_argument(
        "--init-tenant",
        dest="init_tenant",
        type=str,
        help=(
            "Initialise a single tenant database at the given SQLAlchemy "
            "URL: forward-migrates the tenant schema, creates any missing "
            "TenantTable tables, and seeds default roles/permissions/"
            "departments/admin. Use this for dev tenants whose DB you "
            "created out of band; for end-to-end tenant registration use "
            "--provision-tenant instead."
        ),
    )
    parser.add_argument(
        "--keep-existing-tables",
        action="store_true",
        help="Do not drop existing tables before create_all().",
    )
    parser.add_argument(
        "--no-admin",
        action="store_true",
        help="Do not create the default admin user.",
    )
    parser.add_argument(
        "--init-master-only",
        action="store_true",
        help="Only initialize the shared master database (plans, tenants metadata).",
    )
    parser.add_argument(
        "--no-master",
        action="store_true",
        help="Do not initialize the master database.",
    )
    parser.add_argument(
        "--provision-tenant",
        type=str,
        help="Provision a new tenant with the specified code.",
    )
    parser.add_argument(
        "--tenant-name",
        type=str,
        help="Name for the new tenant being provisioned.",
    )
    parser.add_argument(
        "--tenant-domain",
        type=str,
        help="Primary domain for the new tenant.",
    )
    parser.add_argument(
        "--sync-master",
        action="store_true",
        help=(
            "Forward-migrate the existing master database schema only — add "
            "any missing columns / new tables / new enum values without "
            "dropping data. Skips seeding."
        ),
    )
    parser.add_argument(
        "--sync-tenants",
        action="store_true",
        help=(
            "Forward-migrate every active tenant's database schema (no "
            "data loss). Equivalent to --sync-master but iterates each "
            "registered tenant."
        ),
    )
    parser.add_argument(
        "--heal-missing-tenant-dbs",
        action="store_true",
        help=(
            "Probe every is_provisioned=True tenant's physical database "
            "and demote any whose database has gone missing (so subsequent "
            "sync ticks skip them cleanly until re-approved)."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    try:
        if args.heal_missing_tenant_dbs:
            from app.db_sync import heal_stale_tenants

            results = heal_stale_tenants()
            if not results:
                logger.info("No tenants to heal.")
            for code, outcome in results.items():
                logger.info("Tenant %s: %s", code, outcome)
            demoted = sum(1 for v in results.values() if v == "demoted")
            ok = sum(1 for v in results.values() if v == "ok")
            logger.info(
                "Heal sweep complete: %s ok / %s demoted / %s total",
                ok, demoted, len(results),
            )

        elif args.sync_master:
            from app.db_sync import sync_master_schema

            summary = sync_master_schema()
            if summary:
                logger.info("Master schema sync applied: %s", summary)
            else:
                logger.info("Master schema is already up to date.")

        elif args.sync_tenants:
            from app.db_sync import sync_tenant_schemas_all

            results = sync_tenant_schemas_all()
            ok = sum(1 for v in results.values() if isinstance(v, dict))
            failed = sum(1 for v in results.values() if isinstance(v, str) and v.startswith("error"))
            for code, summary in results.items():
                if isinstance(summary, dict) and summary:
                    logger.info("Tenant %s schema sync: %s", code, summary)
                elif isinstance(summary, str):
                    logger.warning("Tenant %s sync: %s", code, summary)
            logger.info(
                "Tenant schema sync complete: %s ok / %s failed / %s total",
                ok, failed, len(results),
            )

        elif args.provision_tenant:
            if not args.tenant_name or not args.tenant_domain:
                logger.error("Provisioning a tenant requires --tenant-name and --tenant-domain.")
                exit(1)

            # This logic would ideally be in a service, but for CLI convenience:
            from app.services.tenant_service import TenantService
            from app.schemas.tenant_schemas import TenantRegistrationSchema

            with Session(create_engine(MASTER_DATABASE_URL)) as master_db:
                service = TenantService(master_db)
                payload = TenantRegistrationSchema(
                    tenant_name=args.tenant_name,
                    tenant_code=args.provision_tenant,
                    domain_url=args.tenant_domain,
                    plan_code="BASIC",  # Default plan
                    admin_email=f"admin@{args.tenant_domain}",
                    admin_username="admin",
                    admin_password="Password123!",
                    admin_first_name="Tenant",
                    admin_last_name="Admin",
                )
                service.register_tenant(payload)
                logger.info(f"Tenant {args.provision_tenant} provisioned successfully.")

        elif args.init_master_only:
            run_master_initialization(
                recreate=args.recreate_master,
                physical_recreate=args.recreate_master_database,
            )

        elif args.init_tenant:
            # Initialise a single tenant DB at the given URL. The
            # ``run_tenant_initialization`` helper runs ``sync_tenant_schema``
            # (idempotent forward-migration) followed by
            # ``create_tables(is_master=False)`` against that engine,
            # then seeds the standard tenant defaults.
            run_tenant_initialization(
                args.init_tenant,
                create_default_admin=not args.no_admin,
            )

        else:
            # Only forward the legacy flags when the operator explicitly
            # passed them; this keeps a bare ``python -m app.init_db``
            # invocation quiet. ``--recreate-db`` is the only one that
            # carries a clear "I asked for it" signal (default False).
            # ``--keep-existing-tables`` and ``--no-admin`` are no-ops
            # now and intentionally not forwarded so the warning fires
            # only when somebody actually typed --recreate-db.
            run_initialization(
                recreate_master_database=args.recreate_master,
                physical_recreate_master_database=args.recreate_master_database,
                init_master=not args.no_master,
                recreate_entire_database=args.recreate_db,
            )
    except SQLAlchemyError as exc:
        logger.error(f"Database operation failed: {exc}")
        raise
    except Exception as exc:
        logger.error(f"Initialization failed: {exc}")
        raise


"""
Usage
-----

Default — schema-level master reset that works on any PostgreSQL,
including managed providers (Render / RDS / Cloud SQL / Neon /
Supabase). DROP SCHEMA public CASCADE on the master DB, then
MasterBase.metadata.create_all + seed plans + seed the default SaaS
admin (superadmin@carepointhms.com / SuperAdmin123!):
    python -m app.init_db

Idempotent forward-migrate only (preserve existing rows, no drop):
    python -m app.init_db --no-recreate-master

Database-level reset of the master DB (DROP DATABASE / CREATE DATABASE).
Requires superuser; not available on most managed Postgres. Stack with
--recreate-master to also wipe the schema afterwards (default already
enabled), or pair with --no-recreate-master if you only want the
physical recreate:
    python -m app.init_db --recreate-master-database

Forward-migrate every active tenant DB (no data loss). Tenant DBs are
auto-created at registration approval, but this is useful after a
deploy that adds new TenantTable columns:
    python -m app.init_db --sync-tenants

Tenant escape hatches (rare). Tenant DBs are normally provisioned
automatically when TenantService.approve_registration runs at
registration approval time. Use these only for out-of-band scenarios:

    # Apply tenant schema + seeds to a DB URL you created out of band:
    python -m app.init_db --init-tenant \
        postgresql+psycopg2://postgres:Admin123@localhost:5432/carepoint_hms_acme

    # End-to-end registration via TenantService (writes master row,
    # provisions the tenant DB, seeds defaults):
    python -m app.init_db --provision-tenant ACME \
        --tenant-name "Acme Hospital" \
        --tenant-domain acme.example.com

NOT supported anymore: dumping every TenantTable into the central
DATABASE_URL DB. In Carepoint HMS, tenant tables live only in
per-tenant databases.
"""