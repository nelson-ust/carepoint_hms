# app/utils/patient_export.py
from __future__ import annotations

"""
Build a full, point-in-time export of a patient's record from the tenant
database that holds it. Used by the interoperability flow once a data-exchange
request has patient consent + holding-hospital approval.

The builder is deliberately defensive: it serialises a curated set of
patient-keyed and visit-keyed clinical tables, skipping any model that isn't
present or doesn't have the expected key, so schema drift never breaks an
export.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

# Tables keyed directly by ``patient_id``.
_PATIENT_SECTIONS = [
    "PatientIdentifier", "PatientAllergy", "PatientConsent", "PatientInsurance",
    "MedicationProfile", "MedicationSchedule", "Visit", "Admission",
    "Appointment", "SurgicalCase", "InsuranceClaim", "Billing", "Invoice",
    "MembershipCard", "Referral",
]

# Visit-scoped clinical detail (gathered via the patient's visit ids). Candidate
# class names — any that don't exist are skipped.
_VISIT_SECTIONS = [
    "Consultation", "Diagnosis", "LabOrder", "LabResult", "RadiologyOrder",
    "Prescription", "PrescriptionItem", "VitalSigns", "VitalsRecord",
    "ClinicalNote", "TriageAssessment", "ProcedureOrder", "BillingItem",
]

_MAX_ROWS_PER_SECTION = 1000


def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    if hasattr(v, "value"):  # enum
        return v.value
    return str(v)


def _row(obj: Any) -> dict:
    out: dict = {}
    for col in obj.__table__.columns:
        out[col.name] = _jsonable(getattr(obj, col.name, None))
    return out


def build_patient_full_export(db: Session, global_patient_id: str) -> Optional[dict]:
    """
    Assemble the full record for the patient identified by ``global_patient_id``
    in ``db`` (the holding tenant's session). Returns ``None`` when no such
    patient exists here.
    """
    from app.models import all_models as m

    Patient = getattr(m, "Patient", None)
    if Patient is None:
        return None

    q = db.query(Patient).filter(Patient.global_patient_id == global_patient_id)
    if hasattr(Patient, "is_deleted"):
        q = q.filter(Patient.is_deleted.is_(False))
    patient = q.first()
    if patient is None:
        return None

    baseline = None
    BaselineProfile = getattr(m, "PatientBaselineProfile", None)
    if BaselineProfile is not None:
        bp = (
            db.query(BaselineProfile)
            .filter(BaselineProfile.patient_id == patient.id,
                    BaselineProfile.is_deleted.is_(False))
            .first()
        )
        if bp is not None:
            baseline = _row(bp)

    export: dict = {
        "schema_version": 1,
        "generated_at": _jsonable(datetime.utcnow()),
        "global_patient_id": global_patient_id,
        "patient": _row(patient),
        "baseline_profile": baseline,
        "sections": {},
        "counts": {},
    }
    pid = patient.id

    def _add(name: str, rows: list) -> None:
        export["sections"][name] = [_row(r) for r in rows]
        export["counts"][name] = len(rows)

    # Patient-keyed sections
    for model_name in _PATIENT_SECTIONS:
        model = getattr(m, model_name, None)
        if model is None or not hasattr(model, "patient_id"):
            continue
        try:
            query = db.query(model).filter(model.patient_id == pid)
            if hasattr(model, "is_deleted"):
                query = query.filter(model.is_deleted.is_(False))
            rows = query.limit(_MAX_ROWS_PER_SECTION).all()
            if rows:
                _add(model_name, rows)
        except Exception:
            continue

    # Visit-scoped clinical detail
    Visit = getattr(m, "Visit", None)
    visit_ids: list[int] = []
    if Visit is not None and hasattr(Visit, "patient_id"):
        try:
            vq = db.query(Visit.id).filter(Visit.patient_id == pid)
            if hasattr(Visit, "is_deleted"):
                vq = vq.filter(Visit.is_deleted.is_(False))
            visit_ids = [row[0] for row in vq.all()]
        except Exception:
            visit_ids = []

    if visit_ids:
        for model_name in _VISIT_SECTIONS:
            model = getattr(m, model_name, None)
            if model is None or not hasattr(model, "visit_id"):
                continue
            try:
                query = db.query(model).filter(model.visit_id.in_(visit_ids))
                if hasattr(model, "is_deleted"):
                    query = query.filter(model.is_deleted.is_(False))
                rows = query.limit(_MAX_ROWS_PER_SECTION).all()
                if rows:
                    _add(model_name, rows)
            except Exception:
                continue

    return export


# ---------------------------------------------------------------------------
# Scoped projections used by the developer/partner data APIs. Both reuse the
# full defensive export and then select the sections relevant to the scope, so
# schema drift never breaks them and no additional queries are introduced.
# ---------------------------------------------------------------------------

_HISTORY_SECTIONS = [
    "PatientAllergy", "MedicationProfile", "MedicationSchedule",
    "Visit", "Admission", "SurgicalCase", "Referral", "InsuranceClaim",
    "Consultation", "Diagnosis", "Prescription", "PrescriptionItem",
    "ProcedureOrder", "ClinicalNote", "TriageAssessment",
]

_DIAGNOSTICS_SECTIONS = [
    "LabOrder", "LabResult", "RadiologyOrder",
    "VitalSigns", "VitalsRecord", "TriageAssessment",
]


def _project(full: Optional[dict], keep: list, kind: str) -> Optional[dict]:
    if full is None:
        return None
    sections = {k: v for k, v in (full.get("sections") or {}).items() if k in keep}
    counts = {k: v for k, v in (full.get("counts") or {}).items() if k in keep}
    return {
        "schema_version": full.get("schema_version"),
        "kind": kind,
        "generated_at": full.get("generated_at"),
        "global_patient_id": full.get("global_patient_id"),
        "patient": full.get("patient"),
        "sections": sections,
        "counts": counts,
    }


def build_patient_medical_history(db: Session, global_patient_id: str) -> Optional[dict]:
    """Patient demographics + longitudinal medical history (no billing/finance)."""
    return _project(build_patient_full_export(db, global_patient_id),
                    _HISTORY_SECTIONS, "MEDICAL_HISTORY")


def build_patient_baseline_diagnostics(db: Session, global_patient_id: str) -> Optional[dict]:
    """Baseline diagnostics: vitals, laboratory results and radiology."""
    return _project(build_patient_full_export(db, global_patient_id),
                    _DIAGNOSTICS_SECTIONS, "BASELINE_DIAGNOSTICS")
