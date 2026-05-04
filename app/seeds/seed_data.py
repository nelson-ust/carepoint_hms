# app/seeds/seed_data.py
from __future__ import annotations

"""
Carepoint HMS — full demo dataset seed.

This is the second-stage seed: it builds on top of ``security_seed`` (which
sets up permissions, roles, role-permission mappings, and the bootstrap
super-user) and populates a realistic operational dataset suitable for
demos, QA, and end-to-end tests.

Layered seed strategy
---------------------
- Pydantic schemas validate every payload before it touches the DB so the
  seed exercises the same input-validation contracts the API does.
- Service classes drive each insert so business rules (uniqueness, code
  normalisation, cascading flushes, audit events) all run as in production.
- Where a service is not yet implemented (Department, Facility), a minimal
  ORM-level upsert is used. These are kept narrow and clearly marked.

Idempotent-by-default
---------------------
Every step looks up the row by its natural key first. Re-running the seed
on an already-seeded DB is safe and quick: rows are *not* duplicated and
existing IDs are reused. This is critical because the seed is wired into
the app startup path during local dev / staging.

Run modes
---------
- programmatic:     ``from app.seeds.seed_data import seed_demo_data; seed_demo_data(db)``
- one-shot CLI:     ``python -m app.seeds.seed_data``
- combined seed:    ``python -m app.seeds.seed_data --bootstrap-superuser \\
                       --username admin --email admin@carepoint.local \\
                       --password 'ChangeMe123!'``
"""

import argparse
import random
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.enums import (
    BedStatus,
    FacilityStatus,
    FacilityType,
    ServicePointType,
)
from app.core.exceptions import AlreadyExistsError

# Existing seed for permissions + roles + (optional) superuser.
from app.seeds.security_seed import seed_security_baseline

# Models — used for direct upserts where there is no service yet, and for
# repository-style lookups during idempotent re-runs.
from app.models.all_models import (
    BillableService,
    Bed,
    Department,
    Drug,
    DrugCategory,
    Facility,
    LabTestCatalog,
    NotificationTemplate,
    Patient,
    ServiceDeliveryPoint,
    Ward,
)

# Pydantic Create-schemas (validation layer).
from app.schemas.bed_schemas import BedCreateSchema
from app.schemas.drug_schema import DrugCategoryCreateSchema, DrugCreateSchema
from app.schemas.lab_schema import LabTestCatalogCreateSchema
from app.schemas.notification_schema import NotificationTemplateCreateSchema
from app.schemas.patient_schemas import PatientCreateSchema
from app.schemas.service_delivery_point_schemas import (
    ServiceDeliveryPointCreateSchema,
)
from app.schemas.ward_schemas import WardCreateSchema

# Services (business-rule layer).
from app.services.bed_service import BedService
from app.services.drug_service import DrugCategoryService, DrugService
from app.services.lab_service import LabCatalogService
from app.services.notification_service import NotificationTemplateService
from app.services.patient_service import PatientService
from app.services.service_delivery_point_service import ServiceDeliveryService
from app.services.ward_service import WardService


# ============================================================
# DEMO DATA
# ============================================================

DEMO_FACILITY = {
    "code": "MAIN",
    "name": "Carepoint General Hospital",
    "facility_type": FacilityType.MAIN_HOSPITAL,
    "status": FacilityStatus.ACTIVE,
    "address_line_1": "1 Carepoint Avenue",
    "city": "Lagos",
    "state": "Lagos",
    "country": "Nigeria",
}

DEMO_DEPARTMENTS: list[dict[str, str]] = [
    {"code": "OPD", "name": "Outpatient Department"},
    {"code": "INPATIENT", "name": "Inpatient Services"},
    {"code": "EMERGENCY", "name": "Emergency Department"},
    {"code": "LAB", "name": "Laboratory"},
    {"code": "RADIOLOGY", "name": "Radiology"},
    {"code": "PHARMACY", "name": "Pharmacy"},
    {"code": "THEATRE", "name": "Operating Theatre"},
    {"code": "FINANCE", "name": "Finance & Billing"},
]

