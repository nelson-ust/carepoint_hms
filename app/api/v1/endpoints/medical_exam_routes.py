# app/api/v1/endpoints/medical_exam_routes.py
"""
Medical Examination (medical fitness assessment) workflow.

Packages define which investigations an examination requires; starting an
examination auto-generates the laboratory order (charges captured, lab
queued); the reviewing physician finalises with clinical findings,
recommendations and a fitness determination once all results are released;
and a branded, QR-verifiable PDF report is generated on demand.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser
from app.core.exceptions import BadRequestError, NotFoundError
from app.dependencies.role import require_permission
from app.models.all_models import (
    LabOrder,
    LabOrderItem,
    LabTestCatalog,
    MedicalExamPackage,
    MedicalExamination,
    Patient,
    StaffProfile,
    User,
    Visit,
)
from app.utils.security_event_util import record_security_event

router = APIRouter(prefix="/medical-exams", tags=["Medical Examinations"])

FITNESS_STATUSES = {
    "FIT", "FIT_WITH_RESTRICTIONS", "TEMPORARILY_UNFIT", "PERMANENTLY_UNFIT",
}
EXAM_TYPES = [
    "PRE_EMPLOYMENT", "SCHOOL_ADMISSION", "IMMIGRATION", "INSURANCE",
    "ANNUAL_WELLNESS", "EXECUTIVE_SCREENING", "OCCUPATIONAL_FITNESS",
    "DRIVERS_LICENSE", "OTHER",
]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PackagePayload(BaseModel):
    code: str = Field(..., min_length=2, max_length=60)
    name: str = Field(..., min_length=2, max_length=200)
    exam_type: str = Field(..., max_length=60)
    description: Optional[str] = None
    lab_test_ids: list[int] = Field(default_factory=list)
    price: Optional[Decimal] = Field(None, ge=0)
    is_active: bool = True


class PackageUpdatePayload(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    exam_type: Optional[str] = Field(None, max_length=60)
    description: Optional[str] = None
    lab_test_ids: Optional[list[int]] = None
    price: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None


class StartExamPayload(BaseModel):
    visit_id: int
    package_id: int


class FinalizeExamPayload(BaseModel):
    fitness_status: str
    clinical_findings: Optional[str] = None
    recommendations: Optional[str] = None
    restrictions: Optional[str] = None
    #: Explicit acknowledgement when finalising with outstanding results.
    override_incomplete_results: bool = False


def _pkg_out(p: MedicalExamPackage) -> dict:
    return {
        "id": p.id, "code": p.code, "name": p.name, "exam_type": p.exam_type,
        "description": p.description, "lab_test_ids": p.lab_test_ids or [],
        "price": str(p.price) if p.price is not None else None,
        "is_active": p.is_active,
    }


def _results_progress(order: Optional[LabOrder]) -> dict:
    if order is None:
        return {"total": 0, "released": 0, "complete": True}
    items = [i for i in (order.items or []) if not i.is_deleted]
    released = sum(1 for i in items
                   if getattr(i, "result", None) is not None
                   and getattr(i.result, "released_at", None) is not None)
    return {"total": len(items), "released": released,
            "complete": len(items) > 0 and released == len(items)}


def _exam_out(db: Session, e: MedicalExamination) -> dict:
    patient = e.patient
    name = " ".join(x for x in (getattr(patient, "first_name", None),
                                getattr(patient, "last_name", None)) if x)
    reviewer = None
    if e.reviewed_by_staff_id:
        pair = (db.query(StaffProfile, User)
                .outerjoin(User, User.id == StaffProfile.user_id)
                .filter(StaffProfile.id == e.reviewed_by_staff_id).first())
        if pair:
            sp, u = pair
            reviewer = (f"{getattr(u, 'first_name', '') or ''} "
                        f"{getattr(u, 'last_name', '') or ''}").strip() or sp.staff_no
    return {
        "id": e.id, "exam_no": e.exam_no, "visit_id": e.visit_id,
        "patient_id": e.patient_id, "patient_name": name or None,
        "hospital_number": getattr(patient, "hospital_number", None),
        "package": _pkg_out(e.package) if e.package else None,
        "lab_order_id": e.lab_order_id,
        "lab_order_no": getattr(e.lab_order, "order_no", None) if e.lab_order else None,
        "status": e.status, "fitness_status": e.fitness_status,
        "clinical_findings": e.clinical_findings,
        "recommendations": e.recommendations,
        "restrictions": e.restrictions,
        "reviewed_by": reviewer, "reviewed_at": e.reviewed_at,
        "created_at": getattr(e, "date_created", None),
        "results": _results_progress(e.lab_order),
    }


# ---------------------------------------------------------------------------
# Packages
# ---------------------------------------------------------------------------

@router.get("/packages", summary="List medical examination packages")
def list_packages(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    rows = (db.query(MedicalExamPackage)
            .filter(MedicalExamPackage.is_deleted.is_(False))
            .order_by(MedicalExamPackage.name).all())
    return {"exam_types": EXAM_TYPES, "items": [_pkg_out(p) for p in rows]}


@router.post("/packages", status_code=201, summary="Create an examination package")
def create_package(
    payload: PackagePayload,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    __: Annotated[User, Depends(require_permission("VISIT_ROUTE", "PATIENT_UPDATE"))],
):
    from app.core.exceptions import AlreadyExistsError
    code = payload.code.strip().upper()
    if db.query(MedicalExamPackage).filter(MedicalExamPackage.code == code).first():
        raise AlreadyExistsError(message=f"A package with code '{code}' already exists.")
    if payload.lab_test_ids:
        found = {t.id for t in db.query(LabTestCatalog.id.label("id"))
                 .filter(LabTestCatalog.id.in_(payload.lab_test_ids)).all()}
        missing = set(payload.lab_test_ids) - {f[0] if isinstance(f, tuple) else f for f in found}
        if missing:
            raise BadRequestError(message=f"Unknown lab test ids: {sorted(missing)}")
    pkg = MedicalExamPackage(**{**payload.model_dump(), "code": code})
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return _pkg_out(pkg)


@router.patch("/packages/{package_id}", summary="Update an examination package")
def update_package(
    package_id: int,
    payload: PackageUpdatePayload,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    __: Annotated[User, Depends(require_permission("VISIT_ROUTE", "PATIENT_UPDATE"))],
):
    pkg = (db.query(MedicalExamPackage)
           .filter(MedicalExamPackage.id == package_id,
                   MedicalExamPackage.is_deleted.is_(False)).first())
    if pkg is None:
        raise NotFoundError(message="Package not found.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(pkg, k, v)
    db.commit()
    db.refresh(pkg)
    return _pkg_out(pkg)


# ---------------------------------------------------------------------------
# Examinations
# ---------------------------------------------------------------------------

def _exam_query(db: Session):
    return (db.query(MedicalExamination)
            .options(joinedload(MedicalExamination.package),
                     joinedload(MedicalExamination.patient),
                     joinedload(MedicalExamination.lab_order)
                     .joinedload(LabOrder.items)
                     .joinedload(LabOrderItem.result))
            .filter(MedicalExamination.is_deleted.is_(False)))


@router.get("", summary="List medical examinations")
def list_exams(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    status_filter: Optional[str] = None,
):
    q = _exam_query(db)
    if status_filter:
        q = q.filter(MedicalExamination.status == status_filter.strip().upper())
    return [_exam_out(db, e) for e in q.order_by(MedicalExamination.id.desc()).limit(200).all()]


@router.post("", status_code=201, summary="Start a medical examination for a visit")
def start_exam(
    payload: StartExamPayload,
    actor: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    __: Annotated[User, Depends(require_permission("VISIT_ROUTE", "CONSULTATION_READ"))],
):
    visit = (db.query(Visit)
             .filter(Visit.id == payload.visit_id, Visit.is_deleted.is_(False)).first())
    if visit is None:
        raise NotFoundError(message="Visit not found.")
    pkg = (db.query(MedicalExamPackage)
           .filter(MedicalExamPackage.id == payload.package_id,
                   MedicalExamPackage.is_deleted.is_(False),
                   MedicalExamPackage.is_active.is_(True)).first())
    if pkg is None:
        raise NotFoundError(message="Examination package not found or inactive.")
    existing = (db.query(MedicalExamination)
                .filter(MedicalExamination.visit_id == visit.id,
                        MedicalExamination.is_deleted.is_(False),
                        MedicalExamination.status != "COMPLETED").first())
    if existing is not None:
        raise BadRequestError(
            message=f"Examination {existing.exam_no} is already in progress on this visit."
        )

    # Auto-generate the package's laboratory order through the standard
    # ordering service — charges captured, lab queued, timeline updated.
    lab_order_id = None
    if pkg.lab_test_ids:
        from app.schemas.lab_order_schema import (
            LabOrderCreateSchema, LabOrderItemCreateSchema,
        )
        from app.services.lab_order_service import LabOrderService
        order = LabOrderService(db).create_order(
            LabOrderCreateSchema(
                visit_id=visit.id,
                clinical_note=f"[MEDICAL EXAM] {pkg.name}",
                items=[LabOrderItemCreateSchema(lab_test_catalog_id=tid)
                       for tid in pkg.lab_test_ids],
                auto_capture_charge=True,
            ),
            actor_user_id=getattr(actor, "id", None),
        )
        lab_order_id = order.id

    exam_no = (f"MEX-{datetime.now(timezone.utc).strftime('%Y%m%d')}-"
               f"{hashlib.sha256(f'{visit.id}-{datetime.now(timezone.utc).isoformat()}'.encode()).hexdigest()[:6].upper()}")
    exam = MedicalExamination(
        exam_no=exam_no, visit_id=visit.id, patient_id=visit.patient_id,
        package_id=pkg.id, lab_order_id=lab_order_id, status="IN_PROGRESS",
    )
    db.add(exam)
    record_security_event(
        db, user_id=getattr(actor, "id", None),
        event_type="MEDICAL_EXAM_STARTED", severity="INFO",
        event_detail=f"Medical examination {exam_no} ({pkg.name}) started on visit {visit.id}.",
        event_metadata={"visit_id": visit.id, "package_id": pkg.id},
    )
    db.commit()
    db.refresh(exam)
    return _exam_out(db, _exam_query(db).filter(MedicalExamination.id == exam.id).first())


@router.get("/{exam_id}", summary="Examination detail (with results progress)")
def get_exam(
    exam_id: int,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    exam = _exam_query(db).filter(MedicalExamination.id == exam_id).first()
    if exam is None:
        raise NotFoundError(message="Medical examination not found.")
    return _exam_out(db, exam)


@router.post("/{exam_id}/finalize", summary="Record findings + fitness determination")
def finalize_exam(
    exam_id: int,
    payload: FinalizeExamPayload,
    actor: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    __: Annotated[User, Depends(require_permission("CONSULTATION_READ", "PATIENT_UPDATE"))],
):
    fitness = payload.fitness_status.strip().upper()
    if fitness not in FITNESS_STATUSES:
        raise BadRequestError(
            message=f"fitness_status must be one of {sorted(FITNESS_STATUSES)}."
        )
    exam = _exam_query(db).filter(MedicalExamination.id == exam_id).first()
    if exam is None:
        raise NotFoundError(message="Medical examination not found.")
    if exam.status == "COMPLETED":
        raise BadRequestError(message="This examination is already finalised.")

    progress = _results_progress(exam.lab_order)
    if not progress["complete"] and not payload.override_incomplete_results:
        raise BadRequestError(
            message=(f"Only {progress['released']} of {progress['total']} results are "
                     "released. Wait for the laboratory, or finalise explicitly with "
                     "override_incomplete_results.")
        )

    sp = (db.query(StaffProfile)
          .filter(StaffProfile.user_id == getattr(actor, "id", None),
                  StaffProfile.is_deleted.is_(False)).first())
    exam.fitness_status = fitness
    exam.clinical_findings = payload.clinical_findings
    exam.recommendations = payload.recommendations
    exam.restrictions = payload.restrictions
    exam.reviewed_by_staff_id = sp.id if sp else None
    exam.reviewed_at = datetime.now(timezone.utc)
    exam.status = "COMPLETED"
    record_security_event(
        db, user_id=getattr(actor, "id", None),
        event_type="MEDICAL_EXAM_FINALIZED", severity="INFO",
        event_detail=f"Medical examination {exam.exam_no} finalised: {fitness}.",
        event_metadata={"exam_id": exam.id, "fitness_status": fitness},
    )
    db.commit()
    return _exam_out(db, _exam_query(db).filter(MedicalExamination.id == exam_id).first())


@router.get("/{exam_id}/report.pdf", summary="Branded Medical Examination Report (PDF)")
def exam_report_pdf(
    exam_id: int,
    actor: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    from fastapi import Response
    from app.api.v1.endpoints.hr_routes import _load_tenant_logo_path
    from app.core.multitenancy import get_current_tenant
    from app.utils.medical_exam_pdf import build_medical_exam_report_pdf

    exam = _exam_query(db).filter(MedicalExamination.id == exam_id).first()
    if exam is None:
        raise NotFoundError(message="Medical examination not found.")
    if exam.status != "COMPLETED":
        raise BadRequestError(message="Finalise the examination before generating the report.")

    patient = exam.patient
    rows = []
    if exam.lab_order:
        for item in (exam.lab_order.items or []):
            result = getattr(item, "result", None)
            catalog = getattr(item, "lab_test_catalog", None)
            rows.append({
                "test": getattr(catalog, "name", None) or "Test",
                "result": (result.result_value or result.result_text or "-")
                if result and result.released_at else "Pending",
                "unit": (result.unit_of_measure if result else None)
                or getattr(catalog, "unit_of_measure", None) or "",
                "reference_range": (result.reference_range if result else None)
                or getattr(catalog, "reference_range", None) or "",
            })

    reviewer_name, designation, license_no = None, None, None
    if exam.reviewed_by_staff_id:
        pair = (db.query(StaffProfile, User)
                .outerjoin(User, User.id == StaffProfile.user_id)
                .filter(StaffProfile.id == exam.reviewed_by_staff_id).first())
        if pair:
            sp, u = pair
            reviewer_name = (f"{getattr(u, 'first_name', '') or ''} "
                             f"{getattr(u, 'last_name', '') or ''}").strip() or sp.staff_no
            designation = sp.job_title or sp.designation
            license_no = sp.professional_license_no

    hospital, contact = "Hospital", None
    try:
        tenant = get_current_tenant()
        if tenant is not None:
            hospital = getattr(tenant, "name", None) or hospital
            contact = getattr(tenant, "contact_email", None) or getattr(tenant, "billing_email", None)
    except Exception:
        pass
    verify_code = hashlib.sha256(
        f"CPHMS-MEX|{exam.exam_no}|{exam.reviewed_at}".encode()
    ).hexdigest()[:10].upper()

    logo_path = _load_tenant_logo_path(db)
    try:
        pdf_bytes = build_medical_exam_report_pdf(
            hospital_name=hospital, hospital_contact=contact, logo_path=logo_path,
            exam_no=exam.exam_no,
            exam_type=(exam.package.exam_type if exam.package else "MEDICAL_EXAM"),
            package_name=(exam.package.name if exam.package else ""),
            patient={
                "name": " ".join(x for x in (patient.first_name, patient.last_name) if x),
                "hospital_number": patient.hospital_number,
                "date_of_birth": str(patient.date_of_birth or "") or None,
                "gender": str(getattr(patient.gender, "value", patient.gender) or "") or None,
            },
            visit_number=getattr(exam.visit, "visit_number", None),
            examined_at=exam.reviewed_at,
            rows=rows,
            clinical_findings=exam.clinical_findings,
            recommendations=exam.recommendations,
            restrictions=exam.restrictions,
            fitness_status=exam.fitness_status or "",
            physician_name=reviewer_name, designation=designation,
            license_no=license_no, verify_code=verify_code,
        )
    finally:
        if logo_path:
            try:
                import os as _os
                _os.remove(logo_path)
            except OSError:
                pass
    record_security_event(
        db, user_id=getattr(actor, "id", None),
        event_type="MEDICAL_EXAM_REPORT_DOWNLOADED", severity="INFO",
        event_detail=f"Report for {exam.exam_no} generated.",
        event_metadata={"exam_id": exam.id},
    )
    db.commit()
    safe = "".join(ch for ch in exam.exam_no if ch.isalnum() or ch in "-_")
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="medical-exam-{safe}.pdf"'})
