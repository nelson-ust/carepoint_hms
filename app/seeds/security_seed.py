# app/seeds/security_seed.py
from __future__ import annotations

"""
Idempotent seed for the Carepoint HMS security baseline.

What this seed does
-------------------
- creates the canonical permission catalog covering all major modules
- creates the canonical role catalog (TENANT_ADMIN, ADMIN, etc.)
- maps roles to their default permissions
- optionally creates a bootstrap superuser

The seed is safe to run repeatedly:
- existing permissions/roles are not duplicated
- system permissions/roles are protected with `is_system=True`
- only missing role-permission mappings are created

Usage
-----
Programmatically:

    from app.core.database import SessionLocal
    from app.seeds import seed_security_baseline
    db = SessionLocal()
    seed_security_baseline(db)

CLI:

    python -m app.seeds.security_seed
"""

import argparse
import sys
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.enums import UserStatus
from app.core.security import get_password_hash
from app.models.all_models import (
    Permission,
    Role,
    RolePermissionAssociation,
    User,
    UserRoleAssociation,
)


# ============================================================
# CANONICAL PERMISSIONS
# ============================================================

DEFAULT_PERMISSIONS: list[dict] = [
    # User & access control
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
    {"code": "REPORT_EXPORT", "name": "Export reports", "module": "REPORT"},

    # Audit
    {"code": "AUDIT_READ", "name": "Read audit trails", "module": "AUDIT"},
    {"code": "SECURITY_EVENT_READ", "name": "Read security events", "module": "AUDIT"},

    # Ambulance & Dispatch (Stage 15)
    {"code": "AMBULANCE_READ", "name": "Read ambulance fleet", "module": "AMBULANCE"},
    {"code": "AMBULANCE_MANAGE", "name": "Manage ambulance fleet, drivers, equipment, maintenance", "module": "AMBULANCE"},
    {"code": "DISPATCH_READ", "name": "Read ambulance dispatches", "module": "AMBULANCE"},
    {"code": "DISPATCH_MANAGE", "name": "Create / progress ambulance dispatches", "module": "AMBULANCE"},

    # Notifications & Messaging (Stage 17)
    {"code": "NOTIFICATION_READ", "name": "Read notifications and templates", "module": "NOTIFICATION"},
    {"code": "NOTIFICATION_MANAGE", "name": "Manage notification templates", "module": "NOTIFICATION"},
    {"code": "NOTIFICATION_DISPATCH", "name": "Send notifications and trigger retries", "module": "NOTIFICATION"},
    {"code": "MESSAGE_SEND", "name": "Send and read direct messages", "module": "NOTIFICATION"},

    # Compliance / Governance (Stage 18)
    {"code": "COMPLIANCE_READ", "name": "Read compliance records", "module": "COMPLIANCE"},
    {"code": "COMPLIANCE_MANAGE", "name": "Manage compliance records", "module": "COMPLIANCE"},
    {"code": "ACCREDITATION_READ", "name": "Read accreditation records", "module": "COMPLIANCE"},
    {"code": "ACCREDITATION_MANAGE", "name": "Manage accreditation records", "module": "COMPLIANCE"},
    {"code": "INCIDENT_READ", "name": "Read incident reports (sensitive)", "module": "COMPLIANCE"},
    {"code": "INCIDENT_MANAGE", "name": "File and update incident reports", "module": "COMPLIANCE"},
    {"code": "INFECTION_LOG_READ", "name": "Read infection control logs", "module": "COMPLIANCE"},
    {"code": "INFECTION_LOG_MANAGE", "name": "Manage infection control logs", "module": "COMPLIANCE"},
    {"code": "QUALITY_PROJECT_READ", "name": "Read quality improvement projects", "module": "COMPLIANCE"},
    {"code": "QUALITY_PROJECT_MANAGE", "name": "Manage quality improvement projects", "module": "COMPLIANCE"},
    {"code": "GOVERNANCE_DASHBOARD", "name": "Read governance dashboard", "module": "COMPLIANCE"},

    # Procedures (clinic-room procedures distinct from surgical)
    {"code": "PROCEDURE_PERFORM", "name": "Perform / progress ordered procedures", "module": "PROCEDURE"},
    {"code": "PROCEDURE_MANAGE", "name": "Manage procedure catalog", "module": "PROCEDURE"},

    # Radiology / RIS
    {"code": "RADIOLOGY_ORDER", "name": "Order radiology studies", "module": "RADIOLOGY"},
    {"code": "RADIOLOGY_PERFORM", "name": "Perform / acquire radiology exams", "module": "RADIOLOGY"},
    {"code": "RADIOLOGY_REPORT", "name": "Draft / finalize radiology reports", "module": "RADIOLOGY"},
    {"code": "RADIOLOGY_RELEASE", "name": "Release radiology reports", "module": "RADIOLOGY"},
    {"code": "RADIOLOGY_MANAGE", "name": "Manage radiology procedure catalog", "module": "RADIOLOGY"},

    # Surgical / Theatre
    {"code": "SURGICAL_READ", "name": "Read surgical cases / theatre worklist", "module": "SURGICAL"},
    {"code": "SURGICAL_BOOK", "name": "Book / cancel surgical cases", "module": "SURGICAL"},
    {"code": "SURGICAL_PERFORM", "name": "Drive surgical-case lifecycle transitions", "module": "SURGICAL"},
    {"code": "SURGICAL_RECORD", "name": "Record consents / checklists / theatre notes", "module": "SURGICAL"},
    {"code": "SURGICAL_MANAGE", "name": "Manage surgical procedure catalog", "module": "SURGICAL"},
    {"code": "THEATRE_MANAGE", "name": "Manage operating theatres + status", "module": "SURGICAL"},
    {"code": "ANAESTHESIA_RECORD", "name": "Record anaesthesia entries", "module": "SURGICAL"},
    {"code": "INSTRUMENT_MANAGE", "name": "Manage surgical instrument sets + sterilization", "module": "SURGICAL"},

    # Insurance Claims
    {"code": "CLAIM_READ", "name": "Read insurance claims", "module": "INSURANCE"},
    {"code": "CLAIM_MANAGE", "name": "Create / submit / withdraw / appeal claims", "module": "INSURANCE"},
    {"code": "CLAIM_REVIEW", "name": "Record adjudication / authorization decisions / receive payments", "module": "INSURANCE"},

    # Patient Portal — granted to the PATIENT role on first OTP login.
    {"code": "PATIENT_PORTAL_ACCESS", "name": "Access the patient portal", "module": "PATIENT_PORTAL"},
    {"code": "PATIENT_PORTAL_VIEW_OWN_RECORD", "name": "View own medical record (visits, labs, prescriptions)", "module": "PATIENT_PORTAL"},
    {"code": "PATIENT_PORTAL_VIEW_OWN_BILLS", "name": "View own bills, invoices, and payments", "module": "PATIENT_PORTAL"},
    {"code": "PATIENT_PORTAL_FUND_CARD", "name": "Top up the patient membership card", "module": "PATIENT_PORTAL"},
]


