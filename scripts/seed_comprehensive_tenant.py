# scripts/seed_comprehensive_tenant.py
import os
import sys
import traceback
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# Ensure app is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_master_engine
from app.core.cryptography import decrypt_string
from app.core.multitenancy import set_current_tenant
from app.models.all_models import (
    Tenant, Role, Facility, FacilityNetwork, FacilityServiceArea, 
    Department, ServiceDeliveryPoint, Ward, Bed, Patient, User, 
    BillableService, RadiologyProcedureCatalog, ProcedureCatalog, Prescription, Admission,
    LeaveType, InventoryStore, InventoryStockItem, LabTestCatalog, Appointment, StaffProfile,
    Visit, QueueTicket, TriageAssessment, VitalSign, Consultation, Diagnosis,
    LabOrder, LabOrderItem, RadiologyOrder, RadiologyOrderItem, ProcedureOrder,
    Billing, BillingItem, Invoice, Payment, DrugCategory, Drug
)
from app.core.enums import (
    FacilityType, FacilityStatus, UserStatus, Gender, QueueStatus, ServicePointType,
    InventoryItemType, StockMovementType, MedicationFrequency, MedicationDoseStatus,
    VisitPriority, BillingStatus, InvoiceStatus, PaymentStatus, OrderStatus,
    RadiologyModality, AmbulanceStatus, LeaveStatus, AppointmentStatus, AdmissionStatus,
    VisitStatus
)

def get_tenant_from_input():
    """Prompt the user for a Tenant ID or Code."""
    print("\n--- Tenant Selection ---")
    val = input("Enter Tenant ID or Tenant Code (leave blank for ID 1): ").strip()
    return val if val else "1"