# Service Delivery Points — one per major workflow gate.
DEMO_SERVICE_DELIVERY_POINTS: list[dict[str, Any]] = [
    {
        "name": "Front Desk Registration",
        "code": "SDP-REG",
        "service_point_type": ServicePointType.REGISTRATION.value,
        "department_code": "OPD",
        "queue_prefix": "REG",
        "supports_appointments": True,
        "supports_walk_in": True,
    },
    {
        "name": "Triage Desk",
        "code": "SDP-TRIAGE",
        "service_point_type": ServicePointType.TRIAGE.value,
        "department_code": "OPD",
        "queue_prefix": "TRG",
    },
    {
        "name": "General Outpatient Clinic",
        "code": "SDP-CLINIC-GP",
        "service_point_type": ServicePointType.CLINIC.value,
        "department_code": "OPD",
        "queue_prefix": "GP",
        "supports_appointments": True,
    },
    {
        "name": "Emergency Room",
        "code": "SDP-ER",
        "service_point_type": ServicePointType.EMERGENCY.value,
        "department_code": "EMERGENCY",
        "queue_prefix": "ER",
    },
    {
        "name": "Laboratory Receiving",
        "code": "SDP-LAB",
        "service_point_type": ServicePointType.LABORATORY.value,
        "department_code": "LAB",
        "queue_prefix": "LAB",
    },
    {
        "name": "Radiology Reception",
        "code": "SDP-RAD",
        "service_point_type": ServicePointType.RADIOLOGY.value,
        "department_code": "RADIOLOGY",
        "queue_prefix": "RAD",
    },
    {
        "name": "Outpatient Pharmacy",
        "code": "SDP-PHARM",
        "service_point_type": ServicePointType.PHARMACY.value,
        "department_code": "PHARMACY",
        "queue_prefix": "PH",
    },
    {
        "name": "Insurance Confirmation",
        "code": "SDP-INS",
        "service_point_type": ServicePointType.INSURANCE_CONFIRMATION.value,
        "department_code": "FINANCE",
        "queue_prefix": "INS",
        "supports_walk_in": True,
    },
    {
        "name": "Cashier",
        "code": "SDP-CASH",
        "service_point_type": ServicePointType.CASHIER.value,
        "department_code": "FINANCE",
        "queue_prefix": "PAY",
    },
    {
        "name": "Procedure Room",
        "code": "SDP-PROC",
        "service_point_type": ServicePointType.PROCEDURE_ROOM.value,
        "department_code": "OPD",
        "queue_prefix": "PROC",
    },
    {
        "name": "Inpatient Ward",
        "code": "SDP-WARD",
        "service_point_type": ServicePointType.WARD.value,
        "department_code": "INPATIENT",
        "queue_prefix": "WRD",
    },
]

# Wards (with bed-day pricing) and the beds inside them.
DEMO_WARDS: list[dict[str, Any]] = [
    {
        "code": "FMW-01",
        "name": "Female Medical Ward",
        "ward_type": "GENERAL",
        "description": "General female inpatient ward.",
        "daily_rate": Decimal("15000"),
        "beds": [
            {"bed_no": "FMW-01-01", "bed_type": "General"},
            {"bed_no": "FMW-01-02", "bed_type": "General"},
            {"bed_no": "FMW-01-03", "bed_type": "General"},
            {"bed_no": "FMW-01-04", "bed_type": "General"},
        ],
    },
    {
        "code": "MMW-01",
        "name": "Male Medical Ward",
        "ward_type": "GENERAL",
        "description": "General male inpatient ward.",
        "daily_rate": Decimal("15000"),
        "beds": [
            {"bed_no": "MMW-01-01", "bed_type": "General"},
            {"bed_no": "MMW-01-02", "bed_type": "General"},
            {"bed_no": "MMW-01-03", "bed_type": "General"},
        ],
    },
    {
        "code": "ICU-01",
        "name": "Intensive Care Unit",
        "ward_type": "ICU",
        "description": "High-dependency monitoring beds.",
        "daily_rate": Decimal("75000"),
        "beds": [
            {"bed_no": "ICU-01-01", "bed_type": "ICU"},
            {"bed_no": "ICU-01-02", "bed_type": "ICU"},
        ],
    },
]