# ============================================================
# CANONICAL ROLES
# ============================================================

DEFAULT_ROLES: list[dict] = [
    {
        "code": "TENANT_ADMIN",
        "name": "Tenant Administrator",
        "description": "Unrestricted system access.",
    },
    {
        "code": "ADMIN",
        "name": "Administrator",
        "description": "General hospital administrator.",
    },
    {
        "code": "DOCTOR",
        "name": "Doctor",
        "description": "Clinician with full clinical privileges.",
    },
    {
        "code": "NURSE",
        "name": "Nurse",
        "description": "Nursing staff for triage, vitals, and ward care.",
    },
    {
        "code": "LAB_SCIENTIST",
        "name": "Laboratory Scientist",
        "description": "Performs and verifies laboratory tests.",
    },
    {
        "code": "PHARMACIST",
        "name": "Pharmacist",
        "description": "Reviews prescriptions, dispenses medications.",
    },
    {
        "code": "BILLING_OFFICER",
        "name": "Billing Officer",
        "description": "Manages charge capture and billing operations.",
    },
    {
        "code": "CASHIER",
        "name": "Cashier",
        "description": "Receives payments and reconciles cash.",
    },
    {
        "code": "RECEPTIONIST",
        "name": "Receptionist",
        "description": "Registers patients and manages appointments and queues.",
    },
    {
        "code": "HR_MANAGER",
        "name": "HR Manager",
        "description": "Manages staff, schedules, and HR records.",
    },
    {
        "code": "RADIOLOGIST",
        "name": "Radiologist",
        "description": "Reads and reports radiology studies.",
    },
    {
        "code": "RADIOGRAPHER",
        "name": "Radiographer",
        "description": "Performs radiology exams and acquires images.",
    },
    {
        "code": "SURGEON",
        "name": "Surgeon",
        "description": "Performs surgical procedures and manages operative cases.",
    },
    {
        "code": "ANAESTHETIST",
        "name": "Anaesthetist",
        "description": "Administers anaesthesia and records intra-op anaesthesia data.",
    },
    {
        "code": "THEATRE_NURSE",
        "name": "Theatre Nurse",
        "description": "Scrub / circulating nurse supporting surgical cases.",
    },
    {
        "code": "INSURANCE_OFFICER",
        "name": "Insurance Officer",
        "description": "Submits and follows up on insurance claims.",
    },
    {
        "code": "INSURANCE_REVIEWER",
        "name": "Insurance Reviewer",
        "description": "Records insurer authorization, adjudication and payments.",
    },
    {
        "code": "PATIENT",
        "name": "Patient",
        "description": (
            "End-user role for patients accessing the patient portal. "
            "Auto-assigned on first successful OTP login."
        ),
    },
]


