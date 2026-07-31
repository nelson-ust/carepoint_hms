# app/seeds/unified_security_seed.py
from __future__ import annotations

"""
Unified Security Baseline Seed for Carepoint HMS.

This script merges the original security_seed.py and the new 
comprehensive_security_seed.py. It provides:
1. Fast-path bulk seeding for fresh databases.
2. Idempotent upsert seeding for existing databases.
3. Fleet-wide seeding across all provisioned tenants.
4. Bootstrap superuser creation.
5. Stand-alone user password reset utility.
"""

import argparse
import sys
import os
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import or_, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import SessionLocal, get_master_engine
from app.core.enums import UserStatus
from app.core.security import get_password_hash
from app.core.cryptography import decrypt_string
from app.models.all_models import (
    Permission,
    Role,
    RolePermissionAssociation,
    User,
    UserRoleAssociation,
    Tenant,
)

# ============================================================
# CANONICAL DATA
# ============================================================

ALL_PERMISSIONS: list[dict] = [
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

    # Patient Portal
    {"code": "PORTAL_MESSAGE_READ", "name": "Read patient portal messages", "module": "PORTAL"},

    # Backup & SaaS Admin
    {"code": "BACKUP_READ", "name": "Read backups", "module": "BACKUP"},
    {"code": "BACKUP_CREATE", "name": "Create backups", "module": "BACKUP"},
    {"code": "SETTING_UPDATE", "name": "Update system settings", "module": "SETTING"},
    {"code": "SaaS_ADMIN", "name": "SaaS Administrative Access", "module": "SaaS"},
]