# Drug categories + a small drug catalogue.
DEMO_DRUG_CATEGORIES: list[dict[str, str]] = [
    {"code": "ANTIBIOTIC", "name": "Antibiotics"},
    {"code": "ANALGESIC", "name": "Analgesics & Antipyretics"},
    {"code": "ANTIMALARIAL", "name": "Antimalarials"},
    {"code": "ANTIHYPERTENSIVE", "name": "Antihypertensives"},
    {"code": "ANTIDIABETIC", "name": "Antidiabetics"},
    {"code": "INFUSION", "name": "IV Fluids & Infusions"},
]

DEMO_DRUGS: list[dict[str, Any]] = [
    {
        "name": "Amoxicillin 500mg Capsule",
        "generic_name": "Amoxicillin",
        "strength": "500mg",
        "dosage_form": "Capsule",
        "pack_size": "Pack of 30",
        "sku": "AMOX500-CAP",
        "drug_category_code": "ANTIBIOTIC",
        "unit_price": Decimal("250"),
        "reorder_level": Decimal("100"),
    },
    {
        "name": "Paracetamol 500mg Tablet",
        "generic_name": "Paracetamol",
        "strength": "500mg",
        "dosage_form": "Tablet",
        "pack_size": "Pack of 100",
        "sku": "PARA500-TAB",
        "drug_category_code": "ANALGESIC",
        "unit_price": Decimal("50"),
        "reorder_level": Decimal("200"),
    },
    {
        "name": "Artemether/Lumefantrine 20/120mg Tablet",
        "generic_name": "Artemether/Lumefantrine",
        "strength": "20/120mg",
        "dosage_form": "Tablet",
        "pack_size": "Blister of 24",
        "sku": "AL-TAB-24",
        "drug_category_code": "ANTIMALARIAL",
        "unit_price": Decimal("1500"),
        "reorder_level": Decimal("50"),
    },
    {
        "name": "Amlodipine 5mg Tablet",
        "generic_name": "Amlodipine",
        "strength": "5mg",
        "dosage_form": "Tablet",
        "pack_size": "Pack of 30",
        "sku": "AMLO5-TAB",
        "drug_category_code": "ANTIHYPERTENSIVE",
        "unit_price": Decimal("400"),
        "reorder_level": Decimal("80"),
    },
    {
        "name": "Metformin 500mg Tablet",
        "generic_name": "Metformin",
        "strength": "500mg",
        "dosage_form": "Tablet",
        "pack_size": "Pack of 60",
        "sku": "MET500-TAB",
        "drug_category_code": "ANTIDIABETIC",
        "unit_price": Decimal("300"),
        "reorder_level": Decimal("100"),
    },
    {
        "name": "Normal Saline 0.9% 1L IV",
        "generic_name": "Sodium Chloride",
        "strength": "0.9%",
        "dosage_form": "IV Infusion",
        "pack_size": "Bag 1L",
        "sku": "NS09-1L",
        "drug_category_code": "INFUSION",
        "unit_price": Decimal("1200"),
        "reorder_level": Decimal("50"),
    },
]