# ============================================================
# ROLE -> PERMISSIONS
# ============================================================

DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    # TENANT_ADMIN gets every permission programmatically.
    "TENANT_ADMIN": [permission["code"] for permission in DEFAULT_PERMISSIONS],
    "ADMIN": [
        "USER_READ", "USER_CREATE", "USER_UPDATE", "USER_MANAGE_STATUS",
        "USER_MANAGE_ROLES", "USER_FORCE_PASSWORD_RESET",
        "ROLE_READ", "ROLE_CREATE", "ROLE_UPDATE",
        "ROLE_ASSIGN_PERMISSIONS",
        "PERMISSION_READ",
        "TWO_FACTOR_ADMIN",
        "PATIENT_READ", "PATIENT_CREATE", "PATIENT_UPDATE",
        "APPOINTMENT_READ", "APPOINTMENT_CREATE", "APPOINTMENT_UPDATE",
        "APPOINTMENT_CANCEL",
        "VISIT_READ", "VISIT_INITIATE", "VISIT_ROUTE", "QUEUE_MANAGE",
        "BILLING_READ", "BILLING_CREATE", "INVOICE_ISSUE", "INVOICE_VOID",
        "PAYMENT_RECEIVE",
        "ADMISSION_CREATE", "ADMISSION_DISCHARGE", "BED_MANAGE", "WARD_MANAGE",
        "INVENTORY_READ", "INVENTORY_MANAGE", "STOCK_MOVEMENT_POST",
        "REPORT_READ", "REPORT_EXPORT",
        "AUDIT_READ", "SECURITY_EVENT_READ",
        "PATIENT_CARD_VIEW", "PATIENT_CARD_CREATE", "PATIENT_CARD_UPDATE",
        "PATIENT_CARD_FUND", "PATIENT_CARD_DEBIT",
        # Admins also get full visibility into ambulance / dispatch /
        # notifications / governance for day-to-day oversight.
        "AMBULANCE_READ", "AMBULANCE_MANAGE", "DISPATCH_READ", "DISPATCH_MANAGE",
        "NOTIFICATION_READ", "NOTIFICATION_MANAGE", "NOTIFICATION_DISPATCH", "MESSAGE_SEND",
        "COMPLIANCE_READ", "COMPLIANCE_MANAGE",
        "ACCREDITATION_READ", "ACCREDITATION_MANAGE",
        "INCIDENT_READ", "INCIDENT_MANAGE",
        "INFECTION_LOG_READ", "INFECTION_LOG_MANAGE",
        "QUALITY_PROJECT_READ", "QUALITY_PROJECT_MANAGE",
        "GOVERNANCE_DASHBOARD",
    ],
    "DOCTOR": [
        "PATIENT_READ", "PATIENT_UPDATE",
        "APPOINTMENT_READ",
        "VISIT_READ", "VISIT_ROUTE", "QUEUE_MANAGE",
        "TRIAGE_PERFORM", "VITAL_SIGN_RECORD",
        "CONSULTATION_READ", "CONSULTATION_WRITE",
        "DIAGNOSIS_WRITE", "PROCEDURE_ORDER",
        "LAB_ORDER_CREATE",
        "PRESCRIPTION_WRITE",
        "ADMISSION_CREATE",
        "REPORT_READ",
        # Radiology + procedure ordering, surgical-case booking
        "RADIOLOGY_ORDER", "PROCEDURE_PERFORM",
        "SURGICAL_READ", "SURGICAL_BOOK",
    ],
    "NURSE": [
        "PATIENT_READ",
        "VISIT_READ", "VISIT_ROUTE", "QUEUE_MANAGE",
        "TRIAGE_PERFORM", "VITAL_SIGN_RECORD",
        "CONSULTATION_READ",
        "REPORT_READ",
    ],
    "LAB_SCIENTIST": [
        "PATIENT_READ",
        "VISIT_READ", "QUEUE_MANAGE", "VISIT_ROUTE",
        "LAB_ORDER_CREATE", "LAB_RESULT_ENTER",
        "LAB_RESULT_VERIFY", "LAB_RESULT_RELEASE",
        "REPORT_READ",
    ],
    "PHARMACIST": [
        "PATIENT_READ",
        "VISIT_READ", "QUEUE_MANAGE", "VISIT_ROUTE",
        "PRESCRIPTION_DISPENSE",
        "PHARMACY_STOCK_MANAGE",
        "INVENTORY_READ", "STOCK_MOVEMENT_POST",
        "REPORT_READ",
    ],
    "BILLING_OFFICER": [
        "PATIENT_READ",
        "VISIT_READ", "QUEUE_MANAGE", "VISIT_ROUTE",
        "BILLING_READ", "BILLING_CREATE",
        "INVOICE_ISSUE", "INVOICE_VOID",
        "PAYMENT_RECEIVE", "PAYMENT_REFUND",
        "REPORT_READ", "REPORT_EXPORT",
        "PATIENT_CARD_VIEW", "PATIENT_CARD_FUND", "PATIENT_CARD_DEBIT",
    ],
    "CASHIER": [
        "PATIENT_READ", "QUEUE_MANAGE", "VISIT_ROUTE",
        "BILLING_READ", "INVOICE_ISSUE",
        "PAYMENT_RECEIVE",
        "REPORT_READ",
        "PATIENT_CARD_VIEW", "PATIENT_CARD_FUND", "PATIENT_CARD_DEBIT",
    ],
    "RECEPTIONIST": [
        "PATIENT_READ", "PATIENT_CREATE", "PATIENT_UPDATE",
        "APPOINTMENT_READ", "APPOINTMENT_CREATE",
        "APPOINTMENT_UPDATE", "APPOINTMENT_CANCEL",
        "VISIT_READ", "VISIT_INITIATE", "QUEUE_MANAGE",
        # Receptionists send appointment reminders and read internal messages.
        "NOTIFICATION_READ", "NOTIFICATION_DISPATCH",
        "MESSAGE_SEND",
    ],
    "HR_MANAGER": [
        "USER_READ", "USER_CREATE", "USER_UPDATE",
        "USER_MANAGE_STATUS", "USER_MANAGE_ROLES",
        "ROLE_READ",
        "REPORT_READ",
        "MESSAGE_SEND",
    ],
    "RADIOLOGIST": [
        "PATIENT_READ", "VISIT_READ",
        "RADIOLOGY_ORDER", "RADIOLOGY_PERFORM",
        "RADIOLOGY_REPORT", "RADIOLOGY_RELEASE",
        "REPORT_READ",
    ],
    "RADIOGRAPHER": [
        "PATIENT_READ", "VISIT_READ",
        "RADIOLOGY_PERFORM",
        "REPORT_READ",
    ],
    "SURGEON": [
        "PATIENT_READ", "PATIENT_UPDATE",
        "VISIT_READ", "VISIT_ROUTE",
        "CONSULTATION_READ", "CONSULTATION_WRITE",
        "DIAGNOSIS_WRITE",
        "SURGICAL_READ", "SURGICAL_BOOK", "SURGICAL_PERFORM", "SURGICAL_RECORD",
        "REPORT_READ",
    ],
    "ANAESTHETIST": [
        "PATIENT_READ",
        "VISIT_READ",
        "SURGICAL_READ", "SURGICAL_RECORD", "ANAESTHESIA_RECORD",
        "REPORT_READ",
    ],
    "THEATRE_NURSE": [
        "PATIENT_READ",
        "VISIT_READ",
        "SURGICAL_READ", "SURGICAL_RECORD", "INSTRUMENT_MANAGE",
        "REPORT_READ",
    ],
    "INSURANCE_OFFICER": [
        "PATIENT_READ", "VISIT_READ", "BILLING_READ",
        "CLAIM_READ", "CLAIM_MANAGE",
        "REPORT_READ",
    ],
    "INSURANCE_REVIEWER": [
        "PATIENT_READ", "VISIT_READ", "BILLING_READ",
        "CLAIM_READ", "CLAIM_REVIEW",
        "REPORT_READ",
    ],
    # PATIENT carries only portal-scoped permissions. Endpoints that act
    # on a specific patient still need to verify ownership at the route
    # layer — having ``PATIENT_PORTAL_VIEW_OWN_RECORD`` is necessary but
    # not sufficient to read someone *else's* record.
    "PATIENT": [
        "PATIENT_PORTAL_ACCESS",
        "PATIENT_PORTAL_VIEW_OWN_RECORD",
        "PATIENT_PORTAL_VIEW_OWN_BILLS",
        "PATIENT_PORTAL_FUND_CARD",
    ],
}


