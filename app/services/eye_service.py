# app/services/eye_service.py
from __future__ import annotations

"""
Service layer for the Eye / Ophthalmology clinic module.

Covers the ophthalmic examination (visual acuity, refraction, intraocular
pressure, anterior / posterior segment findings) and the dispensed spectacle
prescription, so a standalone eye clinic can run its clinical encounter on the
shared patient / visit / billing backbone.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.enums import EncounterStatus, SpectacleLensType
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    EyeExam,
    Patient,
    SpectaclePrescription,
    StaffProfile,
    User,
)

_EYE_NUM_FIELDS = (
    "ref_sphere_od", "ref_sphere_os", "ref_cyl_od", "ref_cyl_os",
    "ref_add_od", "ref_add_os", "iop_od", "iop_os",
)
_EYE_INT_FIELDS = ("ref_axis_od", "ref_axis_os")
_EYE_STR_FIELDS = (
    "chief_complaint", "history_note", "external_note",
    "va_dist_unaided_od", "va_dist_unaided_os", "va_dist_aided_od", "va_dist_aided_os",
    "va_near_od", "va_near_os", "pinhole_od", "pinhole_os", "iop_method",
    "anterior_od", "anterior_os", "posterior_od", "posterior_os",
    "impression", "plan_note",
)
_RX_NUM = ("od_sphere", "od_cyl", "od_add", "os_sphere", "os_cyl", "os_add")
_RX_INT = ("od_axis", "os_axis")


def _d(v) -> Optional[str]:
    return None if v is None else str(v)


def _age(dob: Optional[date]) -> Optional[int]:
    if not dob:
        return None
    t = date.today()
    return t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))


class EyeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _staff_id_for_user(self, actor) -> Optional[int]:
        uid = getattr(actor, "id", None)
        if uid is None:
            return None
        sp = self.db.query(StaffProfile).filter(StaffProfile.user_id == uid).first()
        return sp.id if sp else None

    def _staff_name(self, staff_id: Optional[int]) -> Optional[str]:
        if not staff_id:
            return None
        row = (self.db.query(User.first_name, User.last_name)
               .join(StaffProfile, StaffProfile.user_id == User.id)
               .filter(StaffProfile.id == staff_id).first())
        return f"{row[0]} {row[1]}" if row else None

    def _patient_brief(self, patient_id: int) -> dict:
        p = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not p:
            return {"id": patient_id, "name": "Unknown", "hospital_number": None}
        return {
            "id": p.id, "name": f"{p.first_name} {p.last_name}",
            "hospital_number": p.hospital_number,
            "gender": getattr(p.gender, "value", p.gender) if p.gender else None,
            "age": _age(p.date_of_birth), "phone_number": p.phone_number,
        }

    def _rx_dict(self, r: SpectaclePrescription) -> dict:
        d = {
            "id": r.id, "patient_id": r.patient_id, "exam_id": r.exam_id,
            "prescriber_staff_id": r.prescriber_staff_id,
            "prescriber": self._staff_name(r.prescriber_staff_id),
            "prescribed_date": r.prescribed_date.isoformat() if r.prescribed_date else None,
            "pd": r.pd, "lens_type": getattr(r.lens_type, "value", r.lens_type),
            "usage": r.usage, "notes": r.notes,
            "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
        }
        for f in _RX_NUM:
            d[f] = _d(getattr(r, f))
        for f in _RX_INT:
            d[f] = getattr(r, f)
        return d

    def _exam_dict(self, e: EyeExam, *, full: bool = False) -> dict:
        d = {
            "id": e.id, "patient_id": e.patient_id, "visit_id": e.visit_id,
            "consultation_id": e.consultation_id,
            "clinician_staff_id": e.clinician_staff_id,
            "clinician": self._staff_name(e.clinician_staff_id),
            "status": getattr(e.status, "value", e.status),
            "examined_at": e.examined_at.isoformat() if e.examined_at else None,
            "created_at": e.created_at.isoformat() if getattr(e, "created_at", None) else None,
            "patient": self._patient_brief(e.patient_id),
        }
        for f in _EYE_STR_FIELDS:
            d[f] = getattr(e, f)
        for f in _EYE_NUM_FIELDS:
            d[f] = _d(getattr(e, f))
        for f in _EYE_INT_FIELDS:
            d[f] = getattr(e, f)
        if full:
            rxs = (self.db.query(SpectaclePrescription)
                   .filter(SpectaclePrescription.is_deleted.is_(False),
                           SpectaclePrescription.exam_id == e.id)
                   .order_by(SpectaclePrescription.id.desc()).all())
            d["prescriptions"] = [self._rx_dict(r) for r in rxs]
        return d

    def list_exams(self, *, patient_id: Optional[int], skip: int, limit: int):
        q = self.db.query(EyeExam).filter(EyeExam.is_deleted.is_(False))
        if patient_id:
            q = q.filter(EyeExam.patient_id == patient_id)
        total = q.count()
        rows = q.order_by(EyeExam.id.desc()).offset(skip).limit(limit).all()
        return [self._exam_dict(e) for e in rows], total

    def get_exam(self, exam_id: int) -> dict:
        e = (self.db.query(EyeExam)
             .options(selectinload(EyeExam.prescriptions))
             .filter(EyeExam.id == exam_id, EyeExam.is_deleted.is_(False)).first())
        if not e:
            raise NotFoundError("Eye exam not found.")
        return self._exam_dict(e, full=True)

    def _coerce(self, data: dict) -> dict:
        out = {}
        for f in _EYE_STR_FIELDS:
            if f in data:
                out[f] = data[f]
        for f in _EYE_NUM_FIELDS:
            if f in data and data[f] is not None:
                out[f] = Decimal(str(data[f]))
        for f in _EYE_INT_FIELDS:
            if f in data and data[f] is not None:
                out[f] = int(data[f])
        return out

    def create_exam(self, data: dict, actor) -> dict:
        patient_id = data.get("patient_id")
        if not patient_id:
            raise BadRequestError("patient_id is required.")
        if not self.db.query(Patient.id).filter(Patient.id == patient_id,
                                                Patient.is_deleted.is_(False)).first():
            raise NotFoundError("Patient not found.")
        e = EyeExam(
            patient_id=patient_id, visit_id=data.get("visit_id"),
            consultation_id=data.get("consultation_id"),
            clinician_staff_id=data.get("clinician_staff_id") or self._staff_id_for_user(actor),
            examined_at=datetime.now(timezone.utc),
            **self._coerce(data),
        )
        self.db.add(e)
        self.db.commit()
        self.db.refresh(e)
        return self._exam_dict(e, full=True)

    def update_exam(self, exam_id: int, data: dict) -> dict:
        e = self.db.query(EyeExam).filter(
            EyeExam.id == exam_id, EyeExam.is_deleted.is_(False)).first()
        if not e:
            raise NotFoundError("Eye exam not found.")
        for f, v in self._coerce(data).items():
            setattr(e, f, v)
        if data.get("clinician_staff_id"):
            e.clinician_staff_id = data["clinician_staff_id"]
        if data.get("status"):
            e.status = EncounterStatus(data["status"])
        self.db.commit()
        self.db.refresh(e)
        return self._exam_dict(e, full=True)

    def list_prescriptions(self, *, patient_id: Optional[int], skip: int, limit: int):
        q = self.db.query(SpectaclePrescription).filter(
            SpectaclePrescription.is_deleted.is_(False))
        if patient_id:
            q = q.filter(SpectaclePrescription.patient_id == patient_id)
        total = q.count()
        rows = q.order_by(SpectaclePrescription.id.desc()).offset(skip).limit(limit).all()
        return [self._rx_dict(r) for r in rows], total

    def get_prescription(self, rx_id: int) -> dict:
        r = self.db.query(SpectaclePrescription).filter(
            SpectaclePrescription.id == rx_id,
            SpectaclePrescription.is_deleted.is_(False)).first()
        if not r:
            raise NotFoundError("Prescription not found.")
        d = self._rx_dict(r)
        d["patient"] = self._patient_brief(r.patient_id)
        return d

    def create_prescription(self, data: dict, actor) -> dict:
        if not data.get("patient_id"):
            raise BadRequestError("patient_id is required.")
        kwargs = {}
        for f in _RX_NUM:
            if data.get(f) is not None:
                kwargs[f] = Decimal(str(data[f]))
        for f in _RX_INT:
            if data.get(f) is not None:
                kwargs[f] = int(data[f])
        r = SpectaclePrescription(
            patient_id=data["patient_id"], exam_id=data.get("exam_id"),
            prescriber_staff_id=data.get("prescriber_staff_id") or self._staff_id_for_user(actor),
            prescribed_date=data.get("prescribed_date") or date.today(),
            pd=data.get("pd"),
            lens_type=SpectacleLensType(data.get("lens_type") or "SINGLE_VISION"),
            usage=data.get("usage"), notes=data.get("notes"),
            **kwargs,
        )
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return self._rx_dict(r)

    def worklist(self, *, limit: int = 50):
        rows = (self.db.query(EyeExam).filter(EyeExam.is_deleted.is_(False))
                .order_by(EyeExam.id.desc()).limit(limit).all())
        return [self._exam_dict(e) for e in rows]

    def stats(self) -> dict:
        exams = self.db.query(func.count(EyeExam.id)).filter(
            EyeExam.is_deleted.is_(False)).scalar() or 0
        open_exams = self.db.query(func.count(EyeExam.id)).filter(
            EyeExam.is_deleted.is_(False),
            EyeExam.status == EncounterStatus.OPEN).scalar() or 0
        rx = self.db.query(func.count(SpectaclePrescription.id)).filter(
            SpectaclePrescription.is_deleted.is_(False)).scalar() or 0
        raised_iop = self.db.query(func.count(EyeExam.id)).filter(
            EyeExam.is_deleted.is_(False),
            (func.coalesce(EyeExam.iop_od, 0) > 21) | (func.coalesce(EyeExam.iop_os, 0) > 21)
        ).scalar() or 0
        return {
            "exams_total": exams, "exams_open": open_exams,
            "prescriptions_total": rx, "raised_iop_flagged": raised_iop,
        }