# Lab tests.
DEMO_LAB_TESTS: list[dict[str, Any]] = [
    {
        "code": "FBC",
        "name": "Full Blood Count",
        "sample_type": "Whole Blood (EDTA)",
        "unit_of_measure": "varies",
        "reference_range": "Adult panel",
        "default_price": Decimal("3500"),
    },
    {
        "code": "MP",
        "name": "Malaria Parasite Microscopy",
        "sample_type": "Whole Blood",
        "unit_of_measure": "qualitative",
        "reference_range": "No parasites seen",
        "default_price": Decimal("1500"),
    },
    {
        "code": "FBS",
        "name": "Fasting Blood Sugar",
        "sample_type": "Plasma (Fluoride)",
        "unit_of_measure": "mg/dL",
        "reference_range": "70 - 100",
        "default_price": Decimal("1200"),
    },
    {
        "code": "U_E_CR",
        "name": "Urea, Electrolytes & Creatinine",
        "sample_type": "Serum",
        "unit_of_measure": "varies",
        "reference_range": "Adult panel",
        "default_price": Decimal("8000"),
    },
    {
        "code": "URINALYSIS",
        "name": "Urinalysis",
        "sample_type": "Urine",
        "unit_of_measure": "varies",
        "reference_range": "Standard panel",
        "default_price": Decimal("2000"),
    },
    {
        "code": "HIV_RAPID",
        "name": "HIV Rapid Screen",
        "sample_type": "Whole Blood",
        "unit_of_measure": "qualitative",
        "reference_range": "Non-reactive",
        "default_price": Decimal("2500"),
    },
]

# Billable services — at least the bed-day rates so the bed-day capture
# helper finds a row to attach charges to.
DEMO_BILLABLE_SERVICES: list[dict[str, Any]] = [
    {
        "code": "BED_DAY_GENERAL",
        "name": "General Ward Bed Day",
        "category": "INPATIENT",
        "default_price": Decimal("15000"),
    },
    {
        "code": "BED_DAY_ICU",
        "name": "ICU Bed Day",
        "category": "INPATIENT",
        "default_price": Decimal("75000"),
    },
    {
        "code": "CONSULT_GP",
        "name": "General Practitioner Consultation",
        "category": "CONSULTATION",
        "default_price": Decimal("5000"),
    },
    {
        "code": "CONSULT_SPECIALIST",
        "name": "Specialist Consultation",
        "category": "CONSULTATION",
        "default_price": Decimal("12000"),
    },
    {
        "code": "TRIAGE",
        "name": "Triage Assessment",
        "category": "CONSULTATION",
        "default_price": Decimal("1500"),
    },
]

# Notification templates — the keys downstream services dispatch by code.
DEMO_NOTIFICATION_TEMPLATES: list[dict[str, str]] = [
    {
        "code": "LAB_RESULT_RELEASED",
        "name": "Lab Result Released",
        "channel": "IN_APP",
        "subject_template": "Lab result available",
        "body_template": (
            "Lab order {order_no}: result for item {lab_order_item_id} "
            "(result id {result_id}) has been released."
        ),
    },
    {
        "code": "RADIOLOGY_REPORT_RELEASED",
        "name": "Radiology Report Released",
        "channel": "IN_APP",
        "subject_template": "Radiology report available",
        "body_template": (
            "Radiology order {order_no}: report {report_id} for exam {exam_id} "
            "has been released."
        ),
    },
    {
        "code": "APPOINTMENT_REMINDER",
        "name": "Appointment Reminder",
        "channel": "SMS",
        "subject_template": "Appointment reminder",
        "body_template": (
            "Reminder: you have an appointment at {clinic_name} on {appointment_at}."
        ),
    },
    {
        "code": "PRESCRIPTION_READY",
        "name": "Prescription Ready",
        "channel": "IN_APP",
        "subject_template": "Prescription ready",
        "body_template": "Prescription {prescription_no} is ready at the pharmacy.",
    },
    {
        "code": "PAYMENT_RECEIVED",
        "name": "Payment Received",
        "channel": "EMAIL",
        "subject_template": "Payment receipt {payment_no}",
        "body_template": (
            "We have received your payment of {amount} on invoice {invoice_no}. "
            "Thank you."
        ),
    },
]