# ============================================================
# CORE SEEDING LOGIC
# ============================================================


def _upsert_permission(db: Session, *, code: str, name: str, module: str) -> Permission:
    """
    Insert or update a permission keyed by code.
    """
    permission = (
        db.query(Permission)
        .filter(
            or_(Permission.code == code, Permission.name == name),
            Permission.is_deleted.is_(False),
        )
        .first()
    )
    if permission is None:
        permission = Permission(
            code=code,
            name=name,
            module=module,
            description=name,
            is_system=True,
        )
        db.add(permission)
        db.flush()
        db.refresh(permission)
        return permission

    changed = False
    if permission.name != name:
        permission.name = name
        changed = True
    if permission.module != module:
        permission.module = module
        changed = True
    if not permission.is_system:
        permission.is_system = True
        changed = True
    if changed:
        db.add(permission)
        db.flush()
        db.refresh(permission)
    return permission


def _upsert_role(db: Session, *, code: str, name: str, description: str) -> Role:
    """
    Insert or update a role keyed by code.
    """
    role = (
        db.query(Role)
        .filter(
            or_(Role.code == code, Role.name == name),
            Role.is_deleted.is_(False),
        )
        .first()
    )
    if role is None:
        role = Role(
            code=code,
            name=name,
            description=description,
            is_system=True,
        )
        db.add(role)
        db.flush()
        db.refresh(role)
        return role

    changed = False
    if role.name != name:
        role.name = name
        changed = True
    if role.description != description:
        role.description = description
        changed = True
    if not role.is_system:
        role.is_system = True
        changed = True
    if changed:
        db.add(role)
        db.flush()
        db.refresh(role)
    return role


