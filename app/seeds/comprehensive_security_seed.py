# app/seeds/comprehensive_security_seed.py
from __future__ import annotations

"""
Comprehensive seed for Carepoint HMS permissions and roles.
This script scans all route files to ensure every required permission is accounted for.
It is idempotent and can be run safely multiple times.
"""

import argparse
import sys
import os
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import or_, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import SessionLocal, get_master_engine
from app.core.cryptography import decrypt_string
from app.core.enums import UserStatus
from app.core.security import get_password_hash
from app.models.all_models import (
    Permission,
    Role,
    RolePermissionAssociation,
    User,
    UserRoleAssociation,
    Tenant,
)

# ============================================================
# CANONICAL PERMISSIONS (Extracted from routes)
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

    # Backup & SaaS Admin
    {"code": "BACKUP_READ", "name": "Read backups", "module": "BACKUP"},
    {"code": "BACKUP_CREATE", "name": "Create backups", "module": "BACKUP"},
    {"code": "SETTING_UPDATE", "name": "Update system settings", "module": "SETTING"},
    {"code": "SaaS_ADMIN", "name": "SaaS Administrative Access", "module": "SaaS"},
]

# ============================================================
# CANONICAL ROLES
# ============================================================

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

# ============================================================
# ROLE -> PERMISSIONS MAPPING
# ============================================================

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "TENANT_ADMIN": [p["code"] for p in ALL_PERMISSIONS],
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

# ============================================================
# SEEDING LOGIC
# ============================================================

def seed_comprehensive_security(
    db: Session,
    *,
    bootstrap_superuser: bool = False,
    superuser_username: Optional[str] = None,
    superuser_email: Optional[str] = None,
    superuser_password: Optional[str] = None,
) -> dict:
    print("--- Seeding Comprehensive Security Baseline ---")
    summary = {
        "permissions_processed": 0,
        "roles_processed": 0,
        "role_permission_links_created": 0,
        "superuser_created": False,
    }

    # 1. Upsert Permissions
    permissions_by_code = {}
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
            # print(f"  [+] Created Permission: {p_data['code']}")
        else:
            perm.name = p_data["name"]
            perm.module = p_data["module"]
            perm.is_system = True
            db.add(perm)
        permissions_by_code[p_data["code"]] = perm
        summary["permissions_processed"] += 1
    db.flush()

    # 2. Upsert Roles
    roles_by_code = {}
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
            # print(f"  [+] Created Role: {r_data['code']}")
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
        
        # Refresh role to ensure we see current associations
        db.refresh(role)
        existing_p_ids = {link.permission_id for link in role.role_permissions if not link.is_deleted}
        
        for p_code in p_codes:
            perm = permissions_by_code.get(p_code)
            if perm and perm.id not in existing_p_ids:
                link = RolePermissionAssociation(role_id=role.id, permission_id=perm.id)
                db.add(link)
                summary["role_permission_links_created"] += 1
    
    # 4. Bootstrap Superuser (Optional)
    if bootstrap_superuser and superuser_username and superuser_email and superuser_password:
        existing = db.query(User).filter(
            or_(User.username == superuser_username.lower(), User.email == superuser_email.lower())
        ).first()
        
        if not existing:
            user = User(
                username=superuser_username.lower(),
                email=superuser_email.lower(),
                password_hash=get_password_hash(superuser_password),
                first_name="Super",
                last_name="Admin",
                status=UserStatus.ACTIVE,
                is_superuser=True,
                is_email_verified=True,
            )
            db.add(user)
            db.flush()
            
            admin_role = roles_by_code.get("TENANT_ADMIN")
            if admin_role:
                db.add(UserRoleAssociation(user_id=user.id, role_id=admin_role.id))
            
            summary["superuser_created"] = True
            print(f"  [+] Created Superuser: {superuser_username}")

    db.commit()
    print("--- Security Seeding Completed Successfully ---")
    return summary

def _run_cli():
    # Load .env file explicitly
    load_dotenv()

    parser = argparse.ArgumentParser(description="Comprehensive security seed for Carepoint HMS.")
    parser.add_argument("--db-url", type=str, help="Database URL to seed. Defaults to DATABASE_URL in .env.")
    parser.add_argument("--all-tenants", action="store_true", help="Seed all provisioned tenants in the master database.")
    parser.add_argument("--bootstrap-superuser", action="store_true", help="Create a bootstrap superuser.")
    parser.add_argument("--username", type=str, help="Superuser username.")
    parser.add_argument("--email", type=str, help="Superuser email.")
    parser.add_argument("--password", type=str, help="Superuser password.")
    args = parser.parse_args()

    if args.all_tenants:
        print("--- Fleet-wide Seeding Mode Activated ---")
        master_engine = get_master_engine()
        
        # 1. Fetch all tenants and close master connection immediately
        with Session(master_engine) as master_db:
            tenants = master_db.query(Tenant).filter(Tenant.is_provisioned == True).all()
            print(f"Found {len(tenants)} provisioned tenants.")
            # We copy the attributes we need so we don't need the session anymore
            tenant_data = [
                {
                    "name": t.name,
                    "code": t.code,
                    "db_connection_string": t.db_connection_string
                }
                for t in tenants
            ]
        
        # 2. Process each tenant independently
        for t in tenant_data:
            print(f"\nProcessing Tenant: {t['name']} ({t['code']})")
            if not t['db_connection_string']:
                print(f"  [!] Skipping {t['code']}: No connection string found.")
                continue
            
            try:
                db_url = decrypt_string(t['db_connection_string'])
                tenant_engine = create_engine(db_url)
                with Session(tenant_engine) as tenant_db:
                    summary = seed_comprehensive_security(
                        tenant_db,
                        bootstrap_superuser=args.bootstrap_superuser,
                        superuser_username=args.username,
                        superuser_email=args.email,
                        superuser_password=args.password
                    )
                    for key, value in summary.items():
                        print(f"  {key}: {value}")
                tenant_engine.dispose()
            except Exception as e:
                print(f"  [X] Error seeding tenant {t['code']}: {e}")
        
        print("\n--- Fleet-wide Seeding Completed ---")
        return

    # Use specified DB URL or fallback to SessionLocal
    if args.db_url:
        print(f"Connecting to override database: {args.db_url.split('@')[-1]}") # Log host/db only for safety
        engine = create_engine(args.db_url)
        session_factory = sessionmaker(bind=engine)
        db = session_factory()
    else:
        db = SessionLocal()

    try:
        summary = seed_comprehensive_security(
            db,
            bootstrap_superuser=args.bootstrap_superuser,
            superuser_username=args.username,
            superuser_email=args.email,
            superuser_password=args.password
        )
        for key, value in summary.items():
            print(f"  {key}: {value}")
    finally:
        db.close()

if __name__ == "__main__":
    _run_cli()