# Sample patients to make demos look alive.
DEMO_PATIENTS: list[dict[str, Any]] = [
    {
        "first_name": "Adaeze",
        "last_name": "Okafor",
        "middle_name": "Chiamaka",
        "date_of_birth": date(1992, 5, 14),
        "gender": "FEMALE",
        "phone_number": "+2348012345001",
        "email": "adaeze.okafor@example.com",
        "city": "Lagos",
        "state": "Lagos",
        "country": "Nigeria",
        "blood_group": "O+",
        "patient_type": "OUTPATIENT",
    },
    {
        "first_name": "Ibrahim",
        "last_name": "Bello",
        "date_of_birth": date(1978, 11, 3),
        "gender": "MALE",
        "phone_number": "+2348012345002",
        "email": "ibrahim.bello@example.com",
        "city": "Abuja",
        "state": "FCT",
        "country": "Nigeria",
        "blood_group": "A+",
        "patient_type": "OUTPATIENT",
    },
    {
        "first_name": "Chinedu",
        "last_name": "Eze",
        "date_of_birth": date(1965, 2, 22),
        "gender": "MALE",
        "phone_number": "+2348012345003",
        "city": "Enugu",
        "state": "Enugu",
        "country": "Nigeria",
        "blood_group": "B+",
        "patient_type": "INPATIENT",
    },
    {
        "first_name": "Amina",
        "last_name": "Yusuf",
        "date_of_birth": date(2001, 8, 9),
        "gender": "FEMALE",
        "phone_number": "+2348012345004",
        "email": "amina.yusuf@example.com",
        "city": "Kano",
        "state": "Kano",
        "country": "Nigeria",
        "patient_type": "OUTPATIENT",
    },
    {
        "first_name": "Tunde",
        "last_name": "Adesanya",
        "date_of_birth": date(1985, 6, 30),
        "gender": "MALE",
        "phone_number": "+2348012345005",
        "city": "Ibadan",
        "state": "Oyo",
        "country": "Nigeria",
        "blood_group": "AB+",
        "patient_type": "OUTPATIENT",
    },
]


# ============================================================
# UTILITY: idempotent upserts for resources without a service
# ============================================================


def _upsert_facility(db: Session, payload: dict[str, Any]) -> Facility:
    """Idempotent facility upsert keyed by code."""
    existing = (
        db.query(Facility)
        .filter(
            or_(Facility.code == payload["code"], Facility.name == payload["name"]),
            Facility.is_deleted.is_(False),
        )
        .first()
    )
    if existing is not None:
        return existing
    facility = Facility(**payload)
    db.add(facility)
    db.flush()
    db.refresh(facility)
    return facility


def _upsert_department(
    db: Session, *, code: str, name: str, facility_id: Optional[int]
) -> Department:
    """Idempotent department upsert keyed by code."""
    existing = (
        db.query(Department)
        .filter(
            or_(Department.code == code, Department.name == name),
            Department.is_deleted.is_(False),
        )
        .first()
    )
    if existing is not None:
        # Keep facility_id current if it was missing before.
        if existing.facility_id is None and facility_id is not None:
            existing.facility_id = facility_id
            db.add(existing)
            db.flush()
        return existing
    department = Department(code=code, name=name, facility_id=facility_id)
    db.add(department)
    db.flush()
    db.refresh(department)
    return department


def _upsert_billable_service(
    db: Session, *, code: str, name: str, category: str, default_price: Decimal
) -> BillableService:
    """Idempotent billable-service upsert keyed by code."""
    existing = (
        db.query(BillableService)
        .filter(
            or_(BillableService.code == code, BillableService.name == name),
            BillableService.is_deleted.is_(False),
        )
        .first()
    )
    if existing is not None:
        return existing
    bs = BillableService(
        code=code,
        name=name,
        category=category,
        default_price=default_price,
    )
    db.add(bs)
    db.flush()
    db.refresh(bs)
    return bs


# ============================================================
# DOMAIN SEEDS
# ============================================================


def seed_facility(db: Session) -> Facility:
    """Seed the demo facility (idempotent)."""
    return _upsert_facility(db, DEMO_FACILITY)


def seed_departments(
    db: Session, *, facility_id: Optional[int]
) -> dict[str, Department]:
    """Seed every demo department, keyed by department code."""
    by_code: dict[str, Department] = {}
    for entry in DEMO_DEPARTMENTS:
        dept = _upsert_department(
            db,
            code=entry["code"],
            name=entry["name"],
            facility_id=facility_id,
        )
        by_code[dept.code] = dept
    return by_code