def _ensure_role_permissions(
    db: Session,
    role: Role,
    permission_codes: list[str],
    permissions_by_code: dict[str, Permission],
) -> int:
    """
    Ensure the supplied permissions are attached to the role. Returns the
    number of newly-created associations.
    """
    existing_permission_ids = {
        link.permission_id for link in role.role_permissions or []
        if not link.is_deleted
    }
    created = 0
    for code in permission_codes:
        permission = permissions_by_code.get(code)
        if permission is None:
            continue
        if permission.id in existing_permission_ids:
            continue
        link = RolePermissionAssociation(
            role_id=role.id,
            permission_id=permission.id,
        )
        db.add(link)
        created += 1
    if created:
        db.flush()
    return created


def _seed_fresh_baseline(
    db: Session,
    bootstrap_superuser: bool,
    superuser_username: Optional[str],
    superuser_email: Optional[str],
    superuser_password: Optional[str],
) -> dict:
    """Fast-path for empty databases: direct bulk inserts."""
    summary = {
        "permissions_processed": 0,
        "roles_processed": 0,
        "role_permission_links_created": 0,
        "superuser_created": False,
    }
    
    # 1. Bulk insert permissions
    perms_to_add = []
    perms_by_code = {}
    for entry in DEFAULT_PERMISSIONS:
        p = Permission(
            code=entry["code"],
            name=entry["name"],
            module=entry["module"],
            description=entry["name"],
            is_system=True,
        )
        perms_to_add.append(p)
        perms_by_code[p.code] = p
    
    db.add_all(perms_to_add)
    db.flush()
    summary["permissions_processed"] = len(perms_to_add)
    
    # 2. Bulk insert roles
    roles_to_add = []
    roles_by_code = {}
    for entry in DEFAULT_ROLES:
        r = Role(
            code=entry["code"],
            name=entry["name"],
            description=entry["description"],
            is_system=True,
        )
        roles_to_add.append(r)
        roles_by_code[r.code] = r
    
    db.add_all(roles_to_add)
    db.flush()
    summary["roles_processed"] = len(roles_to_add)
    
    # 3. Create role-permission links
    links = []
    for role_code, perms in ROLE_PERMISSIONS_BASELINE.items():
        role = roles_by_code.get(role_code)
        if not role: continue
        for p_code in perms:
            perm = perms_by_code.get(p_code)
            if perm:
                links.append(RolePermissionAssociation(role_id=role.id, permission_id=perm.id))
    
    db.add_all(links)
    summary["role_permission_links_created"] = len(links)
    
    # 4. Superuser
    if bootstrap_superuser and superuser_username and superuser_email and superuser_password:
        from app.core.security import get_password_hash
        from app.core.enums import UserStatus
        user = User(
            username=superuser_username,
            email=superuser_email,
            password_hash=get_password_hash(superuser_password),
            status=UserStatus.ACTIVE,
            is_superuser=True,
            is_email_verified=True,
        )
        db.add(user)
        db.flush()
        
        # Link to admin role
        admin_role = roles_by_code.get("TENANT_ADMIN")
        if admin_role:
            db.add(UserRoleAssociation(user_id=user.id, role_id=admin_role.id))
        
        summary["superuser_created"] = True
        
    db.commit()
    return summary


