# app/api/v1/endpoints/baseline_profile_routes.py
"""
Patient Baseline Medical Profile.

Lifelong clinical information maintained independently of any visit — blood
group, genotype, rhesus factor, allergies, chronic conditions, long-term
medications, past/family/social/immunisation/obstetric history, disability,
organ-donor status, baseline anthropometry and primary physician. Every
update bumps the profile version and records a full before-snapshot in the
revision trail, so the record is auditable across the patient's lifetime.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser
from app.core.exceptions import BadRequestError, NotFoundError
from app.dependencies.role import require_permission
from app.models.all_models import (
    Patient,
    PatientBaselineProfile,
    PatientBaselineProfileRevision,
    StaffProfile,
    User,
)
from app.utils.security_event_util import record_security_event

router = APIRouter(prefix="/patients", tags=["Patient Baseline Profile"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

#: Fields stored on the baseline profile row itself.
_PROFILE_FIELDS = (
    "rhesus_factor", "g6pd_status", "hepatitis_b_status", "hepatitis_c_status",
    "hiv_status", "blood_sugar_baseline", "lipid_profile_baseline",
    "known_allergies", "chronic_conditions",
    "existing_diagnoses", "long_term_medications", "past_medical_history",
    "past_surgical_history", "family_history", "social_history",
    "immunization_history", "obstetric_history", "disability_info",
    "organ_donor", "baseline_height_cm", "baseline_weight_kg",
    "primary_physician_staff_id", "additional_notes",
)
#: Baseline fields that live on the Patient row (kept there because the rest
#: of the system — exports, cards, portal — already reads them from Patient).
_PATIENT_FIELDS = ("blood_group", "genotype", "allergies", "chronic_conditions")


class BaselineProfileUpdateSchema(BaseModel):
    blood_group: Optional[str] = Field(None, max_length=10)
    genotype: Optional[str] = Field(None, max_length=10)
    rhesus_factor: Optional[str] = Field(None, max_length=10)
    g6pd_status: Optional[str] = Field(None, max_length=40)
    hepatitis_b_status: Optional[str] = Field(None, max_length=40)
    hepatitis_c_status: Optional[str] = Field(None, max_length=40)
    hiv_status: Optional[str] = Field(None, max_length=40)
    blood_sugar_baseline: Optional[str] = Field(None, max_length=80)
    lipid_profile_baseline: Optional[str] = None
    known_allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    existing_diagnoses: Optional[str] = None
    long_term_medications: Optional[str] = None
    past_medical_history: Optional[str] = None
    past_surgical_history: Optional[str] = None
    family_history: Optional[str] = None
    social_history: Optional[str] = None
    immunization_history: Optional[str] = None
    obstetric_history: Optional[str] = None
    disability_info: Optional[str] = None
    organ_donor: Optional[bool] = None
    baseline_height_cm: Optional[Decimal] = Field(None, ge=0, le=300)
    baseline_weight_kg: Optional[Decimal] = Field(None, ge=0, le=700)
    primary_physician_staff_id: Optional[int] = None
    additional_notes: Optional[str] = None


def _enum_val(v: Any) -> Any:
    return getattr(v, "value", v)


def _profile_out(db: Session, patient: Patient,
                 profile: Optional[PatientBaselineProfile]) -> dict:
    physician_name = None
    physician_id = getattr(profile, "primary_physician_staff_id", None) if profile else None
    if physician_id:
        pair = (
            db.query(StaffProfile, User)
            .outerjoin(User, User.id == StaffProfile.user_id)
            .filter(StaffProfile.id == physician_id).first()
        )
        if pair:
            sp, u = pair
            physician_name = (f"{getattr(u, 'first_name', '') or ''} "
                              f"{getattr(u, 'last_name', '') or ''}").strip() or sp.staff_no
    out: dict = {
        "patient_id": patient.id,
        "blood_group": _enum_val(patient.blood_group),
        "genotype": _enum_val(patient.genotype),
        # Narrative allergies/conditions live on Patient; the profile's
        # known_allergies supersedes when set.
        "version": getattr(profile, "version", 0) if profile else 0,
        "updated_at": (getattr(profile, "date_updated", None)
                       or getattr(profile, "date_created", None)),
        "primary_physician_name": physician_name,
        "emergency_contact_name": patient.emergency_contact_name,
        "emergency_contact_phone": patient.emergency_contact_phone,
        "emergency_contact_relationship": patient.emergency_contact_relationship,
    }
    for f in _PROFILE_FIELDS:
        out[f] = getattr(profile, f, None) if profile else None
    if not out.get("known_allergies"):
        out["known_allergies"] = patient.allergies
    if not out.get("chronic_conditions"):
        out["chronic_conditions"] = patient.chronic_conditions
    return out


def _get_patient(db: Session, patient_id: int) -> Patient:
    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id, Patient.is_deleted.is_(False))
        .first()
    )
    if patient is None:
        raise NotFoundError(message="Patient not found.")
    return patient


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/{patient_id}/baseline-profile",
    summary="The patient's lifelong Baseline Medical Profile",
)
def get_baseline_profile(
    patient_id: int,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    __: Annotated[User, Depends(require_permission("PATIENT_READ"))],
):
    patient = _get_patient(db, patient_id)
    profile = (
        db.query(PatientBaselineProfile)
        .filter(PatientBaselineProfile.patient_id == patient_id,
                PatientBaselineProfile.is_deleted.is_(False))
        .first()
    )
    return _profile_out(db, patient, profile)


@router.put(
    "/{patient_id}/baseline-profile",
    summary="Update the Baseline Medical Profile (versioned, audited)",
)
def update_baseline_profile(
    patient_id: int,
    payload: BaselineProfileUpdateSchema,
    actor: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    __: Annotated[User, Depends(require_permission("PATIENT_UPDATE"))],
):
    patient = _get_patient(db, patient_id)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise BadRequestError(message="No baseline fields were provided.")

    if data.get("primary_physician_staff_id") is not None:
        sp = (
            db.query(StaffProfile)
            .filter(StaffProfile.id == data["primary_physician_staff_id"],
                    StaffProfile.is_deleted.is_(False))
            .first()
        )
        if sp is None:
            raise BadRequestError(message="Primary physician staff profile not found.")

    profile = (
        db.query(PatientBaselineProfile)
        .filter(PatientBaselineProfile.patient_id == patient_id,
                PatientBaselineProfile.is_deleted.is_(False))
        .first()
    )
    if profile is None:
        profile = PatientBaselineProfile(patient_id=patient_id, version=0)
        db.add(profile)
        db.flush()

    # Snapshot BEFORE the change for the revision trail.
    before = {f: (str(getattr(profile, f)) if getattr(profile, f) is not None else None)
              for f in _PROFILE_FIELDS}
    before.update({
        "blood_group": str(_enum_val(patient.blood_group) or "") or None,
        "genotype": str(_enum_val(patient.genotype) or "") or None,
    })

    changed: list[str] = []
    for f in _PROFILE_FIELDS:
        if f in data:
            new_val = data[f]
            if str(getattr(profile, f, None)) != str(new_val):
                changed.append(f)
            setattr(profile, f, new_val)

    # Blood group / genotype / narrative allergies stay on Patient so every
    # existing consumer (exports, cards, portal) keeps working.
    if "blood_group" in data and data["blood_group"]:
        if str(_enum_val(patient.blood_group)) != data["blood_group"]:
            changed.append("blood_group")
        patient.blood_group = data["blood_group"]
    if "genotype" in data and data["genotype"]:
        if str(_enum_val(patient.genotype)) != data["genotype"]:
            changed.append("genotype")
        patient.genotype = data["genotype"]
    if "known_allergies" in data:
        patient.allergies = data["known_allergies"]
    if "chronic_conditions" in data:
        patient.chronic_conditions = data["chronic_conditions"]

    if not changed:
        db.rollback()
        return _profile_out(db, patient, profile)

    profile.version = (profile.version or 0) + 1
    db.add(PatientBaselineProfileRevision(
        profile_id=profile.id,
        patient_id=patient_id,
        version=profile.version,
        snapshot_json=before,
        changed_fields=changed,
        changed_by_user_id=getattr(actor, "id", None),
        changed_at=datetime.now(timezone.utc),
    ))
    record_security_event(
        db, user_id=getattr(actor, "id", None),
        event_type="PATIENT_BASELINE_PROFILE_UPDATED", severity="INFO",
        event_detail=f"Baseline profile v{profile.version} for patient {patient_id}: "
                     f"{', '.join(changed)}.",
        event_metadata={"patient_id": patient_id, "version": profile.version,
                        "changed_fields": changed},
    )
    # Best-effort in-app notification so the patient sees, in the portal, that
    # their baseline diagnostic information was updated by an authorised clinician.
    try:
        if patient.user_id:
            from app.repositories.notification_repository import NotificationRepository
            from app.core.enums import NotificationChannel, NotificationStatus
            NotificationRepository(db).create(
                channel=NotificationChannel.IN_APP,
                status=NotificationStatus.SENT,
                sent_at=datetime.now(timezone.utc),
                patient_id=patient.id,
                subject="Baseline diagnostic profile updated",
                body=("Your baseline diagnostic information was updated by your "
                      "care team. You can view it anytime under Baseline "
                      "Diagnostics in your patient portal."),
                event_code="PATIENT_BASELINE_PROFILE_UPDATED",
                payload_metadata={"version": profile.version,
                                  "changed_fields": changed},
            )
    except Exception:
        pass
    db.commit()
    db.refresh(profile)
    return _profile_out(db, patient, profile)


@router.get(
    "/{patient_id}/baseline-profile/revisions",
    summary="Audit history of baseline profile changes",
)
def list_baseline_profile_revisions(
    patient_id: int,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    __: Annotated[User, Depends(require_permission("PATIENT_READ"))],
):
    _get_patient(db, patient_id)
    revisions = (
        db.query(PatientBaselineProfileRevision)
        .filter(PatientBaselineProfileRevision.patient_id == patient_id,
                PatientBaselineProfileRevision.is_deleted.is_(False))
        .order_by(PatientBaselineProfileRevision.version.desc())
        .all()
    )
    user_ids = {r.changed_by_user_id for r in revisions if r.changed_by_user_id}
    names = {}
    if user_ids:
        for u in db.query(User).filter(User.id.in_(user_ids)).all():
            names[u.id] = f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username
    return [{
        "version": r.version,
        "changed_at": r.changed_at,
        "changed_by": names.get(r.changed_by_user_id),
        "changed_fields": r.changed_fields,
        "previous_values": {k: v for k, v in (r.snapshot_json or {}).items()
                            if k in (r.changed_fields or [])},
    } for r in revisions]


@router.get(
    "/{patient_id}/diagnostics",
    summary="Inline diagnostics: baseline indicators + chronological released results",
)
def get_patient_diagnostics(
    patient_id: int,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    __: Annotated[User, Depends(require_permission("PATIENT_READ"))],
    limit_orders: int = 25,
):
    """One optimized payload powering the reusable inline results viewer:
    the baseline diagnostic profile plus every released laboratory result for
    the patient, newest first, grouped per request with reference ranges —
    so the same panel can be embedded in consultation, patient record,
    referral review, admission and ward screens."""
    from sqlalchemy.orm import joinedload
    from app.models.all_models import LabOrder, LabOrderItem, Visit

    patient = _get_patient(db, patient_id)
    profile = (
        db.query(PatientBaselineProfile)
        .filter(PatientBaselineProfile.patient_id == patient_id,
                PatientBaselineProfile.is_deleted.is_(False))
        .first()
    )

    orders = (
        db.query(LabOrder)
        .join(Visit, Visit.id == LabOrder.visit_id)
        .options(
            joinedload(LabOrder.items).joinedload(LabOrderItem.result),
            joinedload(LabOrder.items).joinedload(LabOrderItem.lab_test_catalog),
        )
        .filter(Visit.patient_id == patient_id, LabOrder.is_deleted.is_(False))
        .order_by(LabOrder.ordered_at.desc())
        .limit(max(1, min(limit_orders, 100)))
        .all()
    )
    visit_numbers = {
        v.id: getattr(v, "visit_number", None)
        for v in db.query(Visit).filter(
            Visit.id.in_({o.visit_id for o in orders} or {0})).all()
    }

    lab_history = []
    for order in orders:
        released = []
        for item in (order.items or []):
            result = getattr(item, "result", None)
            if result is None or getattr(result, "released_at", None) is None:
                continue
            catalog = getattr(item, "lab_test_catalog", None)
            released.append({
                "test": getattr(catalog, "name", None) or "Test",
                "code": getattr(catalog, "code", None),
                "result": result.result_value or result.result_text or "-",
                "unit": result.unit_of_measure or getattr(catalog, "unit_of_measure", None),
                "reference_range": result.reference_range
                or getattr(catalog, "reference_range", None),
                "interpretation": result.interpretation,
                "released_at": result.released_at,
                "verified": result.verified_at is not None,
            })
        if released:
            lab_history.append({
                "order_id": order.id,
                "order_no": order.order_no,
                "visit_id": order.visit_id,
                "visit_number": visit_numbers.get(order.visit_id),
                "ordered_at": order.ordered_at,
                "results": released,
            })

    return {
        "patient_id": patient_id,
        "baseline": _profile_out(db, patient, profile),
        "lab_history": lab_history,
    }


# ---------------------------------------------------------------------------
# Canonical Baseline Diagnostic Records
# ---------------------------------------------------------------------------
#
# A single source of truth turning the raw baseline profile into an ordered,
# categorised set of diagnostic records — reused by the Patient Portal JSON
# feed and the branded PDF report so both always agree.

#: (field, label, category, source). ``source`` selects how the value is read.
_BASELINE_CATALOG = (
    ("blood_group", "Blood Group", "Blood & Genetic Markers", "patient"),
    ("genotype", "Genotype", "Blood & Genetic Markers", "patient"),
    ("rhesus_factor", "Rhesus (Rh) Factor", "Blood & Genetic Markers", "profile"),
    ("g6pd_status", "G6PD Status", "Blood & Genetic Markers", "profile"),
    ("hepatitis_b_status", "Hepatitis B Status", "Infectious Disease Screening", "profile"),
    ("hepatitis_c_status", "Hepatitis C Status", "Infectious Disease Screening", "profile"),
    ("hiv_status", "HIV Status", "Infectious Disease Screening", "profile"),
    ("blood_sugar_baseline", "Blood Sugar Baseline", "Metabolic Baselines", "profile"),
    ("lipid_profile_baseline", "Lipid Profile Baseline", "Metabolic Baselines", "profile"),
    ("baseline_height_cm", "Baseline Height (cm)", "Metabolic Baselines", "profile"),
    ("baseline_weight_kg", "Baseline Weight (kg)", "Metabolic Baselines", "profile"),
    ("known_allergies", "Known Allergies", "Clinical Alerts", "allergy"),
    ("chronic_conditions", "Chronic Medical Conditions", "Clinical Alerts", "chronic"),
    ("existing_diagnoses", "Existing Diagnoses", "Clinical Alerts", "profile"),
    ("long_term_medications", "Long-term Medications & Alerts", "Clinical Alerts", "profile"),
    ("disability_info", "Disability Information", "Clinical Alerts", "profile"),
    ("immunization_history", "Immunisation Status", "Immunisation", "profile"),
    ("organ_donor", "Organ Donor", "Additional Baseline Information", "organ_donor"),
)

#: Fixed display order for categories.
_BASELINE_CATEGORY_ORDER = (
    "Blood & Genetic Markers",
    "Infectious Disease Screening",
    "Metabolic Baselines",
    "Clinical Alerts",
    "Immunisation",
    "Additional Baseline Information",
)

#: Records that are clinical alerts get a factual interpretation label.
_BASELINE_INTERP = {
    "known_allergies": "Active clinical alert",
    "chronic_conditions": "Active clinical alert",
    "existing_diagnoses": "Active clinical alert",
    "long_term_medications": "Ongoing therapy",
}


def _baseline_field_value(patient: Patient,
                          profile: Optional[PatientBaselineProfile],
                          field: str, source: str) -> Optional[str]:
    if source == "patient":
        return (str(_enum_val(getattr(patient, field, None)))
                if getattr(patient, field, None) not in (None, "") else None)
    if source == "allergy":
        v = getattr(profile, "known_allergies", None) if profile else None
        v = v or patient.allergies
        return str(v) if v else None
    if source == "chronic":
        v = getattr(profile, "chronic_conditions", None) if profile else None
        v = v or patient.chronic_conditions
        return str(v) if v else None
    if source == "organ_donor":
        v = getattr(profile, "organ_donor", None) if profile else None
        if v is None:
            return None
        return "Yes" if v else "No"
    v = getattr(profile, field, None) if profile else None
    return str(v) if v not in (None, "") else None


def _baseline_field_changes(revisions: list) -> dict:
    """field -> (changed_at, changed_by_name). Newest change wins.
    ``revisions`` must be ordered newest-first and each item carries
    ``changed_fields``, ``changed_at`` and a resolved ``_changed_by_name``."""
    out: dict = {}
    for r in revisions:
        for f in (getattr(r, "changed_fields", None) or []):
            if f not in out:
                out[f] = (getattr(r, "changed_at", None),
                          getattr(r, "_changed_by_name", None))
    return out


def build_baseline_diagnostic_records(
    db: Session,
    patient: Patient,
    profile: Optional[PatientBaselineProfile],
    revisions: Optional[list] = None,
) -> list[dict]:
    """Grouped, ordered diagnostic records for portal + PDF. Each category is
    ``{"name", "records": [{key,label,category,value,interpretation,
    verification_status,verified_by,recorded_at,updated_at}]}``. Records with
    no value are still returned (value=None, status=NOT_RECORDED) so the portal
    can show what is on file vs. outstanding — the PDF filters empties itself."""
    revisions = revisions or []
    # Resolve changer names once.
    user_ids = {getattr(r, "changed_by_user_id", None) for r in revisions
                if getattr(r, "changed_by_user_id", None)}
    names: dict = {}
    if user_ids:
        for u in db.query(User).filter(User.id.in_(user_ids)).all():
            names[u.id] = (f"{u.first_name or ''} {u.last_name or ''}".strip()
                           or u.username)
    for r in revisions:
        r._changed_by_name = names.get(getattr(r, "changed_by_user_id", None))
    changes = _baseline_field_changes(revisions)

    recorded_at = (getattr(profile, "date_created", None) if profile else None)
    physician_name = None
    physician_id = getattr(profile, "primary_physician_staff_id", None) if profile else None
    if physician_id:
        pair = (
            db.query(StaffProfile, User)
            .outerjoin(User, User.id == StaffProfile.user_id)
            .filter(StaffProfile.id == physician_id).first()
        )
        if pair:
            sp, u = pair
            physician_name = (f"{getattr(u, 'first_name', '') or ''} "
                              f"{getattr(u, 'last_name', '') or ''}").strip() or sp.staff_no

    grouped: dict = {name: [] for name in _BASELINE_CATEGORY_ORDER}
    for field, label, category, source in _BASELINE_CATALOG:
        value = _baseline_field_value(patient, profile, field, source)
        changed_at, changed_by = changes.get(field, (None, None))
        if value is None:
            status = "NOT_RECORDED"
        elif changed_by:
            status = "VERIFIED"
        else:
            status = "RECORDED"
        grouped.setdefault(category, []).append({
            "key": field,
            "label": label,
            "category": category,
            "value": value,
            "interpretation": _BASELINE_INTERP.get(field) if value else None,
            "verification_status": status,
            "verified_by": changed_by or (physician_name if value else None),
            "recorded_at": recorded_at,
            "updated_at": changed_at or recorded_at,
        })

    return [{"name": name, "records": grouped.get(name, [])}
            for name in _BASELINE_CATEGORY_ORDER if grouped.get(name)]


def baseline_patient_dict(patient: Patient) -> dict:
    """Compact patient identity block for the baseline report/feed."""
    return {
        "id": patient.id,
        "name": f"{patient.first_name or ''} {patient.last_name or ''}".strip(),
        "hospital_number": patient.hospital_number,
        "global_patient_id": patient.global_patient_id,
        "date_of_birth": patient.date_of_birth,
        "gender": _enum_val(patient.gender),
    }