def seed_service_delivery_points(
    db: Session,
    *,
    facility_id: Optional[int],
    departments_by_code: dict[str, Department],
) -> dict[str, ServiceDeliveryPoint]:
    """Seed every demo SDP via the SDP service so validation runs."""
    service = ServiceDeliveryService(db)
    repo = service.repository
    by_code: dict[str, ServiceDeliveryPoint] = {}
    for entry in DEMO_SERVICE_DELIVERY_POINTS:
        existing = repo.get_by_code(entry["code"])
        if existing is not None:
            by_code[existing.code] = existing
            continue
        dept = departments_by_code.get(entry["department_code"])
        payload = ServiceDeliveryPointCreateSchema(
            name=entry["name"],
            code=entry["code"],
            service_point_type=entry["service_point_type"],
            department_id=dept.id if dept is not None else None,
            queue_prefix=entry.get("queue_prefix"),
            supports_appointments=entry.get("supports_appointments", False),
            supports_walk_in=entry.get("supports_walk_in", True),
        )
        sdp = service.create_service_delivery_point(payload)
        # Stamp facility_id post-create — the SDP create schema doesn't
        # accept facility_id today, so we patch directly.
        if facility_id is not None and sdp.facility_id is None:
            sdp.facility_id = facility_id
            db.add(sdp)
            db.flush()
            db.refresh(sdp)
        by_code[sdp.code] = sdp
    return by_code


def seed_wards_and_beds(
    db: Session,
    *,
    facility_id: Optional[int],
    bed_day_billable_services: dict[str, BillableService],
) -> dict[str, Ward]:
    """
    Seed every demo ward (with daily_rate) and the beds inside it.

    Wards are created via the WardService (validation + uniqueness checks),
    then the bed-day pricing fields and facility scoping are patched in.
    Beds are created via the BedService (which enforces ward existence and
    bed-no uniqueness within a ward).
    """
    ward_service = WardService(db)
    bed_service = BedService(db)
    by_code: dict[str, Ward] = {}

    for entry in DEMO_WARDS:
        # Idempotent: fall back to the existing row if found.
        existing = ward_service.repository.get_by_code(entry["code"])
        if existing is None:
            payload = WardCreateSchema(
                code=entry["code"],
                name=entry["name"],
                ward_type=entry.get("ward_type"),
                description=entry.get("description"),
            )
            ward = ward_service.create_ward(payload)
        else:
            ward = existing
        # Patch in pricing + facility id (not on the create schema yet).
        changed = False
        if entry.get("daily_rate") is not None and ward.daily_rate != entry["daily_rate"]:
            ward.daily_rate = entry["daily_rate"]
            changed = True
        if facility_id is not None and ward.facility_id is None:
            ward.facility_id = facility_id
            changed = True
        # Hook up the matching billable service (for finance reporting).
        bs_code = (
            "BED_DAY_ICU"
            if (entry.get("ward_type") or "").upper() == "ICU"
            else "BED_DAY_GENERAL"
        )
        bs = bed_day_billable_services.get(bs_code)
        if bs is not None and ward.billable_service_id is None:
            ward.billable_service_id = bs.id
            changed = True
        if changed:
            db.add(ward)
            db.flush()
            db.refresh(ward)
        by_code[ward.code] = ward

        # Beds for this ward
        for bed_entry in entry.get("beds", []):
            existing_bed = (
                db.query(Bed)
                .filter(
                    Bed.ward_id == ward.id,
                    Bed.bed_no == bed_entry["bed_no"].strip().upper(),
                    Bed.is_deleted.is_(False),
                )
                .first()
            )
            if existing_bed is not None:
                continue
            bed_payload = BedCreateSchema(
                ward_id=ward.id,
                bed_no=bed_entry["bed_no"],
                bed_status=BedStatus.AVAILABLE.value,
                bed_type=bed_entry.get("bed_type"),
                notes=bed_entry.get("notes"),
            )
            bed_service.create_bed(bed_payload)
    return by_code


