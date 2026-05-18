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
    {"code": "TENANT_ADMIN", "name": "Tenant Administrator", "description": "Full system access."},
    {"code": "ADMIN", "name": "Administrator", "description": "General administrative access."},
    {"code": "DOCTOR", "name": "Doctor", "description": "Full clinical access."},
    {"code": "NURSE", "name": "Nurse", "description": "Nursing and triage access."},
    {"code": "CLINICIAN", "name": "Clinician", "description": "General clinical access."},
    {"code": "LAB_SCIENTIST", "name": "Laboratory Scientist", "description": "Lab management and verification."},
    {"code": "LAB_TECHNICIAN", "name": "Laboratory Technician", "description": "Lab test performance."},
    {"code": "PHARMACIST", "name": "Pharmacist", "description": "Pharmacy and stock management."},
    {"code": "BILLING_OFFICER", "name": "Billing Officer", "description": "Billing and invoice management."},
    {"code": "CASHIER", "name": "Cashier", "description": "Payment collection."},
    {"code": "RECEPTIONIST", "name": "Receptionist", "description": "Registration and appointments."},
    {"code": "HR_MANAGER", "name": "HR Manager", "description": "Workforce management."},
    {"code": "HR_OFFICER", "name": "HR Officer", "description": "HR administrative support."},
    {"code": "RADIOLOGIST", "name": "Radiologist", "description": "Radiology reporting."},
    {"code": "RADIOGRAPHER", "name": "Radiographer", "description": "Radiology imaging."},
    {"code": "SURGEON", "name": "Surgeon", "description": "Surgical procedures."},
    {"code": "ANAESTHETIST", "name": "Anaesthetist", "description": "Anaesthesia management."},
    {"code": "THEATRE_NURSE", "name": "Theatre Nurse", "description": "Surgical support."},
    {"code": "INSURANCE_OFFICER", "name": "Insurance Officer", "description": "Claims management."},
    {"code": "INSURANCE_REVIEWER", "name": "Insurance Reviewer", "description": "Claims adjudication."},
    {"code": "PATIENT", "name": "Patient", "description": "Patient portal access."},
]

