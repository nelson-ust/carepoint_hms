from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import MasterBase, TenantBase
from app.models.all_models import (
    Tenant, Facility, User, Patient, InterFacilityReferral, 
    InterFacilityAccessGrant, ReferralStatus, UserStatus
)

# Use in-memory SQLite for model unit tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    MasterBase.metadata.create_all(bind=engine)
    TenantBase.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        MasterBase.metadata.drop_all(bind=engine)
        TenantBase.metadata.drop_all(bind=engine)

def test_tenant_and_facility_relationship(db):
    # Create tenant
    tenant = Tenant(
        name="ABC Hospital Group",
        code="ABC",
        domain_url="abc.carepointhms.com",
        db_name="carepoint_abc",
        status=UserStatus.ACTIVE
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    # Create facility (in a real system, this would be in the tenant DB)
    facility = Facility(
        code="ABC-MAIN",
        name="ABC Main Hospital",
    )
    db.add(facility)
    db.commit()
    db.refresh(facility)

    assert facility.code == "ABC-MAIN"
    assert tenant.code == "ABC"

def test_patient_global_id_and_tenant(db):
    tenant = Tenant(
        name="Test Tenant",
        code="TST",
        domain_url="test.local",
        db_name="test_db"
    )
    db.add(tenant)
    db.commit()

    patient = Patient(
        global_patient_id="GLOBAL-123",
        hospital_number="HOSP-123",
        first_name="John",
        last_name="Doe"
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    assert patient.global_patient_id == "GLOBAL-123"

def test_inter_facility_referral_workflow(db):
    # Setup two tenants
    t1 = Tenant(name="Tenant 1", code="T1", domain_url="t1.local", db_name="db1")
    t2 = Tenant(name="Tenant 2", code="T2", domain_url="t2.local", db_name="db2")
    db.add_all([t1, t2])
    db.commit()

    # Setup facilities (in real system, these are in tenant DBs)
    f1 = Facility(code="F1", name="Facility 1")
    f2 = Facility(code="F2", name="Facility 2")
    db.add_all([f1, f2])
    db.commit()

    # Setup patient
    patient = Patient(global_patient_id="G-PAT-1", hospital_number="P1", first_name="P", last_name="1")
    db.add(patient)
    db.commit()

    # Create inter-facility referral
    referral = InterFacilityReferral(
        referral_no="REF-001",
        source_tenant_id=t1.id,
        source_facility_id=f1.id,
        target_tenant_id=t2.id,
        target_facility_id=f2.id,
        patient_global_id="G-PAT-1",
        reason_for_referral="Need specialized surgery",
        status=ReferralStatus.PENDING
    )
    db.add(referral)
    db.commit()
    db.refresh(referral)

    assert referral.status == ReferralStatus.PENDING
    
    # Accept referral
    referral.status = ReferralStatus.ACCEPTED
    referral.is_history_access_granted = True
    referral.access_expires_at = datetime.utcnow() + timedelta(days=30)
    db.commit()

    # Verify access grant could be created
    grant = InterFacilityAccessGrant(
        referral_id=referral.id,
        patient_global_id="G-PAT-1",
        source_tenant_id=t1.id,
        target_tenant_id=t2.id,
        expires_at=referral.access_expires_at
    )
    db.add(grant)
    db.commit()

    assert grant.target_tenant_id == t2.id
    assert grant.is_active is True