def seed_billable_services(db: Session) -> dict[str, BillableService]:
    """Seed the billable-service catalogue (idempotent)."""
    by_code: dict[str, BillableService] = {}
    for entry in DEMO_BILLABLE_SERVICES:
        bs = _upsert_billable_service(db, **entry)
        by_code[bs.code] = bs
    return by_code


def seed_drugs(db: Session) -> dict[str, Drug]:
    """Seed drug categories first, then drugs. Both via service classes."""
    cat_service = DrugCategoryService(db)
    drug_service = DrugService(db)

    # Categories
    cats_by_code: dict[str, DrugCategory] = {}
    for entry in DEMO_DRUG_CATEGORIES:
        existing = (
            db.query(DrugCategory)
            .filter(
                DrugCategory.code == entry["code"],
                DrugCategory.is_deleted.is_(False),
            )
            .first()
        )
        if existing is None:
            payload = DrugCategoryCreateSchema(**entry)
            cat = cat_service.create(payload)
        else:
            cat = existing
        cats_by_code[cat.code] = cat

    # Drugs
    drugs_by_sku: dict[str, Drug] = {}
    for entry in DEMO_DRUGS:
        existing = (
            db.query(Drug)
            .filter(Drug.sku == entry["sku"], Drug.is_deleted.is_(False))
            .first()
        )
        if existing is not None:
            drugs_by_sku[existing.sku] = existing
            continue
        cat = cats_by_code.get(entry.pop("drug_category_code", None))
        payload = DrugCreateSchema(
            **entry,
            drug_category_id=cat.id if cat is not None else None,
        )
        drug = drug_service.create(payload)
        drugs_by_sku[drug.sku] = drug
    return drugs_by_sku


def seed_lab_tests(db: Session) -> dict[str, LabTestCatalog]:
    """Seed the laboratory test catalogue."""
    lab_service = LabCatalogService(db)
    by_code: dict[str, LabTestCatalog] = {}
    for entry in DEMO_LAB_TESTS:
        existing = (
            db.query(LabTestCatalog)
            .filter(
                LabTestCatalog.code == entry["code"].strip().upper(),
                LabTestCatalog.is_deleted.is_(False),
            )
            .first()
        )
        if existing is not None:
            by_code[existing.code] = existing
            continue
        payload = LabTestCatalogCreateSchema(**entry)
        try:
            lab = lab_service.create(payload)
        except AlreadyExistsError:
            lab = (
                db.query(LabTestCatalog)
                .filter(LabTestCatalog.code == entry["code"].strip().upper())
                .first()
            )
        if lab is not None:
            by_code[lab.code] = lab
    return by_code


def seed_notification_templates(db: Session) -> dict[str, NotificationTemplate]:
    """Seed canonical notification templates."""
    service = NotificationTemplateService(db)
    by_code: dict[str, NotificationTemplate] = {}
    for entry in DEMO_NOTIFICATION_TEMPLATES:
        existing = (
            db.query(NotificationTemplate)
            .filter(
                NotificationTemplate.code == entry["code"].strip().upper(),
                NotificationTemplate.is_deleted.is_(False),
            )
            .first()
        )
        if existing is not None:
            by_code[existing.code] = existing
            continue
        payload = NotificationTemplateCreateSchema(**entry)
        tpl = service.create(payload)
        by_code[tpl.code] = tpl
    return by_code


def seed_patients(db: Session, *, registered_by_user_id: Optional[int]) -> list[Patient]:
    """
    Seed sample patients via PatientService.

    The service runs duplicate-detection + MRN generation. We enable
    ``force_create_if_possible_duplicate`` so the seed isn't blocked by
    family-name overlaps.
    """
    service = PatientService(db)
    patients: list[Patient] = []
    for entry in DEMO_PATIENTS:
        # Idempotent: if a patient with the same first+last+DOB exists, reuse them.
        existing = (
            db.query(Patient)
            .filter(
                Patient.first_name == entry["first_name"],
                Patient.last_name == entry["last_name"],
                Patient.date_of_birth == entry.get("date_of_birth"),
                Patient.is_deleted.is_(False),
            )
            .first()
        )
        if existing is not None:
            patients.append(existing)
            continue
        payload = PatientCreateSchema(**entry)
        patient = service.create_patient(
            payload,
            registered_by_id=registered_by_user_id,
            force_create_if_possible_duplicate=True,
        )
        patients.append(patient)
    return patients


