# scripts/seed_sample_clinical_data.py
"""
Seed COMPLETE sample clinical data into a tenant database so the clinical
features (Patient 360, chronic problem list, progress analytics, baseline
diagnostics) have realistic data to render.

Every record is populated against the FULL payload the corresponding
Pydantic schema / SQLAlchemy model defines, so the seeded data exercises
every field a real registration / staff-onboarding / baseline capture would.

For a chosen tenant this seeds, idempotently:

  * reference data: a main-hospital Facility, a standard Department set,
    two InsuranceProviders (a private HMO and a corporate retainer), and a
    loyalty programme;
  * care-pathway templates (the standard outpatient visit-flow) and a few
    clinical note templates (SOAP);
  * a full staff roster for a Nigerian tertiary hospital (doctors, nurses,
    lab scientists, pharmacists, accountants, cashiers, front desk, HR, HMO
    desk, radiology, theatre) - each with department, facility, workstation,
    job title, specialty and professional licence;
  * several fully-registered sample patients (complete demographics, patient
    class, contacts, next-of-kin, national ID, insurance enrolment);
  * a complete baseline diagnostic profile per patient;
  * a chronic problem list per patient (hypertension, diabetes, asthma, ...);
  * a longitudinal series of dated visits + vital signs per patient, shaped
    so the trend analytics show a clear improving / stable / worsening signal.

Usage
-----
    python scripts/seed_sample_clinical_data.py --tenant STMARYS
    python scripts/seed_sample_clinical_data.py --tenant 1

Re-running is safe: every record is upserted by a natural key.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.cryptography import decrypt_string
from app.core.database import get_master_engine
from app.core.enums import (
    FacilityStatus,
    FacilityType,
    Gender,
    PatientClass,
    ProblemStatus,
    ServicePointType,
    VisitPriority,
    VisitStatus,
)
from app.core.multitenancy import set_current_tenant
from app.models.all_models import (
    ClinicalTemplate,
    Department,
    Facility,
    InsuranceProvider,
    LoyaltyProgram,
    Patient,
    PatientBaselineProfile,
    PatientProblem,
    Role,
    ServiceDeliveryPoint,
    Tenant,
    User,
    Visit,
    VitalSign,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _d(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


# ==========================================================================
# Reference data: facility, departments, insurance providers, loyalty
# ==========================================================================

FACILITY = {
    "code": "MAIN-HOSP",
    "name": "CarePoint Teaching Hospital",
    "facility_type": FacilityType.MAIN_HOSPITAL,
    "status": FacilityStatus.ACTIVE,
    "address_line_1": "1 Teaching Hospital Road",
    "address_line_2": "Idi-Araba",
    "city": "Lagos",
    "state": "Lagos",
    "country": "Nigeria",
    "postal_code": "100254",
    "phone_number": "+2340123456789",
    "email": "info@carepointhms.com",
    "website": "https://carepointhms.com",
    "timezone": "Africa/Lagos",
    "license_number": "FMOH/TERT/2019/0456",
    "tax_identification_no": "TIN-20345678-0001",
    "bed_capacity": 450,
    "notes": "Sample main teaching-hospital facility seeded for demo data.",
}

# (code, name, description)
DEPARTMENTS = [
    ("ADMIN", "Administration", "Executive and hospital administration."),
    ("RECORDS", "Medical Records", "Health information and records management."),
    ("FRONTDESK", "Front Desk / Registration", "Patient registration and reception."),
    ("GOPD", "General Outpatient", "General outpatient clinics."),
    ("INTMED", "Internal Medicine", "Adult internal medicine and cardiology."),
    ("PAEDS", "Paediatrics", "Child health and paediatric clinics."),
    ("OANDG", "Obstetrics & Gynaecology", "Maternal health and gynaecology."),
    ("SURGERY", "Surgery", "General and specialist surgery."),
    ("THEATRE", "Theatre & Anaesthesia", "Operating theatres and anaesthesia."),
    ("NURSING", "Nursing Services", "Ward and clinic nursing services."),
    ("LAB", "Laboratory", "Medical laboratory services."),
    ("RADIOLOGY", "Radiology", "Diagnostic imaging services."),
    ("PHARMACY", "Pharmacy", "Pharmaceutical services and dispensing."),
    ("ACCOUNTS", "Finance & Accounts", "Billing, cashiering and accounts."),
    ("HMO", "HMO / Insurance Desk", "Claims and insurance verification."),
    ("HR", "Human Resources", "Workforce and personnel management."),
    ("ICT", "Information Technology", "Hospital information systems."),
]

# (service_point_type, name, code, department_code, queue_prefix)
SERVICE_POINTS = [
    (ServicePointType.REGISTRATION, "Registration Desk", "SDP-REG", "FRONTDESK", "REG"),
    (ServicePointType.INSURANCE_CONFIRMATION, "HMO / Insurance Desk", "SDP-INS", "HMO", "INS"),
    (ServicePointType.TRIAGE, "Triage / Vitals Station", "SDP-TRIAGE", "NURSING", "TRI"),
    (ServicePointType.CLINIC, "General Outpatient Clinic", "SDP-GOPD", "GOPD", "CON"),
    (ServicePointType.LABORATORY, "Main Laboratory", "SDP-LAB", "LAB", "LAB"),
    (ServicePointType.RADIOLOGY, "Radiology / Imaging", "SDP-RAD", "RADIOLOGY", "RAD"),
    (ServicePointType.PHARMACY, "Main Pharmacy", "SDP-PHARM", "PHARMACY", "PHM"),
    (ServicePointType.CASHIER, "Billing / Cashier", "SDP-CASH", "ACCOUNTS", "PAY"),
    (ServicePointType.WARD, "Inpatient Ward", "SDP-WARD", "NURSING", "WRD"),
    (ServicePointType.THEATRE, "Operating Theatre", "SDP-THEATRE", "THEATRE", "OTH"),
]

INSURANCE_PROVIDERS = [
    {
        "key": "HMO",
        "name": "Hygeia HMO",
        "code": "HYGEIA",
        "provider_type": "PRIVATE_HMO",
        "contact_person": "Provider Relations Desk",
        "phone_number": "+2348000000001",
        "email": "providers@hygeiahmo.example.com",
        "address": "Plot 15, Adeola Odeku, Victoria Island, Lagos",
        "nhia_accreditation_no": "NHIA/HMO/0021",
        "default_payment_terms_days": 45,
        "capitation_supported": True,
        "fee_for_service_supported": True,
        "notes": "Sample private HMO provider.",
    },
    {
        "key": "RETAINER",
        "name": "Dangote Group Staff Retainership",
        "code": "DANGOTE-RET",
        "provider_type": "CORPORATE_RETAINER",
        "contact_person": "Corporate Health Desk",
        "phone_number": "+2348000000002",
        "email": "healthdesk@dangote-retainer.example.com",
        "address": "1 Alfred Rewane Road, Ikoyi, Lagos",
        "nhia_accreditation_no": None,
        "default_payment_terms_days": 30,
        "capitation_supported": False,
        "fee_for_service_supported": True,
        "notes": "Sample corporate retainership account.",
    },
]

LOYALTY_PROGRAM = {
    "name": "CarePoint Rewards",
    "code": "CP-REWARDS",
    "description": "Sample patient loyalty programme.",
    "points_per_currency_unit": Decimal("0.01"),
    "minimum_redemption_points": Decimal("500"),
    "is_auto_enroll": False,
}


def seed_reference_data(db: Session) -> dict:
    """Resolve-or-create facility, departments, service delivery points,
    insurance providers and a loyalty programme; return a lookup dict used by
    the staff / patient seeders. All lookups match on code OR name so the
    seeder reuses whatever the tenant already provisioned instead of colliding
    on a unique constraint."""
    print("  Reference: facility ...")
    facility = db.query(Facility).filter(
        or_(Facility.code == FACILITY["code"], Facility.name == FACILITY["name"])
    ).first()
    if facility is None:
        facility = Facility(**FACILITY)
        db.add(facility)
        db.flush()

    print("  Reference: departments ...")
    dept_ids: dict[str, int] = {}
    for code, name, desc in DEPARTMENTS:
        dept = db.query(Department).filter(
            or_(Department.code == code, Department.name == name)
        ).first()
        if dept is None:
            dept = Department(
                code=code, name=name, description=desc, facility_id=facility.id
            )
            db.add(dept)
            db.flush()
        dept_ids[code] = dept.id

    print("  Reference: service delivery points ...")
    for sp_type, name, code, dept_code, prefix in SERVICE_POINTS:
        # Reuse any existing (non-deleted) point of this type; only create one
        # when the tenant has none, to avoid duplicate workstations.
        existing_sdp = db.query(ServiceDeliveryPoint).filter(
            ServiceDeliveryPoint.is_deleted.is_(False),
            or_(
                ServiceDeliveryPoint.code == code,
                ServiceDeliveryPoint.service_point_type == sp_type,
            ),
        ).first()
        if existing_sdp is None:
            db.add(ServiceDeliveryPoint(
                name=name,
                code=code,
                service_point_type=sp_type,
                facility_id=facility.id,
                department_id=dept_ids.get(dept_code),
                location_description=name,
                queue_prefix=prefix,
                supports_appointments=True,
                supports_walk_in=True,
            ))
    db.flush()

    print("  Reference: insurance providers ...")
    provider_ids: dict[str, int] = {}
    for prov in INSURANCE_PROVIDERS:
        existing = db.query(InsuranceProvider).filter(
            or_(
                InsuranceProvider.code == prov["code"],
                InsuranceProvider.name == prov["name"],
            )
        ).first()
        if existing is None:
            existing = InsuranceProvider(
                name=prov["name"],
                code=prov["code"],
                provider_type=prov["provider_type"],
                contact_person=prov["contact_person"],
                phone_number=prov["phone_number"],
                email=prov["email"],
                address=prov["address"],
                nhia_accreditation_no=prov["nhia_accreditation_no"],
                default_payment_terms_days=prov["default_payment_terms_days"],
                capitation_supported=prov["capitation_supported"],
                fee_for_service_supported=prov["fee_for_service_supported"],
                notes=prov["notes"],
            )
            db.add(existing)
            db.flush()
        provider_ids[prov["key"]] = existing.id

    print("  Reference: loyalty programme ...")
    loyalty = db.query(LoyaltyProgram).filter(
        or_(
            LoyaltyProgram.code == LOYALTY_PROGRAM["code"],
            LoyaltyProgram.name == LOYALTY_PROGRAM["name"],
        )
    ).first()
    if loyalty is None:
        loyalty = LoyaltyProgram(**LOYALTY_PROGRAM)
        db.add(loyalty)
        db.flush()

    db.commit()
    return {
        "facility_id": facility.id,
        "departments": dept_ids,
        "providers": provider_ids,
        "loyalty_program_id": loyalty.id,
    }


# ==========================================================================
# Sample patients
# ==========================================================================
# Each patient carries: full registration fields, a complete baseline
# profile, a chronic problem list, and a series of dated vitals (oldest
# first) engineered to produce a clear trend for the Patient 360 analytics.

SAMPLE_PATIENTS = [
    {
        "first_name": "Amaka", "middle_name": "Chidera", "last_name": "Okafor",
        "email": "amaka.okafor@example.com", "gender": Gender.FEMALE,
        "marital_status": "MARRIED",
        "dob": "1968-04-12", "phone": "07030000101", "alt_phone": "08030000101",
        "address": "14 Awolowo Road, Ikoyi", "city": "Lagos", "state": "Lagos",
        "country": "Nigeria",
        "patient_class": PatientClass.HMO,
        "payer_type": "HMO",
        "national_identifier": "12345678901", "national_identifier_type": "NIN",
        "allergies": "Penicillin (rash)",
        "emergency_contact": ("Emeka Okafor", "07030000199", "Husband"),
        "next_of_kin": ("Emeka Okafor", "07030000199", "Husband",
                        "14 Awolowo Road, Ikoyi, Lagos"),
        "registration_notes": "Referred from company HMO for hypertension follow-up.",
        "insurance_key": "HMO",
        "insurance": {
            "policy_number": "HYG-0001-2024", "member_id": "HYG-M-77012",
            "plan_name": "Hygeia Gold", "status": "ACTIVE",
            "valid_from": "2024-01-01", "valid_to": "2026-12-31",
            "coverage_details": {"co_pay_percentage": 10, "annual_limit": 2000000},
            "note": "Primary corporate HMO cover.",
        },
        "baseline": {
            "rhesus_factor": "Positive", "g6pd_status": "Normal",
            "hepatitis_b_status": "Negative", "hepatitis_c_status": "Negative",
            "hiv_status": "Negative",
            "blood_group": "O+", "genotype": "AA",
            "blood_sugar_baseline": "FBS 5.4 mmol/L",
            "lipid_profile_baseline": "TC 5.1, LDL 3.0, HDL 1.3, TG 1.4 mmol/L",
            "known_allergies": "Penicillin (rash)",
            "chronic_conditions": "Essential hypertension",
            "existing_diagnoses": "Essential hypertension (I10)",
            "long_term_medications": "Amlodipine 10mg daily",
            "past_medical_history": "Diagnosed hypertensive 2019. No prior admissions.",
            "past_surgical_history": "Appendectomy (1995).",
            "family_history": "Mother hypertensive; father type 2 diabetic.",
            "social_history": "Non-smoker. Occasional alcohol. Civil servant.",
            "immunization_history": "COVID-19 fully vaccinated; tetanus up to date.",
            "obstetric_history": "G3P3, all spontaneous vaginal deliveries.",
            "disability_info": "None.",
            "organ_donor": False,
            "baseline_height_cm": Decimal("164"), "baseline_weight_kg": Decimal("92"),
            "additional_notes": "Compliant with medication; monitors BP at home.",
        },
        "problems": [
            {"condition_name": "Essential hypertension", "condition_code": "I10",
             "category": "Cardiovascular", "status": ProblemStatus.IMPROVING,
             "severity": "MODERATE", "onset": "2019-06-01",
             "notes": "On amlodipine 10mg; responding well."},
        ],
        # (systolic, diastolic, pulse, resp, temp, spo2, weight, height, bmi, pain, mews)
        "vitals": [
            (168, 100, 88, 18, 36.8, 98, 92.0, 164, 34.2, 1, 2),
            (152, 94, 84, 18, 36.7, 98, 91.0, 164, 33.8, 0, 1),
            (140, 88, 80, 16, 36.6, 99, 90.0, 164, 33.5, 0, 0),
            (130, 84, 78, 16, 36.7, 99, 89.0, 164, 33.1, 0, 0),
        ],
        "loyalty": False,
    },
    {
        "first_name": "Chukwudi", "middle_name": "Obinna", "last_name": "Eze",
        "email": "chukwudi.eze@example.com", "gender": Gender.MALE,
        "marital_status": "MARRIED",
        "dob": "1975-11-03", "phone": "07030000102", "alt_phone": "08030000102",
        "address": "7 Ademola Street, Surulere", "city": "Lagos", "state": "Lagos",
        "country": "Nigeria",
        "patient_class": PatientClass.RETAINERSHIP,
        "payer_type": "RETAINERSHIP",
        "national_identifier": "12345678902", "national_identifier_type": "NIN",
        "allergies": "No known drug allergies",
        "emergency_contact": ("Ada Eze", "07030000198", "Wife"),
        "next_of_kin": ("Ada Eze", "07030000198", "Wife",
                        "7 Ademola Street, Surulere, Lagos"),
        "registration_notes": "Corporate retainership - Dangote Group staff.",
        "insurance_key": "RETAINER",
        "insurance": {
            "policy_number": "DAN-RET-5567", "member_id": "DAN-EMP-33218",
            "plan_name": "Dangote Staff Retainer", "status": "ACTIVE",
            "valid_from": "2023-01-01", "valid_to": "2026-12-31",
            "coverage_details": {"billed_to": "employer", "co_pay_percentage": 0},
            "note": "Employer-billed corporate retainership.",
        },
        "baseline": {
            "rhesus_factor": "Positive", "g6pd_status": "Normal",
            "hepatitis_b_status": "Negative", "hepatitis_c_status": "Negative",
            "hiv_status": "Negative",
            "blood_group": "A+", "genotype": "AS",
            "blood_sugar_baseline": "FBS 8.9 mmol/L",
            "lipid_profile_baseline": "TC 5.8, LDL 3.6, HDL 1.0, TG 2.2 mmol/L",
            "known_allergies": "No known drug allergies",
            "chronic_conditions": "Type 2 diabetes mellitus; dyslipidaemia",
            "existing_diagnoses": "Type 2 diabetes mellitus (E11); dyslipidaemia (E78.5)",
            "long_term_medications": "Metformin 1g BD; atorvastatin 20mg nocte",
            "past_medical_history": "Diagnosed diabetic 2017. One episode of DKA (2018).",
            "past_surgical_history": "Nil.",
            "family_history": "Strong family history of type 2 diabetes.",
            "social_history": "Ex-smoker (quit 2016). Sedentary office worker.",
            "immunization_history": "COVID-19 vaccinated; influenza annually.",
            "obstetric_history": "Not applicable.",
            "disability_info": "None.",
            "organ_donor": True,
            "baseline_height_cm": Decimal("178"), "baseline_weight_kg": Decimal("98"),
            "additional_notes": "Enrolled in diabetic education programme.",
        },
        "problems": [
            {"condition_name": "Type 2 diabetes mellitus", "condition_code": "E11",
             "category": "Endocrine", "status": ProblemStatus.CONTROLLED,
             "severity": "MODERATE", "onset": "2017-02-15",
             "notes": "Diet + metformin; HbA1c trending down."},
            {"condition_name": "Dyslipidaemia", "condition_code": "E78.5",
             "category": "Metabolic", "status": ProblemStatus.ACTIVE,
             "severity": "MILD", "onset": "2020-01-01",
             "notes": "On statin therapy."},
        ],
        "vitals": [
            (130, 84, 80, 16, 36.6, 98, 98.0, 178, 30.9, 0, 0),
            (128, 82, 78, 16, 36.7, 98, 97.5, 178, 30.8, 0, 0),
            (126, 82, 78, 16, 36.6, 99, 97.0, 178, 30.6, 0, 0),
            (128, 80, 76, 16, 36.6, 99, 96.5, 178, 30.5, 0, 0),
        ],
        "loyalty": False,
    },
    {
        "first_name": "Ngozi", "middle_name": "Adaeze", "last_name": "Balogun",
        "email": "ngozi.balogun@example.com", "gender": Gender.FEMALE,
        "marital_status": "SINGLE",
        "dob": "1990-07-21", "phone": "07030000103", "alt_phone": "08030000103",
        "address": "22 Bourdillon Road, Ikoyi", "city": "Lagos", "state": "Lagos",
        "country": "Nigeria",
        "patient_class": PatientClass.SELF_PAY,
        "payer_type": "SELF_PAY",
        "national_identifier": "12345678903", "national_identifier_type": "NIN",
        "allergies": "Dust, pollen (seasonal rhinitis)",
        "emergency_contact": ("Kunle Balogun", "07030000197", "Brother"),
        "next_of_kin": ("Kunle Balogun", "07030000197", "Brother",
                        "22 Bourdillon Road, Ikoyi, Lagos"),
        "registration_notes": "Self-paying patient; asthmatic on follow-up.",
        "insurance_key": None,
        "insurance": None,
        "baseline": {
            "rhesus_factor": "Positive", "g6pd_status": "Normal",
            "hepatitis_b_status": "Negative", "hepatitis_c_status": "Negative",
            "hiv_status": "Negative",
            "blood_group": "B+", "genotype": "AA",
            "blood_sugar_baseline": "FBS 4.9 mmol/L",
            "lipid_profile_baseline": "TC 4.4, LDL 2.5, HDL 1.6, TG 1.0 mmol/L",
            "known_allergies": "Dust, pollen (seasonal rhinitis)",
            "chronic_conditions": "Bronchial asthma",
            "existing_diagnoses": "Bronchial asthma (J45)",
            "long_term_medications": "Salbutamol PRN; beclomethasone inhaler",
            "past_medical_history": "Childhood asthma; recurrent exacerbations.",
            "past_surgical_history": "Nil.",
            "family_history": "Mother asthmatic.",
            "social_history": "Non-smoker. Works in a dusty textile market.",
            "immunization_history": "COVID-19 vaccinated; influenza annually.",
            "obstetric_history": "Nulliparous.",
            "disability_info": "None.",
            "organ_donor": False,
            "baseline_height_cm": Decimal("170"), "baseline_weight_kg": Decimal("64"),
            "additional_notes": "Poor inhaler technique noted; needs review.",
        },
        "problems": [
            {"condition_name": "Bronchial asthma", "condition_code": "J45",
             "category": "Respiratory", "status": ProblemStatus.WORSENING,
             "severity": "MODERATE", "onset": "2005-09-01",
             "notes": "Increasing exacerbations; review inhaler technique."},
        ],
        "vitals": [
            (118, 76, 82, 18, 36.7, 98, 64.0, 170, 22.1, 1, 0),
            (120, 78, 88, 20, 36.8, 96, 64.0, 170, 22.1, 2, 1),
            (122, 78, 92, 22, 37.0, 94, 63.5, 170, 22.0, 3, 2),
            (124, 80, 96, 24, 37.1, 92, 63.0, 170, 21.8, 4, 3),
        ],
        "loyalty": True,
    },
    {
        "first_name": "Tunde", "middle_name": "Olamide", "last_name": "Adeyemi",
        "email": "tunde.adeyemi@example.com", "gender": Gender.MALE,
        "marital_status": "SINGLE",
        "dob": "1985-02-09", "phone": "07030000104", "alt_phone": "08030000104",
        "address": "3 Marina, Lagos Island", "city": "Lagos", "state": "Lagos",
        "country": "Nigeria",
        "patient_class": PatientClass.SELF_PAY,
        "payer_type": "SELF_PAY",
        "national_identifier": "12345678904", "national_identifier_type": "NIN",
        "allergies": "No known drug allergies",
        "emergency_contact": ("Sade Adeyemi", "07030000196", "Sister"),
        "next_of_kin": ("Sade Adeyemi", "07030000196", "Sister",
                        "3 Marina, Lagos Island, Lagos"),
        "registration_notes": "Routine health check; no chronic illness.",
        "insurance_key": None,
        "insurance": None,
        "baseline": {
            "rhesus_factor": "Negative", "g6pd_status": "Normal",
            "hepatitis_b_status": "Negative", "hepatitis_c_status": "Negative",
            "hiv_status": "Negative",
            "blood_group": "O-", "genotype": "AA",
            "blood_sugar_baseline": "FBS 5.0 mmol/L",
            "lipid_profile_baseline": "TC 4.2, LDL 2.4, HDL 1.5, TG 0.9 mmol/L",
            "known_allergies": "No known drug allergies",
            "chronic_conditions": "None",
            "existing_diagnoses": "Nil significant",
            "long_term_medications": "None",
            "past_medical_history": "Fit and well; no chronic conditions.",
            "past_surgical_history": "Nil.",
            "family_history": "No significant family history.",
            "social_history": "Non-smoker, non-drinker. Regular exercise.",
            "immunization_history": "COVID-19 vaccinated; tetanus up to date.",
            "obstetric_history": "Not applicable.",
            "disability_info": "None.",
            "organ_donor": True,
            "baseline_height_cm": Decimal("182"), "baseline_weight_kg": Decimal("80"),
            "additional_notes": "Healthy baseline; annual review advised.",
        },
        "problems": [],
        "vitals": [
            (120, 80, 72, 16, 36.6, 99, 80.0, 182, 24.2, 0, 0),
            (118, 78, 70, 16, 36.6, 99, 80.0, 182, 24.2, 0, 0),
        ],
        "loyalty": False,
    },
]

CLINICAL_TEMPLATES = [
    {
        "name": "General Consultation (SOAP)",
        "description": "Default SOAP note for a general outpatient consultation.",
        "specialty": "General Practice",
        "template_type": "SOAP",
        "sections": [
            {"key": "subjective", "label": "Subjective", "placeholder": "Presenting complaint, history"},
            {"key": "objective", "label": "Objective", "placeholder": "Examination findings, vitals"},
            {"key": "assessment", "label": "Assessment", "placeholder": "Diagnosis / impression"},
            {"key": "plan", "label": "Plan", "placeholder": "Investigations, treatment, follow-up"},
        ],
    },
    {
        "name": "Hypertension Follow-up",
        "description": "Structured review for a hypertensive patient.",
        "specialty": "Cardiology",
        "template_type": "SOAP",
        "sections": [
            {"key": "subjective", "label": "Symptoms & adherence"},
            {"key": "objective", "label": "BP, weight, BMI"},
            {"key": "assessment", "label": "Control status"},
            {"key": "plan", "label": "Medication adjustment & review date"},
        ],
    },
    {
        "name": "Diabetes Review",
        "description": "Structured review for a diabetic patient.",
        "specialty": "Endocrinology",
        "template_type": "SOAP",
        "sections": [
            {"key": "subjective", "label": "Symptoms, hypo/hyper episodes"},
            {"key": "objective", "label": "FBS/RBS, HbA1c, weight, foot exam"},
            {"key": "assessment", "label": "Glycaemic control"},
            {"key": "plan", "label": "Therapy, diet, review date"},
        ],
    },
]


def seed_templates(db: Session) -> None:
    print("  Templates: visit-flow pathway ...")
    try:
        from app.seeds.clinical_flow_seed import seed_standard_visit_flow

        res = seed_standard_visit_flow(db)
        print(f"    -> {res.get('message')}")
    except Exception as exc:  # pragma: no cover
        print(f"    !! visit-flow seed skipped: {exc}")

    print("  Templates: clinical note templates ...")
    for t in CLINICAL_TEMPLATES:
        existing = db.query(ClinicalTemplate).filter(ClinicalTemplate.name == t["name"]).first()
        if existing:
            continue
        db.add(ClinicalTemplate(
            name=t["name"], description=t["description"], specialty=t["specialty"],
            template_type=t["template_type"], sections=t["sections"],
        ))
    db.commit()


def _upsert_patient(db, spec: dict, ref: dict) -> Patient:
    from app.schemas.patient_schemas import (
        PatientCreateSchema,
        PatientInsuranceEnrollmentSchema,
        PatientLoyaltyEnrollmentSchema,
    )
    from app.services.patient_service import PatientService

    existing = db.query(Patient).filter(Patient.email == spec["email"]).first()
    if existing:
        return existing

    ec_name, ec_phone, ec_rel = spec["emergency_contact"]
    nok_name, nok_phone, nok_rel, nok_addr = spec["next_of_kin"]

    insurance_enrollment = None
    if spec.get("insurance") and spec.get("insurance_key"):
        ins = spec["insurance"]
        insurance_enrollment = PatientInsuranceEnrollmentSchema(
            insurance_provider_id=ref["providers"][spec["insurance_key"]],
            policy_number=ins["policy_number"],
            member_id=ins["member_id"],
            plan_name=ins["plan_name"],
            coverage_details=ins["coverage_details"],
            status=ins["status"],
            valid_from=_d(ins["valid_from"]),
            valid_to=_d(ins["valid_to"]),
            note=ins["note"],
        )

    loyalty_enrollment = None
    if spec.get("loyalty"):
        loyalty_enrollment = PatientLoyaltyEnrollmentSchema(
            loyalty_program_id=ref["loyalty_program_id"],
            points_balance=Decimal("0"),
            joined_date=_now(),
            note="Enrolled at registration (sample data).",
        )

    svc = PatientService(db)
    svc.create_patient(
        PatientCreateSchema(
            first_name=spec["first_name"],
            middle_name=spec.get("middle_name"),
            last_name=spec["last_name"],
            email=spec["email"],
            date_of_birth=_d(spec["dob"]),
            gender=spec["gender"].value if hasattr(spec["gender"], "value") else spec["gender"],
            marital_status=spec.get("marital_status"),
            phone_number=spec["phone"],
            alternate_phone_number=spec.get("alt_phone"),
            address=spec["address"],
            city=spec.get("city"),
            state=spec.get("state"),
            country=spec.get("country", "Nigeria"),
            blood_group=spec["baseline"].get("blood_group"),
            genotype=spec["baseline"].get("genotype"),
            allergies=spec.get("allergies"),
            chronic_conditions=spec["baseline"].get("chronic_conditions"),
            emergency_contact_name=ec_name,
            emergency_contact_phone=ec_phone,
            emergency_contact_relationship=ec_rel,
            next_of_kin_name=nok_name,
            next_of_kin_phone=nok_phone,
            next_of_kin_relationship=nok_rel,
            next_of_kin_address=nok_addr,
            patient_type="OUTPATIENT",
            patient_class=spec["patient_class"].value,
            payer_type=spec.get("payer_type"),
            national_identifier=spec.get("national_identifier"),
            national_identifier_type=spec.get("national_identifier_type"),
            identification_details={
                "issued_by": "NIMC",
                "type": spec.get("national_identifier_type", "NIN"),
            },
            registration_notes=spec.get("registration_notes"),
            insurance_enrollment=insurance_enrollment,
            loyalty_enrollment=loyalty_enrollment,
        ),
        force_create_if_possible_duplicate=True,
    )
    db.commit()
    return db.query(Patient).filter(Patient.email == spec["email"]).first()


def _upsert_baseline(db, patient: Patient, spec: dict) -> None:
    b = spec["baseline"]
    existing = (
        db.query(PatientBaselineProfile)
        .filter(PatientBaselineProfile.patient_id == patient.id)
        .first()
    )
    if existing:
        return
    db.add(PatientBaselineProfile(
        patient_id=patient.id,
        rhesus_factor=b.get("rhesus_factor"),
        g6pd_status=b.get("g6pd_status"),
        hepatitis_b_status=b.get("hepatitis_b_status"),
        hepatitis_c_status=b.get("hepatitis_c_status"),
        hiv_status=b.get("hiv_status"),
        blood_sugar_baseline=b.get("blood_sugar_baseline"),
        lipid_profile_baseline=b.get("lipid_profile_baseline"),
        known_allergies=b.get("known_allergies"),
        chronic_conditions=b.get("chronic_conditions"),
        existing_diagnoses=b.get("existing_diagnoses"),
        long_term_medications=b.get("long_term_medications"),
        past_medical_history=b.get("past_medical_history"),
        past_surgical_history=b.get("past_surgical_history"),
        family_history=b.get("family_history"),
        social_history=b.get("social_history"),
        immunization_history=b.get("immunization_history"),
        obstetric_history=b.get("obstetric_history"),
        disability_info=b.get("disability_info"),
        organ_donor=b.get("organ_donor"),
        baseline_height_cm=b.get("baseline_height_cm"),
        baseline_weight_kg=b.get("baseline_weight_kg"),
        additional_notes=b.get("additional_notes"),
        version=1,
    ))
    db.commit()


def _upsert_problems(db, patient: Patient, spec: dict) -> None:
    for pr in spec["problems"]:
        exists = (
            db.query(PatientProblem)
            .filter(
                PatientProblem.patient_id == patient.id,
                PatientProblem.condition_name == pr["condition_name"],
            )
            .first()
        )
        if exists:
            continue
        onset = pr.get("onset")
        db.add(PatientProblem(
            patient_id=patient.id,
            condition_name=pr["condition_name"],
            condition_code=pr.get("condition_code"),
            category=pr.get("category"),
            status=pr["status"],
            is_chronic=True,
            severity=pr.get("severity"),
            onset_date=_d(onset) if onset else None,
            notes=pr.get("notes"),
            last_reviewed_at=_now(),
        ))
    db.commit()


def _seed_visits_and_vitals(db, patient: Patient, spec: dict, facility_id) -> None:
    series = spec["vitals"]
    n = len(series)
    # Space readings ~4 weeks apart, oldest first, ending ~today.
    base = _now() - timedelta(days=28 * (n - 1))
    for i, row in enumerate(series):
        sys_bp, dia_bp, pulse, resp, temp, spo2, weight, height, bmi, pain, mews = row
        recorded = base + timedelta(days=28 * i)
        visit_code = f"SEEDVIT-{patient.id}-{i + 1}"
        visit = db.query(Visit).filter(Visit.visit_code == visit_code).first()
        if visit is None:
            visit = Visit(
                patient_id=patient.id,
                facility_id=facility_id,
                visit_code=visit_code,
                visit_date=recorded,
                status=VisitStatus.COMPLETED,
                priority=VisitPriority.NORMAL,
                visit_reason="Routine chronic-care review (sample data)",
                check_in_time=recorded,
                check_out_time=recorded + timedelta(hours=1),
            )
            db.add(visit)
            db.flush()  # assign visit.id
        already = db.query(VitalSign).filter(VitalSign.visit_id == visit.id).first()
        if already is None:
            db.add(VitalSign(
                visit_id=visit.id,
                temperature_celsius=Decimal(str(temp)),
                pulse_rate=pulse,
                respiratory_rate=resp,
                systolic_bp=sys_bp,
                diastolic_bp=dia_bp,
                oxygen_saturation=Decimal(str(spo2)),
                weight_kg=Decimal(str(weight)),
                height_cm=Decimal(str(height)),
                bmi=Decimal(str(bmi)),
                pain_score=pain,
                mews_score=mews,
                recorded_at=recorded,
            ))
    db.commit()


def seed_patients(db: Session, ref: dict) -> None:
    for spec in SAMPLE_PATIENTS:
        patient = _upsert_patient(db, spec, ref)
        print(f"  Patient: {patient.first_name} {patient.last_name} "
              f"({spec['patient_class'].value}) [id={patient.id}]")
        _upsert_baseline(db, patient, spec)
        _upsert_problems(db, patient, spec)
        _seed_visits_and_vitals(db, patient, spec, ref["facility_id"])


# ==========================================================================
# Staff roster for a standard Nigerian tertiary hospital
# ==========================================================================
# Each entry populates the full UserCreateSchema + StaffProfileCreateSchema.
STAFF_ROSTER = [
    # --- Executive / administration ---
    {"username": "cmd.adewale", "first": "Adewale", "middle": "Oluwaseun", "last": "Ogunbanjo",
     "roles": ["TENANT_ADMIN", "DOCTOR"], "dept": "ADMIN", "sdp": None,
     "title": "Chief Medical Director", "specialty": "Internal Medicine", "licence": "MDCN/12001"},
    {"username": "admin.folake", "first": "Folake", "middle": "Aderonke", "last": "Bello",
     "roles": ["ADMIN"], "dept": "ADMIN", "sdp": None,
     "title": "Hospital Administrator", "specialty": None, "licence": None},
    {"username": "it.emeka", "first": "Emeka", "middle": "Chinedu", "last": "Nnaji",
     "roles": ["ADMIN"], "dept": "ICT", "sdp": None,
     "title": "IT Administrator", "specialty": None, "licence": None},
    {"username": "records.bisi", "first": "Bisi", "middle": "Omolara", "last": "Adeleke",
     "roles": ["RECEPTIONIST"], "dept": "RECORDS", "sdp": ServicePointType.REGISTRATION,
     "title": "Medical Records Officer", "specialty": None, "licence": None},

    # --- Front desk / registration ---
    {"username": "reception.chidinma", "first": "Chidinma", "middle": "Ada", "last": "Okoro",
     "roles": ["RECEPTIONIST"], "dept": "FRONTDESK", "sdp": ServicePointType.REGISTRATION,
     "title": "Front Desk Officer", "specialty": None, "licence": None},
    {"username": "reception.yusuf", "first": "Yusuf", "middle": "Aliyu", "last": "Ibrahim",
     "roles": ["RECEPTIONIST"], "dept": "FRONTDESK", "sdp": ServicePointType.REGISTRATION,
     "title": "Front Desk Officer", "specialty": None, "licence": None},

    # --- Nursing ---
    {"username": "matron.grace", "first": "Grace", "middle": "Nkoyo", "last": "Etim",
     "roles": ["NURSE"], "dept": "NURSING", "sdp": ServicePointType.WARD,
     "title": "Matron", "specialty": None, "licence": "RN/RM 30012"},
    {"username": "nurse.halima", "first": "Halima", "middle": "Zara", "last": "Sani",
     "roles": ["NURSE"], "dept": "NURSING", "sdp": ServicePointType.TRIAGE,
     "title": "Triage Nurse", "specialty": None, "licence": "RN 44021"},
    {"username": "nurse.ifeoma", "first": "Ifeoma", "middle": "Chioma", "last": "Uche",
     "roles": ["NURSE"], "dept": "NURSING", "sdp": ServicePointType.TRIAGE,
     "title": "Staff Nurse", "specialty": None, "licence": "RN 44022"},
    {"username": "nurse.tobi", "first": "Tobi", "middle": "Ayodele", "last": "Fashola",
     "roles": ["NURSE"], "dept": "NURSING", "sdp": ServicePointType.WARD,
     "title": "Ward Nurse", "specialty": None, "licence": "RN 44023"},

    # --- Doctors / consultants ---
    {"username": "dr.okon", "first": "Aniekan", "middle": "Effiong", "last": "Okon",
     "roles": ["DOCTOR"], "dept": "GOPD", "sdp": ServicePointType.CLINIC,
     "title": "Medical Officer", "specialty": "General Practice", "licence": "MDCN/12045"},
    {"username": "dr.aisha", "first": "Aisha", "middle": "Binta", "last": "Mohammed",
     "roles": ["DOCTOR"], "dept": "INTMED", "sdp": ServicePointType.CLINIC,
     "title": "Consultant Physician", "specialty": "Internal Medicine", "licence": "MDCN/12046"},
    {"username": "dr.chukwu", "first": "Chukwuemeka", "middle": "Ikenna", "last": "Obi",
     "roles": ["DOCTOR"], "dept": "PAEDS", "sdp": ServicePointType.CLINIC,
     "title": "Consultant Paediatrician", "specialty": "Paediatrics", "licence": "MDCN/12047"},
    {"username": "dr.funmi", "first": "Funmilayo", "middle": "Titilayo", "last": "Adeyemi",
     "roles": ["DOCTOR"], "dept": "OANDG", "sdp": ServicePointType.CLINIC,
     "title": "Consultant O&G", "specialty": "Obstetrics & Gynaecology", "licence": "MDCN/12048"},

    # --- Surgery / theatre ---
    {"username": "surg.balarabe", "first": "Balarabe", "middle": "Sadiq", "last": "Musa",
     "roles": ["SURGEON", "DOCTOR"], "dept": "SURGERY", "sdp": ServicePointType.THEATRE,
     "title": "Consultant Surgeon", "specialty": "General Surgery", "licence": "MDCN/12060"},
    {"username": "anaes.rita", "first": "Rita", "middle": "Ngozi", "last": "Eze",
     "roles": ["ANAESTHETIST", "DOCTOR"], "dept": "THEATRE", "sdp": ServicePointType.THEATRE,
     "title": "Consultant Anaesthetist", "specialty": "Anaesthesia", "licence": "MDCN/12061"},
    {"username": "theatre.nurse.paul", "first": "Paul", "middle": "Chukwuma", "last": "Achebe",
     "roles": ["THEATRE_NURSE", "NURSE"], "dept": "THEATRE", "sdp": ServicePointType.THEATRE,
     "title": "Theatre Nurse", "specialty": None, "licence": "RN 44050"},

    # --- Laboratory ---
    {"username": "lab.ngozi", "first": "Ngozi", "middle": "Amarachi", "last": "Ekwueme",
     "roles": ["LAB_SCIENTIST"], "dept": "LAB", "sdp": ServicePointType.LABORATORY,
     "title": "Chief Medical Laboratory Scientist", "specialty": "Haematology", "licence": "MLSCN/7001"},
    {"username": "lab.samuel", "first": "Samuel", "middle": "Oluwatobi", "last": "Ojo",
     "roles": ["LAB_SCIENTIST"], "dept": "LAB", "sdp": ServicePointType.LABORATORY,
     "title": "Medical Laboratory Scientist", "specialty": "Chemical Pathology", "licence": "MLSCN/7002"},
    {"username": "lab.tech.mary", "first": "Mary", "middle": "Fatima", "last": "Danjuma",
     "roles": ["LAB_TECHNICIAN"], "dept": "LAB", "sdp": ServicePointType.LABORATORY,
     "title": "Laboratory Technician", "specialty": None, "licence": "MLSCN/T-330"},

    # --- Radiology ---
    {"username": "rad.dr.uche", "first": "Uche", "middle": "Obiora", "last": "Nwankwo",
     "roles": ["RADIOLOGIST", "DOCTOR"], "dept": "RADIOLOGY", "sdp": ServicePointType.RADIOLOGY,
     "title": "Consultant Radiologist", "specialty": "Radiology", "licence": "MDCN/12070"},
    {"username": "radiographer.john", "first": "John", "middle": "Oluwadamilare", "last": "Ade",
     "roles": ["RADIOGRAPHER"], "dept": "RADIOLOGY", "sdp": ServicePointType.RADIOLOGY,
     "title": "Radiographer", "specialty": None, "licence": "RRBN 5501"},

    # --- Pharmacy ---
    {"username": "pharm.zainab", "first": "Zainab", "middle": "Halima", "last": "Abubakar",
     "roles": ["PHARMACIST"], "dept": "PHARMACY", "sdp": ServicePointType.PHARMACY,
     "title": "Chief Pharmacist", "specialty": None, "licence": "PCN 9001"},
    {"username": "pharm.david", "first": "David", "middle": "Chibueze", "last": "Okoro",
     "roles": ["PHARMACIST"], "dept": "PHARMACY", "sdp": ServicePointType.PHARMACY,
     "title": "Pharmacist", "specialty": None, "licence": "PCN 9002"},

    # --- Finance / accounts ---
    {"username": "accountant.tunde", "first": "Tunde", "middle": "Babatunde", "last": "Bakare",
     "roles": ["BILLING_OFFICER"], "dept": "ACCOUNTS", "sdp": None,
     "title": "Accountant", "specialty": None, "licence": None},
    {"username": "billing.esther", "first": "Esther", "middle": "Oluwakemi", "last": "Ojo",
     "roles": ["BILLING_OFFICER"], "dept": "ACCOUNTS", "sdp": ServicePointType.CASHIER,
     "title": "Billing Officer", "specialty": None, "licence": None},
    {"username": "cashier.blessing", "first": "Blessing", "middle": "Chidera", "last": "Umeh",
     "roles": ["CASHIER"], "dept": "ACCOUNTS", "sdp": ServicePointType.CASHIER,
     "title": "Cashier", "specialty": None, "licence": None},
    {"username": "cashier.suleiman", "first": "Suleiman", "middle": "Abdullahi", "last": "Garba",
     "roles": ["CASHIER"], "dept": "ACCOUNTS", "sdp": ServicePointType.CASHIER,
     "title": "Cashier", "specialty": None, "licence": None},

    # --- HMO / insurance ---
    {"username": "hmo.amara", "first": "Amara", "middle": "Chiamaka", "last": "Nwosu",
     "roles": ["INSURANCE_OFFICER"], "dept": "HMO", "sdp": ServicePointType.INSURANCE_CONFIRMATION,
     "title": "HMO Desk Officer", "specialty": None, "licence": None},
    {"username": "hmo.reviewer.kelvin", "first": "Kelvin", "middle": "Oghenetega", "last": "Ade",
     "roles": ["INSURANCE_REVIEWER"], "dept": "HMO", "sdp": ServicePointType.INSURANCE_CONFIRMATION,
     "title": "Claims Reviewer", "specialty": None, "licence": None},

    # --- Human resources ---
    {"username": "hr.manager.ruth", "first": "Ruth", "middle": "Onyinye", "last": "Ibe",
     "roles": ["HR_MANAGER"], "dept": "HR", "sdp": None,
     "title": "HR Manager", "specialty": None, "licence": None},
    {"username": "hr.officer.james", "first": "James", "middle": "Ebuka", "last": "Okafor",
     "roles": ["HR_OFFICER"], "dept": "HR", "sdp": None,
     "title": "HR Officer", "specialty": None, "licence": None},
]

STAFF_PASSWORD = "Carepoint@2026"


def seed_staff(db: Session, tenant_code: str, ref: dict) -> None:
    from app.schemas.staff_profile_schemas import StaffProfileCreateSchema, UserCreateSchema
    from app.services.staff_profile_service import StaffProfileService

    roles = {r.code: r.id for r in db.query(Role).all()}
    facility_id = ref["facility_id"]
    dept_ids = ref["departments"]

    # Group service delivery points by type so we can attach staff to the
    # right workstation (drives the queue worklist + routing guardrails).
    sdp_by_type: dict = {}
    for sdp in db.query(ServiceDeliveryPoint).all():
        sdp_by_type.setdefault(sdp.service_point_type, sdp)

    svc = StaffProfileService(db)
    domain = f"{(tenant_code or 'hms').lower()}.hospital.ng"
    created = 0
    backfilled = 0
    for idx, member in enumerate(STAFF_ROSTER):
        username = member["username"]
        role_ids = [roles[rc] for rc in member["roles"] if rc in roles]
        sdp_type = member["sdp"]
        sdp_ids = []
        if sdp_type is not None and sdp_type in sdp_by_type:
            sdp_ids = [sdp_by_type[sdp_type].id]
        department_id = dept_ids.get(member["dept"]) if member.get("dept") else None

        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            # Self-heal: backfill facility / department / workstation on staff
            # created before those reference records existed.
            profile = svc.repository.get_staff_profile_by_user_id(existing_user.id)
            if profile is not None:
                changed = False
                if profile.facility_id is None and facility_id is not None:
                    profile.facility_id = facility_id
                    changed = True
                if profile.department_id is None and department_id is not None:
                    profile.department_id = department_id
                    changed = True
                if sdp_ids and not profile.service_delivery_points:
                    svc.repository.replace_sdp_assignments(profile.id, sdp_ids)
                    changed = True
                if changed:
                    backfilled += 1
            continue

        try:
            svc.create_user_with_staff_profile(UserCreateSchema(
                username=username,
                email=f"{username}@{domain}",
                password=STAFF_PASSWORD,
                first_name=member["first"],
                middle_name=member.get("middle"),
                last_name=member["last"],
                phone_number=f"0803{1000000 + idx:07d}"[:11],
                is_email_verified=True,
                is_phone_verified=True,
                role_ids=role_ids,
                staff_profile=StaffProfileCreateSchema(
                    staff_no=f"STF-{username.replace('.', '-').upper()}",
                    facility_id=facility_id,
                    department_id=department_id,
                    service_delivery_point_ids=sdp_ids,
                    job_title=member["title"],
                    specialty=member["specialty"],
                    professional_license_no=member["licence"],
                ),
            ))
            created += 1
        except Exception as exc:  # keep going; report the offender
            print(f"    !! could not create {username}: {exc}")
    db.commit()
    print(f"  Staff: {created} new user(s) created, {backfilled} existing profile(s) "
          f"backfilled (default password: {STAFF_PASSWORD}); {len(STAFF_ROSTER)} in roster.")


def resolve_tenant(master_db: Session, tenant_arg: str) -> Tenant:
    q = master_db.query(Tenant)
    if tenant_arg and tenant_arg.isdigit():
        tenant = q.filter(Tenant.id == int(tenant_arg)).first()
    elif tenant_arg:
        tenant = q.filter(Tenant.code.ilike(tenant_arg)).first()
    else:
        tenant = q.order_by(Tenant.id.asc()).first()
    return tenant


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed sample clinical data into a tenant DB.")
    parser.add_argument("--tenant", type=str, default=None,
                        help="Tenant code or id. Defaults to the first tenant.")
    args = parser.parse_args()

    master_engine = get_master_engine()
    with Session(master_engine) as master_db:
        tenant = resolve_tenant(master_db, args.tenant or "")
        if not tenant:
            print(f"Error: tenant '{args.tenant}' not found in the master DB.")
            sys.exit(1)
        if not tenant.db_connection_string:
            print(f"Error: tenant {tenant.code} has no database connection string.")
            sys.exit(1)
        try:
            db_url = decrypt_string(tenant.db_connection_string)
        except Exception:
            db_url = tenant.db_connection_string
        master_db.expunge(tenant)
        set_current_tenant(tenant)

    print(f"Seeding sample clinical data into tenant: {tenant.name} ({tenant.code})")
    tenant_engine = create_engine(db_url, poolclass=NullPool, future=True)
    with Session(tenant_engine) as db:
        ref = seed_reference_data(db)
        seed_templates(db)
        seed_staff(db, tenant.code, ref)
        seed_patients(db, ref)
    tenant_engine.dispose()
    print("Done. Reference data, staff, sample patients, baselines, problem lists, "
          "vitals and templates seeded.")


if __name__ == "__main__":
    main()