def seed_security_baseline(
    db: Session,
    *,
    bootstrap_superuser: bool = False,
    superuser_username: Optional[str] = None,
    superuser_email: Optional[str] = None,
    superuser_password: Optional[str] = None,
    is_fresh: bool = False,
) -> dict:
    """
    Seed the canonical permission catalog, role catalog, role-permission
    mapping, and (optionally) a bootstrap superuser.

    The function commits at the end. Pass an existing transactional session
    if your caller already manages commits.

    Args:
        db: Active SQLAlchemy session.
        bootstrap_superuser: When True, also create a superuser with
            TENANT_ADMIN role assigned.
        superuser_username / superuser_email / superuser_password:
            Required when `bootstrap_superuser` is True.

    Returns:
        dict: Summary of created/updated counts.
    """
    if is_fresh:
        return _seed_fresh_baseline(db, bootstrap_superuser, superuser_username, superuser_email, superuser_password)

    summary = {
        "permissions_processed": 0,
        "roles_processed": 0,
        "role_permission_links_created": 0,
        "superuser_created": False,
    }

    # 1. Bulk pre-fetch existing permissions to avoid hundreds of single queries
    existing_perms = db.query(Permission).filter(Permission.is_deleted.is_(False)).all()
    perms_map = {p.code: p for p in existing_perms}
    perms_by_name = {p.name: p for p in existing_perms}

    permissions_by_code: dict[str, Permission] = {}
    to_add_perms = []

    for entry in DEFAULT_PERMISSIONS:
        code = entry["code"]
        name = entry["name"]
        module = entry["module"]
        
        # Check by code or name (to match _upsert_permission logic)
        permission = perms_map.get(code) or perms_by_name.get(name)
        
        if permission is None:
            permission = Permission(
                code=code,
                name=name,
                module=module,
                description=name,
                is_system=True,
            )
            to_add_perms.append(permission)
            perms_map[code] = permission # Track for subsequent role mapping
        else:
            # Update existing if needed
            changed = False
            if permission.name != name:
                permission.name = name
                changed = True
            if permission.module != module:
                permission.module = module
                changed = True
            if not permission.is_system:
                permission.is_system = True
                changed = True
            if changed:
                db.add(permission)
        
        permissions_by_code[code] = permission
        summary["permissions_processed"] += 1

    if to_add_perms:
        db.add_all(to_add_perms)
    db.flush()

    # 2. Bulk pre-fetch existing roles
    existing_roles = db.query(Role).filter(Role.is_deleted.is_(False)).all()
    roles_map = {r.code: r for r in existing_roles}

    roles_by_code: dict[str, Role] = {}
    to_add_roles = []

    for entry in DEFAULT_ROLES:
        code = entry["code"]
        name = entry["name"]
        description = entry["description"]
        
        role = roles_map.get(code)
        if role is None:
            role = Role(
                code=code,
                name=name,
                description=description,
                is_system=True,
            )
            to_add_roles.append(role)
        else:
            changed = False
            if role.name != name:
                role.name = name
                changed = True
            if role.description != description:
                role.description = description
                changed = True
            if not role.is_system:
                role.is_system = True
                changed = True
            if changed:
                db.add(role)
        
        roles_by_code[code] = role
        summary["roles_processed"] += 1

    if to_add_roles:
        db.add_all(to_add_roles)
    db.flush()

    for role_code, permission_codes in DEFAULT_ROLE_PERMISSIONS.items():
        role = roles_by_code.get(role_code)
        if role is None:
            continue
        # Re-fetch with permissions loaded so the existing-set check works.
        db.refresh(role)
        new_links = _ensure_role_permissions(
            db,
            role,
            permission_codes,
            permissions_by_code,
        )
        summary["role_permission_links_created"] += new_links

    if bootstrap_superuser:
        if not (superuser_username and superuser_email and superuser_password):
            raise ValueError(
                "bootstrap_superuser=True requires superuser_username, "
                "superuser_email, and superuser_password."
            )
        uname_lower = superuser_username.lower()
        email_lower = superuser_email.lower()
        existing = (
            db.query(User)
            .filter(
                or_(User.username == uname_lower, User.email == email_lower),
                User.is_deleted.is_(False),
            )
            .first()
        )
        if existing is None:
            # ----- create path -----
            user = User(
                username=uname_lower,
                email=email_lower,
                password_hash=get_password_hash(superuser_password),
                first_name="Super",
                last_name="Admin",
                status=UserStatus.ACTIVE,
                is_superuser=True,
                is_email_verified=True,
            )
            db.add(user)
            db.flush()
            db.refresh(user)
            summary["superuser_created"] = True
        else:
            # ----- idempotent refresh path -----
            # Re-running the bootstrap with the same identifier should be a
            # safe way to reset/refresh the superuser. Without this, the
            # operator has no way to recover from a forgotten password
            # short of editing the DB directly.
            existing.password_hash = get_password_hash(superuser_password)
            existing.status = UserStatus.ACTIVE
            existing.is_superuser = True
            existing.is_email_verified = True
            existing.failed_login_attempts = 0
            existing.locked_until = None
            db.add(existing)
            db.flush()
            db.refresh(existing)
            user = existing
            summary["superuser_refreshed"] = True

        # Make sure the TENANT_ADMIN role is assigned, regardless of path.
        super_admin_role = roles_by_code.get("TENANT_ADMIN")
        if super_admin_role is not None:
            already_assigned = (
                db.query(UserRoleAssociation)
                .filter(
                    UserRoleAssociation.user_id == user.id,
                    UserRoleAssociation.role_id == super_admin_role.id,
                    UserRoleAssociation.is_deleted.is_(False),
                )
                .first()
            )
            if already_assigned is None:
                link = UserRoleAssociation(
                    user_id=user.id,
                    role_id=super_admin_role.id,
                )
                db.add(link)
                db.flush()

    db.commit()
    return summary


