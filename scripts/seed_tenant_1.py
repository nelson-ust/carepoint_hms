import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_master_engine
from app.core.cryptography import decrypt_string
from app.core.multitenancy import set_current_tenant, get_current_tenant
from app.models.all_models import (
    Tenant, Role, User, Patient, Facility, VitalSign, Department
)
from app.core.enums import FacilityType, FacilityStatus, UserStatus, Gender

def seed_tenant_1():
    print("Connecting to Master Database...")
    master_engine = get_master_engine()
    
    with Session(master_engine) as master_db:
        tenant = master_db.query(Tenant).filter(Tenant.id == 1).first()
        if not tenant:
            print("Error: Tenant with ID 1 not found in Master DB.")
            return
        
        if not tenant.db_connection_string:
            print("Error: Tenant 1 has no db_connection_string.")
            return

        try:
            db_url = decrypt_string(tenant.db_connection_string)
        except Exception:
            db_url = tenant.db_connection_string

        # Ensure subscription exists so UserService doesn't fail if we were to use it
        from app.models.all_models import TenantSubscription, SubscriptionPlan
        from app.core.enums import SubscriptionStatus
        plan = master_db.query(SubscriptionPlan).first()
        if plan:
            sub = master_db.query(TenantSubscription).filter_by(tenant_id=tenant.id).first()
            if not sub:
                sub = TenantSubscription(
                    tenant_id=tenant.id,
                    subscription_plan_id=plan.id,
                    status=SubscriptionStatus.ACTIVE,
                    start_date=datetime.now(timezone.utc),
                    end_date=datetime.now(timezone.utc) + timedelta(days=365)
                )
                master_db.add(sub)
                master_db.commit()

        print(f"Connecting to Tenant Database: {tenant.name} ({tenant.code})")

    # Set context
    set_current_tenant(tenant)

    # Connect to tenant DB
    tenant_engine = create_engine(db_url, future=True)
    with Session(tenant_engine) as db:
        try:
            # 1. Seed Roles
            print("Seeding Roles...")
            roles_to_create = [
                {"code": "ADMIN", "name": "Administrator", "description": "System Admin"},
                {"code": "DOCTOR", "name": "Doctor", "description": "Medical Doctor"},
                {"code": "NURSE", "name": "Nurse", "description": "Registered Nurse"}
            ]
            for rd in roles_to_create:
                if not db.query(Role).filter_by(code=rd["code"]).first():
                    r = Role(**rd)
                    db.add(r)
            
            # 2. Seed Facility
            print("Seeding Facility...")
            facility = db.query(Facility).first()
            if not facility:
                facility = Facility(
                    name=f"{tenant.name} Main Hospital",
                    facility_type=FacilityType.HOSPITAL,
                    status=FacilityStatus.ACTIVE,
                    is_primary=True,
                    address="123 Health Ave, Medical District",
                    city="Metropolis",
                    country="Country"
                )
                db.add(facility)

            # 3. Seed Department
            print("Seeding Department...")
            department = db.query(Department).first()
            if not department:
                # Flush to ensure facility has an ID
                db.flush()
                department = Department(
                    name="General Medicine",
                    code="GEN-MED",
                    facility_id=facility.id,
                    is_clinical=True,
                    is_active=True
                )
                db.add(department)

            # 5. Seed Patient (Moved up to keep raw ORM together)
            print("Seeding Patient...")
            patient = db.query(Patient).first()
            if not patient:
                import uuid
                patient = Patient(
                    global_patient_id=str(uuid.uuid4()),
                    facility_id=facility.id,
                    hospital_number="MRN-10001",
                    first_name="Jane",
                    last_name="Doe",
                    gender=Gender.FEMALE.value,
                    date_of_birth=datetime(1990, 1, 1).date(),
                    phone_number="0987654321",
                    blood_group="O+",
                    genotype="AA"
                )
                db.add(patient)

            # Commit all raw ORM operations as a single transaction
            db.commit()
            print("Raw ORM seeding committed successfully.")

            # Refresh objects to use in Services
            if facility.id: db.refresh(facility)
            if department.id: db.refresh(department)
            if patient.id: db.refresh(patient)
            doctor_role = db.query(Role).filter_by(code="DOCTOR").first()

        except Exception as e:
            db.rollback()
            print(f"Transaction failed, rolling back raw ORM seeding: {e}")
            return

        # 4. Seed User using Service
        print("Seeding User...")
        from app.services.user_service import UserService
        from app.schemas.user_schema import UserCreateSchema
        from app.core.exceptions import AppException
        
        user_svc = UserService(db)
        doctor = db.query(User).filter_by(username="dr.smith").first()
        if not doctor:
            payload = UserCreateSchema(
                username="dr.smith",
                email="dr.smith@carepointhms.com",
                password="Secure!Password123",
                first_name="John",
                last_name="Smith",
                phone_number="1234567890",
                role_ids=[doctor_role.id] if doctor_role else []
            )
            try:
                # The service will run its own internal commit
                doctor = user_svc.create_user(payload)
                print("Doctor created successfully via UserService.")
            except AppException as e:
                print(f"UserService error: {e.message}")
                from app.core.security import get_password_hash
                doctor = User(
                    username=payload.username,
                    email=payload.email,
                    first_name=payload.first_name,
                    last_name=payload.last_name,
                    phone_number=payload.phone_number,
                    password_hash=get_password_hash(payload.password),
                    status=UserStatus.ACTIVE,
                    is_superuser=False
                )
                db.add(doctor)
                db.commit()

        # 6. Seed Vital Signs
        print("Seeding Vital Signs (with MEWS triggers)...")
        from app.services.vital_sign_service import VitalSignService
        from app.schemas.vital_sign_schema import VitalSignCreateSchema
        
        vital_svc = VitalSignService(db)
        payload = VitalSignCreateSchema(
            patient_id=patient.id,
            recorded_by_id=doctor.id if doctor else None,
            temperature=39.5,
            heart_rate=115,
            respiratory_rate=25,
            systolic_bp=85,
            diastolic_bp=55,
            oxygen_saturation=93,
            consciousness_level="V",
            is_ipd=True,
            notes="Patient appears lethargic, possible sepsis."
        )
        try:
            # The service will run its own internal commit
            vital = vital_svc.create_vital_sign(payload)
            print(f"Vital signs recorded. MEWS Score: {vital.mews_score}")
        except Exception as e:
            print(f"Failed to create vital signs via service: {e}")

        print("Tenant 1 data seeding complete!")

if __name__ == "__main__":
    seed_tenant_1()