ALL_ROLES: list[dict] = [
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

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "TENANT_ADMIN": [p["code"] for p in ALL_PERMISSIONS],
    "ADMIN": [
        "USER_READ", "USER_CREATE", "USER_UPDATE", "USER_MANAGE_STATUS", "USER_MANAGE_ROLES",
        "ROLE_READ", "ROLE_CREATE", "ROLE_UPDATE", "ROLE_ASSIGN_PERMISSIONS",
        "PERMISSION_READ", "FACILITY_READ", "FACILITY_CREATE", "FACILITY_UPDATE",
        "BACKUP_READ", "BACKUP_CREATE", "SETTING_UPDATE", "REPORT_READ", "REPORT_GENERATE",
        "TEMPLATE_READ", "TEMPLATE_CREATE", "INTEGRATION_READ", "INTEGRATION_UPDATE",
        "PATIENT_READ", "PATIENT_CREATE", "PATIENT_UPDATE", "APPOINTMENT_READ",
        "VISIT_READ", "BILLING_READ", "AUDIT_READ", "SECURITY_EVENT_READ",
        "PORTAL_MESSAGE_READ",
    ],
    "DOCTOR": [
        "PATIENT_READ", "PATIENT_UPDATE", "VISIT_READ", "VISIT_ROUTE", "CONSULTATION_READ",
        "CONSULTATION_WRITE", "DIAGNOSIS_WRITE", "PRESCRIPTION_WRITE", "LAB_ORDER_CREATE",
        "RADIOLOGY_ORDER", "PROCEDURE_ORDER", "PROCEDURE_PERFORM", "ADMISSION_CREATE",
        "MEAL_READ", "MEAL_ORDER", "REFERRAL_READ", "REFERRAL_CREATE", "REFERRAL_UPDATE",
        "SURGICAL_READ", "SURGICAL_BOOK",
    ],
    "NURSE": [
        "PATIENT_READ", "VISIT_READ", "VISIT_ROUTE", "TRIAGE_PERFORM", "VITAL_SIGN_RECORD",
        "MEAL_READ", "MEAL_SERVE", "REFERRAL_READ", "CONSULTATION_READ", "ADMISSION_CREATE",
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
        "PORTAL_MESSAGE_READ",
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
    "PATIENT": [
        "PATIENT_READ", "APPOINTMENT_READ", "BILLING_READ",
    ]
}


# ============================================================
# CORE SEEDING LOGIC
# ============================================================

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
    Unified entry point for seeding permissions and roles.
    """
    if is_fresh:
        return _seed_fresh_baseline(db, bootstrap_superuser, superuser_username, superuser_email, superuser_password)

    summary = {
        "permissions_processed": 0,
        "roles_processed": 0,
        "role_permission_links_created": 0,
        "superuser_created": False,
        "superuser_refreshed": False,
    }

    # 1. Upsert Permissions
    permissions_by_code: dict[str, Permission] = {}
    for p_data in ALL_PERMISSIONS:
        perm = db.query(Permission).filter_by(code=p_data["code"]).first()
        if not perm:
            perm = Permission(
                code=p_data["code"],
                name=p_data["name"],
                module=p_data["module"],
                description=p_data["name"],
                is_system=True
            )
            db.add(perm)
        else:
            perm.name = p_data["name"]
            perm.module = p_data["module"]
            perm.is_system = True
            db.add(perm)
        permissions_by_code[p_data["code"]] = perm
        summary["permissions_processed"] += 1
    db.flush()

    # 2. Upsert Roles
    roles_by_code: dict[str, Role] = {}
    for r_data in ALL_ROLES:
        role = db.query(Role).filter_by(code=r_data["code"]).first()
        if not role:
            role = Role(
                code=r_data["code"],
                name=r_data["name"],
                description=r_data["description"],
                is_system=True
            )
            db.add(role)
        else:
            role.name = r_data["name"]
            role.description = r_data["description"]
            role.is_system = True
            db.add(role)
        roles_by_code[r_data["code"]] = role
        summary["roles_processed"] += 1
    db.flush()

    # 3. Map Role-Permissions
    for role_code, p_codes in ROLE_PERMISSIONS.items():
        role = roles_by_code.get(role_code)
        if not role:
            continue
        
        db.refresh(role)
        existing_p_ids = {link.permission_id for link in role.role_permissions if not link.is_deleted}
        
        for p_code in p_codes:
            perm = permissions_by_code.get(p_code)
            if perm and perm.id not in existing_p_ids:
                link = RolePermissionAssociation(role_id=role.id, permission_id=perm.id)
                db.add(link)
                summary["role_permission_links_created"] += 1
    
    # 4. Bootstrap Superuser
    if bootstrap_superuser:
        _handle_superuser_bootstrap(db, roles_by_code, summary, superuser_username, superuser_email, superuser_password)

    db.commit()
    return summary


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
    for entry in ALL_PERMISSIONS:
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
    for entry in ALL_ROLES:
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
    for role_code, perms in ROLE_PERMISSIONS.items():
        role = roles_by_code.get(role_code)
        if not role: continue
        for p_code in perms:
            perm = perms_by_code.get(p_code)
            if perm:
                links.append(RolePermissionAssociation(role_id=role.id, permission_id=perm.id))
    db.add_all(links)
    summary["role_permission_links_created"] = len(links)
    
    # 4. Superuser
    if bootstrap_superuser:
        _handle_superuser_bootstrap(db, roles_by_code, summary, superuser_username, superuser_email, superuser_password)
        
    db.commit()
    return summary


def _handle_superuser_bootstrap(db, roles_by_code, summary, username, email, password):
    if not (username and email and password):
        raise ValueError("Bootstrap superuser requires username, email, and password.")
    
    uname_lower = username.lower()
    email_lower = email.lower()
    
    existing = db.query(User).filter(
        or_(User.username == uname_lower, User.email == email_lower),
        User.is_deleted.is_(False)
    ).first()
    
    if existing is None:
        user = User(
            username=uname_lower,
            email=email_lower,
            password_hash=get_password_hash(password),
            first_name="Super",
            last_name="Admin",
            status=UserStatus.ACTIVE,
            is_superuser=True,
            is_email_verified=True,
        )
        db.add(user)
        db.flush()
        summary["superuser_created"] = True
    else:
        existing.password_hash = get_password_hash(password)
        existing.status = UserStatus.ACTIVE
        existing.is_superuser = True
        existing.is_email_verified = True
        db.add(existing)
        db.flush()
        user = existing
        summary["superuser_refreshed"] = True

    admin_role = roles_by_code.get("TENANT_ADMIN")
    if admin_role:
        already_assigned = db.query(UserRoleAssociation).filter(
            UserRoleAssociation.user_id == user.id,
            UserRoleAssociation.role_id == admin_role.id,
            UserRoleAssociation.is_deleted.is_(False)
        ).first()
        if not already_assigned:
            db.add(UserRoleAssociation(user_id=user.id, role_id=admin_role.id))


def reset_user_password(db: Session, *, identifier: str, new_password: str, activate: bool = True) -> dict:
    """One-off password reset utility."""
    normalized = identifier.strip().lower()
    user = db.query(User).filter(
        or_(User.username == normalized, User.email == normalized, User.phone_number == identifier.strip())
    ).first()
    
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
    return {"user_id": user.id, "username": user.username, "email": user.email, "reset": True}


# ============================================================
# CLI ENTRYPOINT
# ============================================================

def _run_cli():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Unified Security Seed for Carepoint HMS.")
    
    # Modes
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--all-tenants", action="store_true", help="Seed all provisioned tenants.")
    mode_group.add_argument("--db-url", type=str, help="Seed a specific database URL.")
    mode_group.add_argument("--reset-password", action="store_true", help="Reset a user's password.")
    
    # Seeding Options
    parser.add_argument("--bootstrap-superuser", action="store_true", help="Create/refresh superuser.")
    parser.add_argument("--username", type=str, help="Superuser username.")
    parser.add_argument("--email", type=str, help="Superuser email.")
    parser.add_argument("--password", type=str, help="Superuser password.")
    parser.add_argument("--is-fresh", action="store_true", help="Use bulk-insert fast-path (for empty DBs).")
    
    # Reset Options
    parser.add_argument("--identifier", type=str, help="Username/Email/Phone for password reset.")
    parser.add_argument("--new-password", type=str, help="New password for reset.")

    args = parser.parse_args()
    db = None

    try:
        if args.reset_password:
            if not (args.identifier and args.new_password):
                parser.error("--reset-password requires --identifier and --new-password")
            db = SessionLocal()
            result = reset_user_password(db, identifier=args.identifier, new_password=args.new_password)
            print(f"Password reset result: {result}")
            return

        if args.all_tenants:
            print("--- Fleet-wide Seeding Mode Activated ---")
            master_engine = get_master_engine()
            with Session(master_engine) as master_db:
                tenants = master_db.query(Tenant).filter(Tenant.is_provisioned == True).all()
                tenant_data = [{"name": t.name, "code": t.code, "conn": t.db_connection_string} for t in tenants]
            
            for t in tenant_data:
                print(f"\nProcessing Tenant: {t['name']} ({t['code']})")
                if not t['conn']: continue
                try:
                    db_url = decrypt_string(t['conn'])
                    engine = create_engine(db_url)
                    with Session(engine) as tenant_db:
                        summary = seed_security_baseline(
                            tenant_db,
                            bootstrap_superuser=args.bootstrap_superuser,
                            superuser_username=args.username,
                            superuser_email=args.email,
                            superuser_password=args.password,
                            is_fresh=args.is_fresh
                        )
                        print(f"  Summary: {summary}")
                    engine.dispose()
                except Exception as e:
                    print(f"  [X] Error: {e}")
            return

        # Single DB seeding
        if args.db_url:
            print(f"Connecting to override database: {args.db_url.split('@')[-1]}")
            engine = create_engine(args.db_url)
            session_factory = sessionmaker(bind=engine)
            db = session_factory()
        else:
            db = SessionLocal()

        summary = seed_security_baseline(
            db,
            bootstrap_superuser=args.bootstrap_superuser,
            superuser_username=args.username,
            superuser_email=args.email,
            superuser_password=args.password,
            is_fresh=args.is_fresh
        )
        print(f"Seeding completed: {summary}")

    finally:
        if db: db.close()


if __name__ == "__main__":
    _run_cli()