# ============================================================
# TOP-LEVEL ENTRYPOINT
# ============================================================


def seed_demo_data(
    db: Session,
    *,
    seed_security_first: bool = True,
    bootstrap_superuser: bool = False,
    superuser_username: Optional[str] = None,
    superuser_email: Optional[str] = None,
    superuser_password: Optional[str] = None,
) -> dict[str, Any]:
    """
    Run the full demo-dataset seed.

    Args:
        db: Active SQLAlchemy session. The function commits at the end of
            each domain step so a partial run leaves the DB in a usable
            state.
        seed_security_first: When True, also runs ``seed_security_baseline``
            up-front so permissions/roles/superuser exist before the demo
            data is inserted.
        bootstrap_superuser, superuser_username, superuser_email,
            superuser_password: Forwarded to ``seed_security_baseline``.

    Returns:
        dict: Per-step counts so callers can log progress.
    """
    summary: dict[str, Any] = {}

    if seed_security_first:
        summary["security"] = seed_security_baseline(
            db,
            bootstrap_superuser=bootstrap_superuser,
            superuser_username=superuser_username,
            superuser_email=superuser_email,
            superuser_password=superuser_password,
        )

    # Facility → departments → SDPs anchor the rest of the data.
    facility = seed_facility(db)
    db.commit()
    summary["facility"] = {"id": facility.id, "code": facility.code}

    departments = seed_departments(db, facility_id=facility.id)
    db.commit()
    summary["departments"] = len(departments)

    sdps = seed_service_delivery_points(
        db, facility_id=facility.id, departments_by_code=departments
    )
    summary["service_delivery_points"] = len(sdps)

    # Billable services need to exist before the wards reference them.
    billable_services = seed_billable_services(db)
    db.commit()
    summary["billable_services"] = len(billable_services)

    wards = seed_wards_and_beds(
        db,
        facility_id=facility.id,
        bed_day_billable_services=billable_services,
    )
    summary["wards"] = len(wards)

    # Drugs + lab catalogue + notification templates are independent.
    drugs = seed_drugs(db)
    summary["drugs"] = len(drugs)

    lab_tests = seed_lab_tests(db)
    summary["lab_tests"] = len(lab_tests)

    templates = seed_notification_templates(db)
    summary["notification_templates"] = len(templates)

    patients = seed_patients(
        db,
        registered_by_user_id=None,  # not bound to a specific seeding user
    )
    summary["patients"] = len(patients)

    db.commit()
    return summary


# ============================================================
# CLI
# ============================================================


def _run_cli() -> int:
    parser = argparse.ArgumentParser(description="Seed Carepoint HMS demo dataset.")
    parser.add_argument(
        "--skip-security",
        action="store_true",
        help="Don't re-run the permission / role / superuser baseline seed.",
    )
    parser.add_argument(
        "--bootstrap-superuser",
        action="store_true",
        help="Also create a bootstrap superuser (forwarded to security_seed).",
    )
    parser.add_argument("--username", type=str, help="Bootstrap superuser username.")
    parser.add_argument("--email", type=str, help="Bootstrap superuser email.")
    parser.add_argument("--password", type=str, help="Bootstrap superuser password.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        summary = seed_demo_data(
            db,
            seed_security_first=not args.skip_security,
            bootstrap_superuser=args.bootstrap_superuser,
            superuser_username=args.username,
            superuser_email=args.email,
            superuser_password=args.password,
        )
    finally:
        db.close()

    print("Demo dataset seeded.")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_cli())



'''
#CLI (with security baseline + bootstrap superuser)
python -m app.seeds.seed_data --bootstrap-superuser \
  --username admin --email admin@carepoint.local --password 'ChangeMe123!'


CLI (skip the security baseline if it's already been run):

python -m app.seeds.seed_data --skip-security

'''