# ============================================================
# STAND-ALONE PASSWORD RESET
# ============================================================


def reset_user_password(
    db: Session,
    *,
    identifier: str,
    new_password: str,
    activate: bool = True,
) -> dict:
    """
    One-off password reset for a single user.

    Looks the user up by username, email, or phone (matching the same
    identifier resolution the login flow uses), hashes the supplied
    password, and clears any active lockout. Useful when the bootstrap
    superuser flow can't be used because there is no working credential.

    Args:
        db: Active SQLAlchemy session. The function commits.
        identifier: Username / email / phone — case-insensitive on
            username + email.
        new_password: Plaintext password (will be bcrypt-hashed).
        activate: When True, also flip ``status`` back to ACTIVE and clear
            soft-delete / lockout fields so the user can log in again.

    Returns:
        dict: ``{"user_id": int, "username": str, "email": str,
                 "status": str, "reset": True}`` or
              ``{"reset": False, "reason": "user not found"}``.
    """
    normalized = identifier.strip()
    normalized_lower = normalized.lower()

    user = (
        db.query(User)
        .filter(
            or_(
                User.username == normalized_lower,
                User.email == normalized_lower,
                User.phone_number == normalized,
            )
        )
        .first()
    )
    if user is None:
        return {"reset": False, "reason": "user not found", "identifier": identifier}

    user.password_hash = get_password_hash(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    if activate:
        user.is_deleted = False
        user.status = UserStatus.ACTIVE
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "status": str(user.status),
        "reset": True,
    }