def seed_tenant_full():
    """
    Seeds an extensive, multi-record dataset for a specific tenant.
    Captures full clinical flows, multiple departments, staff coverage, and queues.
    Now includes Facility Networks and Service Areas.
    """
    master_engine = get_master_engine()
    tenant_input = get_tenant_from_input()
    
    with Session(master_engine) as master_session:
        # Resolve Tenant
        query = master_session.query(Tenant)
        if tenant_input.isdigit():
            tenant = query.filter(Tenant.id == int(tenant_input)).first()
        else:
            tenant = query.filter(Tenant.code.ilike(tenant_input)).first()
            
        if not tenant:
            print(f"Error: Tenant '{tenant_input}' not found.")
            return

        print(f"Connecting to Database for Tenant: {tenant.name} ({tenant.code})...")
        
        # Decrypt connection string and set context
        db_url = decrypt_string(tenant.db_connection_string)
        # Using NullPool for seeding
        from sqlalchemy.pool import NullPool
        tenant_engine = create_engine(db_url, poolclass=NullPool)
        # Detach the ORM object so it survives the session close, then set the
        # full Tenant object as context (set_current_tenant expects the object,
        # not the bare id — get_current_tenant_id() reads `.id` from it).
        master_session.expunge(tenant)
        set_current_tenant(tenant)

    try:
        with Session(tenant_engine) as db:
            print("\n--- Starting Extensive Seeding ---")
            
            # 1. FACILITY NETWORK
            print("1. Seeding Facility Network...")
            from app.services.facility_service import FacilityService
            from app.schemas.facility_schemas import (
                FacilityNetworkCreate, FacilityCreate, FacilityServiceAreaCreate
            )
            fac_svc = FacilityService(db)
            
            network = db.query(FacilityNetwork).filter_by(code="CP-NET").first()
            if not network:
                network = fac_svc.create_network(FacilityNetworkCreate(
                    name="Carepoint Global Network",
                    code="CP-NET",
                    description="The primary healthcare network for Carepoint HMS."
                ))
                print(f"   Created Network: {network.name}")

            # 2. FACILITY & INFRASTRUCTURE
            print("2. Seeding Facility & Departments...")
            facility = db.query(Facility).filter_by(code="MAIN-HOSP").first()
            if not facility:
                facility = fac_svc.create_facility(FacilityCreate(
                    name="Carepoint Central Hospital", 
                    code="MAIN-HOSP",
                    facility_type=FacilityType.MAIN_HOSPITAL, 
                    status=FacilityStatus.ACTIVE,
                    network_id=network.id,
                    address_line_1="123 Health Way",
                    city="Lagos",
                    state="Lagos",
                    country="Nigeria"
                ))
                print(f"   Created Facility: {facility.name}")
            else:
                # Update network if not set
                if not facility.network_id:
                    facility.network_id = network.id
                    db.flush()

            # 3. FACILITY SERVICE AREAS
            print("3. Seeding Facility Service Areas...")
            areas_data = [
                ("Lagos Central", "NG-LA-CEN", "Covers the mainland and island central areas."),
                ("Lagos East", "NG-LA-EST", "Covers Ibeju-Lekki and surrounding axes."),
                ("Lagos West", "NG-LA-WST", "Covers Ikeja and Alimosho axes.")
            ]
            for name, code, notes in areas_data:
                area = db.query(FacilityServiceArea).filter_by(area_name=name, facility_id=facility.id).first()
                if not area:
                    fac_svc.create_service_area(FacilityServiceAreaCreate(
                        facility_id=facility.id,
                        area_name=name,
                        region_code=code,
                        notes=notes
                    ))
            print(f"   Seeded {len(areas_data)} Service Areas for {facility.name}")

            # 4. DEPARTMENTS
            print("4. Seeding Departments...")
            depts_data = [
                ("Internal Medicine", "INT-MED"),
                ("Surgery", "SURG"),
                ("Pediatrics", "PEDS"),
                ("Diagnostics", "DIAG"),
                ("Pharmacy", "PHARM"),
                ("Administration", "ADMIN")
            ]
            depts = {}
            for name, code in depts_data:
                d = db.query(Department).filter_by(code=code).first()
                if not d:
                    d = Department(name=name, code=code, facility_id=facility.id)
                    db.add(d)
                depts[code] = d
            db.flush()

            # 5. SERVICE DELIVERY POINTS (SDPs)
            print("5. Seeding Service Delivery Points (SDPs)...")
            sdps_data = [
                ("Main Reception", "REC-01", ServicePointType.REGISTRATION, "ADMIN", True, True),
                ("Triage Center", "TRI-01", ServicePointType.TRIAGE, "INT-MED", False, True),
                ("General Clinic", "CLIN-GEN", ServicePointType.CLINIC, "INT-MED", True, True),
                ("Specialist Clinic", "CLIN-SPEC", ServicePointType.CLINIC, "INT-MED", True, False),
                ("Main Laboratory", "LAB-01", ServicePointType.LABORATORY, "DIAG", False, True),
                ("Radiology Suite", "RAD-01", ServicePointType.RADIOLOGY, "DIAG", True, True),
                ("Main Pharmacy", "PHARM-01", ServicePointType.PHARMACY, "PHARM", False, True),
                ("Surgical Theatre", "THE-01", ServicePointType.THEATRE, "SURG", True, False),
            ]
            sdps = {}
            for name, code, sp_type, d_code, appt, walkin in sdps_data:
                s = db.query(ServiceDeliveryPoint).filter_by(code=code).first()
                if not s:
                    s = ServiceDeliveryPoint(
                        name=name, code=code, service_point_type=sp_type,
                        facility_id=facility.id, department_id=depts[d_code].id,
                        supports_appointments=appt, supports_walk_in=walkin
                    )
                    db.add(s)
                sdps[code] = s
            db.flush()

            # 6. ROLES & STAFF
            print("6. Seeding Extensive Staff Coverage...")
            roles = {r.code: r for r in db.query(Role).all()}
            from app.services.staff_profile_service import StaffProfileService
            from app.schemas.staff_profile_schemas import UserCreateSchema, StaffProfileCreateSchema
            sp_svc = StaffProfileService(db)

            # Use a common secure password
            SECURE_PWD = "Carepoint@2026"

            staff_to_seed = [
                ("reception.alice", "Alice", "Receptionist", "ADMIN", "REC-01", ["RECEPTIONIST"]),
                ("reception.bob", "Bob", "FrontDesk", "ADMIN", "REC-01", ["RECEPTIONIST"]),
                ("dr.house", "Gregory", "House", "INT-MED", "CLIN-SPEC", ["DOCTOR"]),
                ("dr.strange", "Stephen", "Strange", "SURG", "THE-01", ["DOCTOR"]),
                ("dr.watson", "John", "Watson", "INT-MED", "CLIN-GEN", ["DOCTOR"]),
                ("nurse.joy", "Joy", "Nurse", "INT-MED", "TRI-01", ["NURSE"]),
                ("nurse.nightingale", "Florence", "Nightingale", "INT-MED", "TRI-01", ["NURSE"]),
                ("lab.dexter", "Dexter", "Lab", "DIAG", "LAB-01", ["LAB_TECHNICIAN"]),
                ("pharm.walter", "Walter", "White", "PHARM", "PHARM-01", ["PHARMACIST"]),
            ]
            staff_members = {}
            for username, f_name, l_name, d_code, s_code, role_codes in staff_to_seed:
                user = db.query(User).filter_by(username=username).first()
                if not user:
                    user = sp_svc.create_user_with_staff_profile(UserCreateSchema(
                        username=username, email=f"{username}@hospital.com", password=SECURE_PWD,
                        first_name=f_name, last_name=l_name, phone_number=f"080{random.randint(1000000, 9999999)}",
                        role_ids=[roles[rc].id for rc in role_codes if rc in roles],
                        staff_profile=StaffProfileCreateSchema(
                            staff_no=f"STF-{username.replace('.', '-').upper()}-{random.randint(100, 999)}",
                            department_id=depts[d_code].id,
                            facility_id=facility.id,
                            service_delivery_point_id=sdps[s_code].id,
                            job_title=l_name
                        )
                    ))
                staff_members[username] = db.query(StaffProfile).filter_by(user_id=user.id).first()
            db.flush()

            # 7. PATIENTS
            print("7. Seeding Multiple Patients...")
            from app.services.patient_service import PatientService
            from app.schemas.patient_schemas import PatientCreateSchema
            p_svc = PatientService(db)
            
            patients_data = [
                ("John", "Wick", "john.wick@continental.com", Gender.MALE),
                ("Jane", "Doe", "jane.doe@example.com", Gender.FEMALE),
                ("Bob", "Smith", "bob.smith@example.com", Gender.MALE),
                ("Alice", "Wonder", "alice.w@example.com", Gender.FEMALE),
                ("Bruce", "Wayne", "bruce.w@waynecorp.com", Gender.MALE),
            ]
            patients = []
            for f_name, l_name, email, gender in patients_data:
                p = db.query(Patient).filter_by(email=email).first()
                if not p:
                    p = p_svc.create_patient(PatientCreateSchema(
                        first_name=f_name, last_name=l_name, email=email,
                        date_of_birth=datetime(random.randint(1960, 2010), 1, 1).date(),
                        gender=gender.value if hasattr(gender, 'value') else gender, 
                        phone_number=f"070{random.randint(1000000, 9999999)}",
                        address=f"{random.randint(1, 100)} Hospital Road"
                    ))
                patients.append(p)
            db.flush()

            # 8. CATALOG DATA
            print("8. Seeding Expanded Catalogs...")
            from app.services.billing_service import BillableServiceService
            from app.schemas.billing_schemas import BillableServiceCreateSchema
            bs_svc = BillableServiceService(db)
            services_data = [
                ("General Consultation", "CONS-001", "CLINICAL", "50.00"),
                ("Specialist Consultation", "CONS-SPEC", "CLINICAL", "150.00"),
                ("Emergency Consultation", "CONS-EMER", "CLINICAL", "200.00"),
                ("Nursing Assessment", "NURS-001", "NURSING", "10.00"),
                ("Theater Fee", "THEA-001", "SURGERY", "1000.00"),
            ]
            services = {}
            for name, code, cat, price in services_data:
                s = db.query(BillableService).filter_by(code=code).first()
                if not s:
                    s = bs_svc.create(BillableServiceCreateSchema(
                        name=name, code=code, category=cat, default_price=Decimal(price)
                    ))
                services[code] = s

            # Drugs
            from app.services.drug_service import DrugCategoryService, DrugService
            from app.schemas.drug_schema import DrugCategoryCreateSchema, DrugCreateSchema
            dc_svc = DrugCategoryService(db)
            d_svc = DrugService(db)
            
            antibiotics = db.query(DrugCategory).filter_by(code="ANTI").first() or dc_svc.create(DrugCategoryCreateSchema(name="Antibiotics", code="ANTI"))
            analgesics = db.query(DrugCategory).filter_by(code="ANAL").first() or dc_svc.create(DrugCategoryCreateSchema(name="Analgesics", code="ANAL"))
            
            drugs_to_seed = [
                ("Amoxicillin 500mg", "ANTI", "15.00"),
                ("Ciprofloxacin 500mg", "ANTI", "25.00"),
                ("Paracetamol 500mg", "ANAL", "2.00"),
                ("Ibuprofen 400mg", "ANAL", "5.00"),
                ("Aspirin 100mg", "ANAL", "3.00"),
            ]
            drugs = []
            for name, cat_code, price in drugs_to_seed:
                dr = db.query(Drug).filter_by(name=name).first()
                if not dr:
                    cat = antibiotics if cat_code == "ANTI" else analgesics
                    dr = d_svc.create(DrugCreateSchema(
                        name=name, drug_category_id=cat.id, unit_price=Decimal(price), reorder_level=Decimal("50")
                    ))
                drugs.append(dr)

            # Lab Tests
            from app.services.lab_service import LabCatalogService
            from app.schemas.lab_schema import LabTestCatalogCreateSchema
            lcat_svc = LabCatalogService(db)
            lab_tests = [
                ("MAL-01", "Malaria Parasite", "20.00"),
                ("FBC-01", "Full Blood Count", "40.00"),
                ("WID-01", "Widal Test", "15.00"),
                ("GLU-01", "Glucose Test", "10.00"),
            ]
            test_catalogs = []
            for code, name, price in lab_tests:
                t = db.query(LabTestCatalog).filter_by(code=code).first()
                if not t:
                    t = lcat_svc.create(LabTestCatalogCreateSchema(code=code, name=name, default_price=Decimal(price)))
                test_catalogs.append(t)

            # 9. QUEUES & VISITS
            print("9. Seeding Active Clinic Queues & Multi-Patient Journeys...")
            from app.services.visit_service import VisitService
            from app.schemas.visit_schemas import VisitInitiateSchema
            v_svc = VisitService(db)
            
            # Journey 1: Patient 3 (Bob Smith) - Waiting at Reception
            active_bob, _ = v_svc.list_visits(patient_id=patients[2].id)
            if not [v for v in active_bob if v.status not in [VisitStatus.COMPLETED, VisitStatus.CANCELLED]]:
                v_svc.initiate_visit(VisitInitiateSchema(
                    patient_id=patients[2].id, first_service_delivery_point_id=sdps["REC-01"].id,
                    visit_reason="New Registration", create_queue_ticket=True, first_queue_status="WAITING"
                ))

            # Journey 2: Patient 4 (Alice Wonder) - Waiting at Triage
            active_alice, _ = v_svc.list_visits(patient_id=patients[3].id)
            if not [v for v in active_alice if v.status not in [VisitStatus.COMPLETED, VisitStatus.CANCELLED]]:
                v_svc.initiate_visit(VisitInitiateSchema(
                    patient_id=patients[3].id, first_service_delivery_point_id=sdps["TRI-01"].id,
                    visit_reason="Fever", create_queue_ticket=True, first_queue_status="WAITING"
                ))

            # Journey 3: Patient 2 (Jane Doe) - In Consultation with Dr. Watson
            active_jane, _ = v_svc.list_visits(patient_id=patients[1].id)
            if not [v for v in active_jane if v.status not in [VisitStatus.COMPLETED, VisitStatus.CANCELLED]]:
                v_svc.initiate_visit(VisitInitiateSchema(
                    patient_id=patients[1].id, first_service_delivery_point_id=sdps["CLIN-GEN"].id,
                    visit_reason="General Checkup", create_queue_ticket=True, first_queue_status="SERVING"
                ))
            
            # Journey 4: Patient 1 (John Wick) - Complex Journey
            print("10. Seeding Complex Journey (John Wick)...")
            from app.services.appointment_service import AppointmentService
            from app.schemas.appointment_schemas import AppointmentCreateSchema
            appt_svc = AppointmentService(db)
            
            existing_visits, _ = v_svc.list_visits(patient_id=patients[0].id)
            if not existing_visits:
                appt = appt_svc.book_appointment(AppointmentCreateSchema(
                    patient_id=patients[0].id, facility_id=facility.id, 
                    service_delivery_point_id=sdps["CLIN-SPEC"].id,
                    scheduled_start_at=datetime.now(timezone.utc) - timedelta(hours=1),
                    reason="Severe chronic pain"
                ))
                
                v_res_john = v_svc.initiate_visit(VisitInitiateSchema(
                    patient_id=patients[0].id, appointment_id=appt.id,
                    first_service_delivery_point_id=sdps["TRI-01"].id,
                    visit_reason="Follow-up on pain", create_queue_ticket=True
                ))
                visit_john = v_res_john["visit"]

                from app.services.triage_service import TriageService
                from app.services.vital_sign_service import VitalSignService
                from app.schemas.triage_schema import TriageCreateSchema
                from app.schemas.vital_sign_schema import VitalSignCreateSchema
                TriageService(db).create(TriageCreateSchema(
                    visit_id=visit_john.id, chief_complaint="Worsening pain", priority="HIGH", 
                    assessed_by_staff_id=staff_members["nurse.joy"].id
                ))
                VitalSignService(db).create(VitalSignCreateSchema(
                    patient_id=patients[0].id, visit_id=visit_john.id, temperature=38.5, heart_rate=110
                ))

                # Triage complete -> route the patient to the specialist clinic.
                # Consultations are only valid at CLINIC/EMERGENCY/WARD SDPs, so
                # the visit must leave the TRIAGE point first.
                from app.schemas.visit_schemas import VisitRerouteSchema
                v_svc.reroute_visit(visit_john.id, VisitRerouteSchema(
                    service_delivery_point_id=sdps["CLIN-SPEC"].id,
                    reason="Triage complete - refer to specialist clinic",
                    create_queue_ticket=True,
                ))

                from app.services.consultation_service import ConsultationService
                from app.services.diagnosis_service import DiagnosisService
                from app.schemas.consultation_schema import ConsultationCreateSchema
                from app.schemas.diagnosis_schema import DiagnosisCreateSchema
                con_john = ConsultationService(db).create(ConsultationCreateSchema(
                    visit_id=visit_john.id, clinician_staff_id=staff_members["dr.house"].id,
                    subjective_note="Patient reports localized pain in ribs.", assessment_note="Potential fracture."
                ))
                DiagnosisService(db).create(DiagnosisCreateSchema(
                    visit_id=visit_john.id, consultation_id=con_john.id, diagnosis_name="Chest trauma", diagnosis_type="PROVISIONAL"
                ))

                # Lab Order
                from app.services.lab_order_service import LabOrderService
                from app.schemas.lab_order_schema import LabOrderCreateSchema, LabOrderItemCreateSchema
                LabOrderService(db).create_order(LabOrderCreateSchema(
                    visit_id=visit_john.id, consultation_id=con_john.id, items=[LabOrderItemCreateSchema(lab_test_catalog_id=test_catalogs[0].id)]
                ))

                # Admission
                from app.services.ward_service import WardService
                from app.services.bed_service import BedService
                from app.schemas.ward_schemas import WardCreateSchema
                from app.schemas.bed_schemas import BedCreateSchema
                ward = db.query(Ward).filter_by(code="WARD-A").first() or WardService(db).create_ward(WardCreateSchema(
                    name="Executive Ward", code="WARD-A", facility_id=facility.id, department_id=depts["INT-MED"].id, capacity=5
                ))
                bed = db.query(Bed).filter_by(ward_id=ward.id, bed_status="AVAILABLE").first() or BedService(db).create_bed(BedCreateSchema(
                    ward_id=ward.id, bed_no="SUITE-01", bed_status="AVAILABLE"
                ))
                
                from app.services.admission_service import AdmissionService
                from app.schemas.admission_schemas import AdmissionCreateSchema
                AdmissionService(db).admit(AdmissionCreateSchema(
                    patient_id=patients[0].id, visit_id=visit_john.id, ward_id=ward.id, bed_id=bed.id,
                    admission_reason="Close observation for chest trauma."
                ))

            db.commit()
            print("\nExtensive Seeding Finished SUCCESSFULLY!")

    except Exception as e:
        if 'db' in locals():
            db.rollback()
        print("\nSEEDING FAILED!")
        traceback.print_exc()
    finally:
        if 'tenant_engine' in locals():
            tenant_engine.dispose()

if __name__ == "__main__":
    seed_tenant_full()