PERMISSION_SEEDS: list[dict[str, Any]] = [
    # User & Access Control
    {"code": "USER_READ", "name": "Read users", "module": "USER"},
    {"code": "USER_CREATE", "name": "Create users", "module": "USER"},
    {"code": "USER_UPDATE", "name": "Update users", "module": "USER"},
    {"code": "USER_DELETE", "name": "Delete users", "module": "USER"},
    {"code": "USER_MANAGE_STATUS", "name": "Manage user status", "module": "USER"},
    {"code": "USER_MANAGE_ROLES", "name": "Assign / revoke user roles", "module": "USER"},
    {"code": "USER_FORCE_PASSWORD_RESET", "name": "Force password reset", "module": "USER"},
    {"code": "ROLE_READ", "name": "Read roles", "module": "ROLE"},
    {"code": "ROLE_CREATE", "name": "Create roles", "module": "ROLE"},
    {"code": "ROLE_UPDATE", "name": "Update roles", "module": "ROLE"},
    {"code": "ROLE_DELETE", "name": "Delete roles", "module": "ROLE"},
    {"code": "ROLE_ASSIGN_PERMISSIONS", "name": "Assign permissions to roles", "module": "ROLE"},
    {"code": "PERMISSION_READ", "name": "Read permissions", "module": "PERMISSION"},
    {"code": "PERMISSION_MANAGE", "name": "Manage permission catalog", "module": "PERMISSION"},
    {"code": "TWO_FACTOR_ADMIN", "name": "Administer 2FA challenges", "module": "TWO_FACTOR"},

    # Patient
    {"code": "PATIENT_READ", "name": "Read patients", "module": "PATIENT"},
    {"code": "PATIENT_CREATE", "name": "Register patients", "module": "PATIENT"},
    {"code": "PATIENT_UPDATE", "name": "Update patient records", "module": "PATIENT"},
    {"code": "PATIENT_DELETE", "name": "Deactivate patients", "module": "PATIENT"},
    {"code": "PATIENT_CARD_VIEW", "name": "View patient membership cards and wallet history", "module": "PATIENT"},
    {"code": "PATIENT_CARD_CREATE", "name": "Issue new membership cards", "module": "PATIENT"},
    {"code": "PATIENT_CARD_UPDATE", "name": "Update membership card status", "module": "PATIENT"},
    {"code": "PATIENT_CARD_FUND", "name": "Credit membership card wallets", "module": "PATIENT"},
    {"code": "PATIENT_CARD_DEBIT", "name": "Debit membership card wallets", "module": "PATIENT"},

    # Appointment
    {"code": "APPOINTMENT_READ", "name": "Read appointments", "module": "APPOINTMENT"},
    {"code": "APPOINTMENT_CREATE", "name": "Create appointments", "module": "APPOINTMENT"},
    {"code": "APPOINTMENT_UPDATE", "name": "Update appointments", "module": "APPOINTMENT"},
    {"code": "APPOINTMENT_CANCEL", "name": "Cancel appointments", "module": "APPOINTMENT"},

    # Visit / Queue
    {"code": "VISIT_READ", "name": "Read visits", "module": "VISIT"},
    {"code": "VISIT_INITIATE", "name": "Initiate visits", "module": "VISIT"},
    {"code": "VISIT_ROUTE", "name": "Route visits", "module": "VISIT"},
    {"code": "QUEUE_MANAGE", "name": "Manage queue tickets", "module": "QUEUE"},

    # Clinical
    {"code": "TRIAGE_PERFORM", "name": "Perform triage", "module": "CLINICAL"},
    {"code": "VITAL_SIGN_RECORD", "name": "Record vital signs", "module": "CLINICAL"},
    {"code": "CONSULTATION_READ", "name": "Read consultations", "module": "CLINICAL"},
    {"code": "CONSULTATION_WRITE", "name": "Write consultations", "module": "CLINICAL"},
    {"code": "DIAGNOSIS_WRITE", "name": "Record diagnoses", "module": "CLINICAL"},
    {"code": "PROCEDURE_ORDER", "name": "Order procedures", "module": "CLINICAL"},

    # Lab
    {"code": "LAB_ORDER_CREATE", "name": "Create lab orders", "module": "LAB"},
    {"code": "LAB_RESULT_ENTER", "name": "Enter lab results", "module": "LAB"},
    {"code": "LAB_RESULT_VERIFY", "name": "Verify lab results", "module": "LAB"},
    {"code": "LAB_RESULT_RELEASE", "name": "Release lab results", "module": "LAB"},

    # Pharmacy
    {"code": "PRESCRIPTION_WRITE", "name": "Write prescriptions", "module": "PHARMACY"},
    {"code": "PRESCRIPTION_DISPENSE", "name": "Dispense prescriptions", "module": "PHARMACY"},
    {"code": "PHARMACY_STOCK_MANAGE", "name": "Manage pharmacy stock", "module": "PHARMACY"},

    # Billing / Finance
    {"code": "BILLING_READ", "name": "Read billing", "module": "BILLING"},
    {"code": "BILLING_CREATE", "name": "Create billing", "module": "BILLING"},
    {"code": "INVOICE_ISSUE", "name": "Issue invoices", "module": "BILLING"},
    {"code": "INVOICE_VOID", "name": "Void / cancel invoices", "module": "BILLING"},
    {"code": "PAYMENT_RECEIVE", "name": "Receive payments", "module": "BILLING"},
    {"code": "PAYMENT_REFUND", "name": "Refund payments", "module": "BILLING"},

    # Admission / Ward
    {"code": "ADMISSION_CREATE", "name": "Admit patients", "module": "ADMISSION"},
    {"code": "ADMISSION_DISCHARGE", "name": "Discharge patients", "module": "ADMISSION"},
    {"code": "BED_MANAGE", "name": "Manage beds", "module": "ADMISSION"},
    {"code": "WARD_MANAGE", "name": "Manage wards", "module": "ADMISSION"},

    # Inventory
    {"code": "INVENTORY_READ", "name": "Read inventory", "module": "INVENTORY"},
    {"code": "INVENTORY_MANAGE", "name": "Manage inventory items and stores", "module": "INVENTORY"},
    {"code": "STOCK_MOVEMENT_POST", "name": "Post stock movements", "module": "INVENTORY"},

    # Reports
    {"code": "REPORT_READ", "name": "Read reports", "module": "REPORT"},
    {"code": "REPORT_GENERATE", "name": "Generate complex reports", "module": "REPORT"},

    # Audit
    {"code": "AUDIT_READ", "name": "Read audit trails", "module": "AUDIT"},
    {"code": "SECURITY_EVENT_READ", "name": "Read security events", "module": "AUDIT"},

    # Ambulance & Dispatch
    {"code": "AMBULANCE_READ", "name": "Read ambulance fleet", "module": "AMBULANCE"},
    {"code": "AMBULANCE_MANAGE", "name": "Manage ambulance fleet", "module": "AMBULANCE"},
    {"code": "DISPATCH_READ", "name": "Read ambulance dispatches", "module": "AMBULANCE"},
    {"code": "DISPATCH_MANAGE", "name": "Manage ambulance dispatches", "module": "AMBULANCE"},

    # Notifications & Messaging
    {"code": "NOTIFICATION_READ", "name": "Read notifications", "module": "NOTIFICATION"},
    {"code": "NOTIFICATION_MANAGE", "name": "Manage notification templates", "module": "NOTIFICATION"},
    {"code": "NOTIFICATION_DISPATCH", "name": "Send notifications", "module": "NOTIFICATION"},
    {"code": "MESSAGE_SEND", "name": "Send direct messages", "module": "NOTIFICATION"},

    # Compliance / Governance
    {"code": "COMPLIANCE_READ", "name": "Read compliance records", "module": "COMPLIANCE"},
    {"code": "COMPLIANCE_MANAGE", "name": "Manage compliance records", "module": "COMPLIANCE"},
    {"code": "ACCREDITATION_READ", "name": "Read accreditation records", "module": "COMPLIANCE"},
    {"code": "ACCREDITATION_MANAGE", "name": "Manage accreditation records", "module": "COMPLIANCE"},
    {"code": "INCIDENT_READ", "name": "Read incident reports", "module": "COMPLIANCE"},
    {"code": "INCIDENT_MANAGE", "name": "File incident reports", "module": "COMPLIANCE"},
    {"code": "INFECTION_LOG_READ", "name": "Read infection control logs", "module": "COMPLIANCE"},
    {"code": "INFECTION_LOG_MANAGE", "name": "Manage infection control logs", "module": "COMPLIANCE"},
    {"code": "QUALITY_PROJECT_READ", "name": "Read quality projects", "module": "COMPLIANCE"},
    {"code": "QUALITY_PROJECT_MANAGE", "name": "Manage quality projects", "module": "COMPLIANCE"},
    {"code": "GOVERNANCE_DASHBOARD", "name": "Read governance dashboard", "module": "COMPLIANCE"},

    # Procedures
    {"code": "PROCEDURE_PERFORM", "name": "Perform procedures", "module": "PROCEDURE"},
    {"code": "PROCEDURE_MANAGE", "name": "Manage procedure catalog", "module": "PROCEDURE"},

    # Radiology
    {"code": "RADIOLOGY_ORDER", "name": "Order radiology studies", "module": "RADIOLOGY"},
    {"code": "RADIOLOGY_PERFORM", "name": "Perform radiology exams", "module": "RADIOLOGY"},
    {"code": "RADIOLOGY_REPORT", "name": "Draft radiology reports", "module": "RADIOLOGY"},
    {"code": "RADIOLOGY_RELEASE", "name": "Release radiology reports", "module": "RADIOLOGY"},
    {"code": "RADIOLOGY_MANAGE", "name": "Manage radiology catalog", "module": "RADIOLOGY"},

    # Surgical
    {"code": "SURGICAL_READ", "name": "Read surgical cases", "module": "SURGICAL"},
    {"code": "SURGICAL_BOOK", "name": "Book surgical cases", "module": "SURGICAL"},
    {"code": "SURGICAL_PERFORM", "name": "Drive surgical lifecycle", "module": "SURGICAL"},
    {"code": "SURGICAL_RECORD", "name": "Record surgical notes", "module": "SURGICAL"},
    {"code": "SURGICAL_MANAGE", "name": "Manage surgical catalog", "module": "SURGICAL"},
    {"code": "THEATRE_MANAGE", "name": "Manage operating theatres", "module": "SURGICAL"},
    {"code": "ANAESTHESIA_RECORD", "name": "Record anaesthesia entries", "module": "SURGICAL"},
    {"code": "INSTRUMENT_MANAGE", "name": "Manage surgical instruments", "module": "SURGICAL"},

    # Insurance Claims
    {"code": "CLAIM_READ", "name": "Read insurance claims", "module": "INSURANCE"},
    {"code": "CLAIM_MANAGE", "name": "Manage insurance claims", "module": "INSURANCE"},
    {"code": "CLAIM_REVIEW", "name": "Review insurance claims", "module": "INSURANCE"},

    # Facilities
    {"code": "FACILITY_READ", "name": "Read facility info", "module": "FACILITY"},
    {"code": "FACILITY_CREATE", "name": "Create facilities", "module": "FACILITY"},
    {"code": "FACILITY_UPDATE", "name": "Update facility info", "module": "FACILITY"},
    {"code": "FACILITY_DELETE", "name": "Delete facilities", "module": "FACILITY"},

    # Integrations
    {"code": "INTEGRATION_READ", "name": "Read integration settings", "module": "INTEGRATION"},
    {"code": "INTEGRATION_CREATE", "name": "Create integrations", "module": "INTEGRATION"},
    {"code": "INTEGRATION_UPDATE", "name": "Update integrations", "module": "INTEGRATION"},
    {"code": "INTEGRATION_DELETE", "name": "Delete integrations", "module": "INTEGRATION"},

    # Meals
    {"code": "MEAL_READ", "name": "Read meal info", "module": "MEAL"},
    {"code": "MEAL_MANAGE", "name": "Manage meal catalog", "module": "MEAL"},
    {"code": "MEAL_ORDER", "name": "Order meals", "module": "MEAL"},
    {"code": "MEAL_SERVE", "name": "Serve meals", "module": "MEAL"},

    # Referrals
    {"code": "REFERRAL_READ", "name": "Read referrals", "module": "REFERRAL"},
    {"code": "REFERRAL_CREATE", "name": "Create referrals", "module": "REFERRAL"},
    {"code": "REFERRAL_UPDATE", "name": "Update referrals", "module": "REFERRAL"},
    {"code": "REFERRAL_CANCEL", "name": "Cancel referrals", "module": "REFERRAL"},

    # Templates
    {"code": "TEMPLATE_READ", "name": "Read templates", "module": "TEMPLATE"},
    {"code": "TEMPLATE_CREATE", "name": "Create templates", "module": "TEMPLATE"},

    # Backup & SaaS Admin
    {"code": "BACKUP_READ", "name": "Read backups", "module": "BACKUP"},
    {"code": "BACKUP_CREATE", "name": "Create backups", "module": "BACKUP"},
    {"code": "SETTING_UPDATE", "name": "Update system settings", "module": "SETTING"},
    {"code": "SaaS_ADMIN", "name": "SaaS Administrative Access", "module": "SaaS"},
]