# ============================================================
# CLI ENTRYPOINT
# ============================================================


def _run_cli() -> int:
    parser = argparse.ArgumentParser(description="Seed Carepoint HMS security baseline.")
    parser.add_argument(
        "--bootstrap-superuser",
        action="store_true",
        help="Create or refresh the bootstrap superuser.",
    )
    parser.add_argument("--username", type=str, help="Bootstrap superuser username.")
    parser.add_argument("--email", type=str, help="Bootstrap superuser email.")
    parser.add_argument("--password", type=str, help="Bootstrap superuser password.")

    parser.add_argument(
        "--reset-password",
        action="store_true",
        help=(
            "Reset the password for an existing user matched by --identifier. "
            "Skips the permission/role/superuser baseline seed."
        ),
    )
    parser.add_argument(
        "--identifier",
        type=str,
        help="Username, email, or phone of the user whose password to reset.",
    )
    parser.add_argument(
        "--new-password",
        type=str,
        help="New password to set when --reset-password is used.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset_password:
            if not (args.identifier and args.new_password):
                parser.error("--reset-password requires --identifier and --new-password.")
            result = reset_user_password(
                db,
                identifier=args.identifier,
                new_password=args.new_password,
            )
            print("Password reset:")
            for key, value in result.items():
                print(f"  {key}: {value}")
            return 0 if result.get("reset") else 1

        summary = seed_security_baseline(
            db,
            bootstrap_superuser=args.bootstrap_superuser,
            superuser_username=args.username,
            superuser_email=args.email,
            superuser_password=args.password,
        )
    finally:
        db.close()

    print("Security baseline seeded.")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(_run_cli())