ROLE_PERMISSION_MAP: dict[str, list[str]] = {
    "TENANT_ADMIN": [p["code"] for p in PERMISSION_SEEDS],
    "ADMIN": [
        "USER_READ", "USER_CREATE", "USER_UPDATE", "USER_MANAGE_STATUS", "USER_MANAGE_ROLES",
        "ROLE_READ", "ROLE_CREATE", "ROLE_UPDATE", "ROLE_ASSIGN_PERMISSIONS",
        "PERMISSION_READ", "FACILITY_READ", "FACILITY_CREATE", "FACILITY_UPDATE",
        "BACKUP_READ", "BACKUP_CREATE", "SETTING_UPDATE", "REPORT_READ", "REPORT_GENERATE",
        "TEMPLATE_READ", "TEMPLATE_CREATE", "INTEGRATION_READ", "INTEGRATION_UPDATE",
    ],
    "DOCTOR": [
        "PATIENT_READ", "PATIENT_UPDATE", "VISIT_READ", "VISIT_ROUTE", "CONSULTATION_READ",
        "CONSULTATION_WRITE", "DIAGNOSIS_WRITE", "PRESCRIPTION_WRITE", "LAB_ORDER_CREATE",
        "RADIOLOGY_ORDER", "PROCEDURE_ORDER", "PROCEDURE_PERFORM", "ADMISSION_CREATE",
        "MEAL_READ", "MEAL_ORDER", "REFERRAL_READ", "REFERRAL_CREATE", "REFERRAL_UPDATE",
    ],
    "NURSE": [
        "PATIENT_READ", "VISIT_READ", "VISIT_ROUTE", "TRIAGE_PERFORM", "VITAL_SIGN_RECORD",
        "MEAL_READ", "MEAL_SERVE", "REFERRAL_READ",
    ],
    "CLINICIAN": [
        "PATIENT_READ", "VISIT_READ", "CONSULTATION_READ", "VITAL_SIGN_RECORD", "TRIAGE_PERFORM",
    ],
    "LAB_SCIENTIST": [
        "PATIENT_READ", "VISIT_READ", "LAB_ORDER_CREATE", "LAB_RESULT_ENTER", "LAB_RESULT_VERIFY", "LAB_RESULT_RELEASE",
    ],
    "LAB_TECHNICIAN": [
        "PATIENT_READ", "VISIT_READ", "LAB_RESULT_ENTER",
    ],
    "PHARMACIST": [
        "PATIENT_READ", "VISIT_READ", "PRESCRIPTION_DISPENSE", "PHARMACY_STOCK_MANAGE", "INVENTORY_READ",
    ],
    "BILLING_OFFICER": [
        "PATIENT_READ", "BILLING_READ", "BILLING_CREATE", "INVOICE_ISSUE", "INVOICE_VOID", "PAYMENT_RECEIVE", "PAYMENT_REFUND",
    ],
    "CASHIER": [
        "PATIENT_READ", "BILLING_READ", "PAYMENT_RECEIVE",
    ],
    "RECEPTIONIST": [
        "PATIENT_READ", "PATIENT_CREATE", "PATIENT_UPDATE", "APPOINTMENT_READ", "APPOINTMENT_CREATE",
        "APPOINTMENT_UPDATE", "APPOINTMENT_CANCEL", "VISIT_INITIATE", "QUEUE_MANAGE", "REFERRAL_READ", "REFERRAL_CREATE",
    ],
    "HR_MANAGER": [
        "USER_READ", "USER_CREATE", "USER_UPDATE", "USER_MANAGE_STATUS", "ROLE_READ",
    ],
    "HR_OFFICER": [
        "USER_READ", "ROLE_READ",
    ],
    "RADIOLOGIST": [
        "PATIENT_READ", "VISIT_READ", "RADIOLOGY_ORDER", "RADIOLOGY_PERFORM", "RADIOLOGY_REPORT", "RADIOLOGY_RELEASE",
    ],
    "RADIOGRAPHER": [
        "PATIENT_READ", "VISIT_READ", "RADIOLOGY_PERFORM",
    ],
    "SURGEON": [
        "PATIENT_READ", "VISIT_READ", "SURGICAL_READ", "SURGICAL_BOOK", "SURGICAL_PERFORM", "SURGICAL_RECORD",
    ],
    "ANAESTHETIST": [
        "PATIENT_READ", "SURGICAL_READ", "ANAESTHESIA_RECORD",
    ],
    "THEATRE_NURSE": [
        "PATIENT_READ", "SURGICAL_READ", "INSTRUMENT_MANAGE",
    ],
    "INSURANCE_OFFICER": [
        "PATIENT_READ", "CLAIM_READ", "CLAIM_MANAGE",
    ],
    "INSURANCE_REVIEWER": [
        "PATIENT_READ", "CLAIM_READ", "CLAIM_REVIEW",
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

    return url.set(database="postgres").render_as_string(hide_password=False)


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


def ensure_master_database_exists(db_url: str) -> None:
    """
    Best-effort: make sure the database referenced by ``db_url`` exists.

    Connects to the ``postgres`` maintenance DB on the same host and
    issues ``CREATE DATABASE`` if the target is missing. Used by
    ``run_master_initialization`` so a fresh local Postgres can be
    bootstrapped with a single ``python -m app.init_db`` call without
    the operator having to run ``createdb`` first.

    Silently no-ops on managed Postgres (where the user lacks
    ``CREATEDB``); the caller decides how to surface that.
    """
    target_db_name = _get_database_name(db_url)
    admin_uri = _build_postgres_admin_uri(db_url)
    target_identifier = _quote_identifier(target_db_name)

    admin_engine = create_engine(
        admin_uri,
        isolation_level="AUTOCOMMIT",
        future=True,
        connect_args={"connect_timeout": 10},
    )
    try:
        with admin_engine.connect() as conn:
            existing = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": target_db_name},
            ).first()
            if existing:
                return
            try:
                conn.execute(text(f"CREATE DATABASE {target_identifier}"))
                logger.info("Master database '%s' created.", target_db_name)
            except Exception as create_exc:
                err_msg = str(create_exc).lower()
                # Managed Postgres or insufficient privileges — nothing
                # we can do automatically. Bubble up so the caller logs
                # a single warning instead of a stack trace.
                if any(
                    kw in err_msg
                    for kw in (
                        "must be superuser",
                        "permission denied",
                        "insufficient privilege",
                        "createdb",
                    )
                ):
                    logger.warning(
                        "Cannot auto-create master database '%s' on this "
                        "host — user lacks CREATEDB. Create the database "
                        "out of band before re-running init_db.",
                        target_db_name,
                    )
                    return
                raise
    finally:
        admin_engine.dispose()


def create_new_database(db_name: str, base_url: str = MASTER_DATABASE_URL) -> None:
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

    Connection robustness
    ---------------------
    Both the admin-URI engine and the schema-fallback engine pass an
    explicit ``connect_timeout`` so a misconfigured master URL fails
    fast (5 seconds) instead of hanging the API request thread for the
    full TCP timeout (~75s on Linux). This is what was causing the
    test_tenant_routes test class to appear to "hang" indefinitely.
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
            connect_args={"connect_timeout": 10},
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
    fallback_engine = create_engine(
        base_url,
        future=True,
        connect_args={"connect_timeout": 10},
    )
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
                is_system=True
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
                description=item.get("description", item["name"]),
                is_system=True
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
    # Safety check: Prevent accidental seeding of tenant data into the master DB
    from app.core.database import MASTER_DATABASE_URL
    from sqlalchemy.engine import make_url
    
    bind_url = db.get_bind().url
    if MASTER_DATABASE_URL:
        m_url = make_url(MASTER_DATABASE_URL)
        if bind_url.host == m_url.host and bind_url.database == m_url.database and not bind_url.query.get("options"):
             logger.warning("seed_all() called on Master DB session. Blocking to prevent pollution.")
             return
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

def grant_master_permissions(engine: Engine) -> None:
    """
    Grant read/write permissions to the application user on the master DB.
    
    This is necessary when the database is initialized by a superuser or admin
    user (MASTER_DATABASE_URL) but the application runs as a restricted
    user (DATABASE_URL).
    """
    app_url = make_url(settings.DATABASE_URL)
    app_user = app_url.username
    if not app_user:
        return

    logger.info("Granting privileges to application user: %s", app_user)
    with engine.connect() as conn:
        try:
            # Grant on tables, sequences, and functions in the public schema
            conn.execute(text(f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {app_user}"))
            conn.execute(text(f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {app_user}"))
            conn.execute(text(f"GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO {app_user}"))
            # Ensure future tables also get permissions
            conn.execute(text(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {app_user}"))
            conn.execute(text(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {app_user}"))
            conn.execute(text(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO {app_user}"))
            conn.commit()
        except Exception as e:
            logger.warning("Failed to grant permissions (likely not a superuser): %s", e)


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
    else:
        # Bootstrap: if the master database itself does not exist yet,
        # try to create it. This makes ``python -m app.init_db`` work
        # against a brand-new local Postgres without requiring the
        # operator to run ``createdb`` first. Best-effort — on managed
        # Postgres this will fail and fall through to the regular flow,
        # which will surface a clear error if the DB still cannot be
        # reached.
        try:
            ensure_master_database_exists(MASTER_DATABASE_URL)
        except Exception as exc:
            logger.warning(
                "Could not auto-create the master database (%s). "
                "Continuing — will fail later if it does not exist.",
                exc,
            )

    logger.info(f"Initializing Master Database: {MASTER_DATABASE_URL}")
    master_engine = create_engine(
        MASTER_DATABASE_URL,
        future=True,
        connect_args={"connect_timeout": 10},
    )

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
            else:
                # Be explicit when nothing happened (tables already exist)
                from app.models.base import MasterBase
                logger.info(
                    "Master schema is already up to date (%d tables verified).", 
                    len(MasterBase.metadata.tables)
                )
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

        # Grant permissions to the app user so the running API can see the tables
        # created by the admin user.
        grant_master_permissions(master_engine)
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

    Performance
    -----------
    ``sync_tenant_schema`` already runs ``metadata.create_all`` (with a
    fast-path on fresh DBs), so we no longer call ``create_tables`` a
    second time afterwards — that doubled the number of round trips
    against the tenant DB and was the dominant slowdown on
    high-latency managed-Postgres links.

    The engine that drives the seed pass is created with a 10s
    ``connect_timeout`` and reused across the whole call, so all DDL
    + seed inserts ride a single warm pool instead of opening and
    tearing down a connection per step.
    """
    check_production_safety(destructive=False)

    logger.info(f"Initializing Tenant Database: {db_url}")

    # Forward-migrate the tenant schema. On a brand-new DB this fast-
    # paths to a single ``metadata.create_all(checkfirst=False)`` pass.
    try:
        from app.db_sync import sync_tenant_schema

        summary = sync_tenant_schema(db_url)
        if summary:
            logger.info("Tenant schema sync applied: %s", summary)
    except Exception as exc:
        logger.exception("Tenant schema sync failed for %s: %s", db_url, exc)
        raise

    tenant_engine = create_engine(
        db_url,
        future=True,
        pool_pre_ping=False,
        connect_args={"connect_timeout": 10},
    )
    try:
        # Seed tenant data on the same engine — no extra create_tables
        # pass; sync_tenant_schema above already produced the schema.
        with Session(tenant_engine) as db:
            seed_all(db, create_default_admin=create_default_admin)
            db.commit()
    finally:
        tenant_engine.dispose()

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
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Destructive wipe! Drops all physical tenant databases "
            "and resets the master database schema from scratch."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    try:
        if args.reset:
            check_production_safety(destructive=True)
            logger.warning("Initiating FULL RESET. Dropping all tenant databases...")
            
            from app.core.cryptography import decrypt_string
            try:
                master_engine = create_engine(MASTER_DATABASE_URL, future=True)
                with Session(master_engine) as master_db:
                    tenants = master_db.query(Tenant).all()
                    
                    for tenant in tenants:
                        if tenant.db_connection_string:
                            try:
                                conn_str = decrypt_string(tenant.db_connection_string)
                                # Target database name
                                target_db_name = make_url(conn_str).database
                                target_identifier = f'"{target_db_name}"'
                                
                                # Connect to admin/postgres db
                                admin_url = make_url(MASTER_DATABASE_URL).set(database="postgres")
                                admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
                                
                                logger.info(f"Dropping tenant database: {target_db_name}")
                                with admin_engine.connect() as conn:
                                    conn.execute(text(f"""
                                        SELECT pg_terminate_backend(pid) 
                                        FROM pg_stat_activity 
                                        WHERE datname = '{target_db_name}' AND pid <> pg_backend_pid()
                                    """))
                                    conn.execute(text(f"DROP DATABASE IF EXISTS {target_identifier}"))
                                admin_engine.dispose()
                            except Exception as e:
                                logger.error(f"Failed to drop tenant database for {tenant.code}: {e}")
            except Exception as e:
                logger.error(f"Error accessing master database to list tenants: {e}")
            finally:
                if 'master_engine' in locals():
                    master_engine.dispose()
            
            logger.info("Proceeding to recreate master database schema...")
            run_master_initialization(recreate=True, physical_recreate=False)

        elif args.heal_missing_tenant_dbs:
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