# app/services/ortho_service.py
from __future__ import annotations

"""
Service layer for the Orthopaedics clinic module.

Covers the musculoskeletal assessment (OrthoAssessment) with its fracture
records (OrthoFracture), immobilisation / casting episodes
(OrthoImmobilisation) and the treatment plan of planned / completed
procedures (OrthoProcedure). Designed so a standalone orthopaedic clinic can
run its whole clinical encounter on the shared patient / visit / billing
backbone.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.enums import EncounterStatus, OrthoLaterality, OrthoProcedureStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    OrthoAssessment,
    OrthoFracture,
    OrthoImmobilisation,
    OrthoProcedure,
    Patient,
    StaffProfile,
    User,
)


def _d(v) -> Optional[str]:
    return None if v is None else str(v)


def _age(dob: Optional[date]) -> Optional[int]:
    if not dob:
        return None
    t = date.today()
    return t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))


def _enum(v, default="NOT_APPLICABLE"):
    return getattr(v, "value", v) if v is not None else default


class OrthoService:
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

    def _fracture_dict(self, f: OrthoFracture) -> dict:
        return {
            "id": f.id, "assessment_id": f.assessment_id, "bone": f.bone,
            "side": _enum(f.side), "pattern": f.pattern, "classification": f.classification,
            "is_open": f.is_open, "is_displaced": f.is_displaced,
            "management": f.management, "note": f.note,
        }

    def _immob_dict(self, m: OrthoImmobilisation) -> dict:
        return {
            "id": m.id, "assessment_id": m.assessment_id, "device_type": m.device_type,
            "body_part": m.body_part, "side": _enum(m.side),
            "applied_date": m.applied_date.isoformat() if m.applied_date else None,
            "expected_removal_date": m.expected_removal_date.isoformat() if m.expected_removal_date else None,
            "removed_date": m.removed_date.isoformat() if m.removed_date else None,
            "active": m.removed_date is None, "note": m.note,
        }

    def _proc_dict(self, p: OrthoProcedure) -> dict:
        return {
            "id": p.id, "patient_id": p.patient_id, "visit_id": p.visit_id,
            "assessment_id": p.assessment_id, "procedure_code": p.procedure_code,
            "procedure_name": p.procedure_name, "laterality": _enum(p.laterality),
            "status": _enum(p.status, "PLANNED"), "cost": _d(p.cost),
            "planned_date": p.planned_date.isoformat() if p.planned_date else None,
            "performed_date": p.performed_date.isoformat() if p.performed_date else None,
            "performed_by_staff_id": p.performed_by_staff_id,
            "performed_by": self._staff_name(p.performed_by_staff_id), "note": p.note,
            "created_at": p.created_at.isoformat() if getattr(p, "created_at", None) else None,
        }

    def _assessment_dict(self, a: OrthoAssessment, *, full: bool = False) -> dict:
        d = {
            "id": a.id, "patient_id": a.patient_id, "visit_id": a.visit_id,
            "consultation_id": a.consultation_id, "clinician_staff_id": a.clinician_staff_id,
            "clinician": self._staff_name(a.clinician_staff_id),
            "status": _enum(a.status, "OPEN"), "region": a.region,
            "laterality": _enum(a.laterality),
            "chief_complaint": a.chief_complaint, "mechanism_of_injury": a.mechanism_of_injury,
            "injury_date": a.injury_date.isoformat() if a.injury_date else None,
            "pain_score": a.pain_score, "rom_note": a.rom_note,
            "neurovascular_note": a.neurovascular_note, "special_tests": a.special_tests,
            "provisional_diagnosis": a.provisional_diagnosis, "imaging_modality": a.imaging_modality,
            "imaging_findings": a.imaging_findings, "plan_note": a.plan_note, "note": a.note,
            "examined_at": a.examined_at.isoformat() if a.examined_at else None,
            "created_at": a.created_at.isoformat() if getattr(a, "created_at", None) else None,
            "patient": self._patient_brief(a.patient_id),
        }
        if full:
            d["fractures"] = [self._fracture_dict(f) for f in sorted(a.fractures, key=lambda x: x.id) if not f.is_deleted]
            d["immobilisations"] = [self._immob_dict(m) for m in sorted(a.immobilisations, key=lambda x: x.id) if not m.is_deleted]
            procs = (self.db.query(OrthoProcedure)
                     .filter(OrthoProcedure.is_deleted.is_(False),
                             OrthoProcedure.assessment_id == a.id)
                     .order_by(OrthoProcedure.id.desc()).all())
            d["procedures"] = [self._proc_dict(p) for p in procs]
        else:
            d["fracture_count"] = self.db.query(func.count(OrthoFracture.id)).filter(
                OrthoFracture.is_deleted.is_(False), OrthoFracture.assessment_id == a.id).scalar() or 0
        return d

    # -- assessments ---------------------------------------------------
    def list_assessments(self, *, patient_id: Optional[int], skip: int, limit: int):
        q = self.db.query(OrthoAssessment).filter(OrthoAssessment.is_deleted.is_(False))
        if patient_id:
            q = q.filter(OrthoAssessment.patient_id == patient_id)
        total = q.count()
        rows = q.order_by(OrthoAssessment.id.desc()).offset(skip).limit(limit).all()
        return [self._assessment_dict(a) for a in rows], total

    def get_assessment(self, aid: int) -> dict:
        a = (self.db.query(OrthoAssessment)
             .options(selectinload(OrthoAssessment.fractures),
                      selectinload(OrthoAssessment.immobilisations))
             .filter(OrthoAssessment.id == aid, OrthoAssessment.is_deleted.is_(False)).first())
        if not a:
            raise NotFoundError("Assessment not found.")
        return self._assessment_dict(a, full=True)

    def create_assessment(self, data: dict, actor) -> dict:
        patient_id = data.get("patient_id")
        if not patient_id:
            raise BadRequestError("patient_id is required.")
        if not self.db.query(Patient.id).filter(Patient.id == patient_id,
                                                Patient.is_deleted.is_(False)).first():
            raise NotFoundError("Patient not found.")
        a = OrthoAssessment(
            patient_id=patient_id, visit_id=data.get("visit_id"),
            consultation_id=data.get("consultation_id"),
            clinician_staff_id=data.get("clinician_staff_id") or self._staff_id_for_user(actor),
            region=data.get("region"),
            laterality=OrthoLaterality(data.get("laterality") or "NOT_APPLICABLE"),
            chief_complaint=data.get("chief_complaint"),
            mechanism_of_injury=data.get("mechanism_of_injury"),
            injury_date=data.get("injury_date"), pain_score=data.get("pain_score"),
            rom_note=data.get("rom_note"), neurovascular_note=data.get("neurovascular_note"),
            special_tests=data.get("special_tests"),
            provisional_diagnosis=data.get("provisional_diagnosis"),
            imaging_modality=data.get("imaging_modality"),
            imaging_findings=data.get("imaging_findings"),
            plan_note=data.get("plan_note"), note=data.get("note"),
            examined_at=datetime.now(timezone.utc),
        )
        self.db.add(a)
        self.db.commit()
        self.db.refresh(a)
        return self._assessment_dict(a, full=True)

    def update_assessment(self, aid: int, data: dict) -> dict:
        a = self.db.query(OrthoAssessment).filter(
            OrthoAssessment.id == aid, OrthoAssessment.is_deleted.is_(False)).first()
        if not a:
            raise NotFoundError("Assessment not found.")
        for f in ("region", "chief_complaint", "mechanism_of_injury", "injury_date",
                  "pain_score", "rom_note", "neurovascular_note", "special_tests",
                  "provisional_diagnosis", "imaging_modality", "imaging_findings",
                  "plan_note", "note", "clinician_staff_id"):
            if f in data and data[f] is not None:
                setattr(a, f, data[f])
        if data.get("laterality"):
            a.laterality = OrthoLaterality(data["laterality"])
        if data.get("status"):
            a.status = EncounterStatus(data["status"])
        self.db.commit()
        self.db.refresh(a)
        return self._assessment_dict(a, full=True)

    # -- fractures -----------------------------------------------------
    def add_fracture(self, aid: int, data: dict) -> dict:
        a = self.db.query(OrthoAssessment).filter(
            OrthoAssessment.id == aid, OrthoAssessment.is_deleted.is_(False)).first()
        if not a:
            raise NotFoundError("Assessment not found.")
        if not data.get("bone"):
            raise BadRequestError("bone is required.")
        f = OrthoFracture(
            assessment_id=aid, patient_id=a.patient_id, bone=data["bone"],
            side=OrthoLaterality(data.get("side") or "NOT_APPLICABLE"),
            pattern=data.get("pattern"), classification=data.get("classification"),
            is_open=bool(data.get("is_open")), is_displaced=bool(data.get("is_displaced")),
            management=data.get("management"), note=data.get("note"),
        )
        self.db.add(f)
        self.db.commit()
        return self.get_assessment(aid)

    def delete_fracture(self, frac_id: int) -> dict:
        f = self.db.query(OrthoFracture).filter(
            OrthoFracture.id == frac_id, OrthoFracture.is_deleted.is_(False)).first()
        if not f:
            raise NotFoundError("Fracture not found.")
        f.is_deleted = True
        aid = f.assessment_id
        self.db.commit()
        return self.get_assessment(aid)

    # -- immobilisations ----------------------------------------------
    def add_immobilisation(self, aid: int, data: dict) -> dict:
        a = self.db.query(OrthoAssessment).filter(
            OrthoAssessment.id == aid, OrthoAssessment.is_deleted.is_(False)).first()
        if not a:
            raise NotFoundError("Assessment not found.")
        if not data.get("device_type"):
            raise BadRequestError("device_type is required.")
        m = OrthoImmobilisation(
            assessment_id=aid, patient_id=a.patient_id, device_type=data["device_type"],
            body_part=data.get("body_part"),
            side=OrthoLaterality(data.get("side") or "NOT_APPLICABLE"),
            applied_date=data.get("applied_date") or date.today(),
            expected_removal_date=data.get("expected_removal_date"),
            removed_date=data.get("removed_date"), note=data.get("note"),
        )
        self.db.add(m)
        self.db.commit()
        return self.get_assessment(aid)

    def remove_immobilisation(self, immob_id: int, removed_date: Optional[str]) -> dict:
        m = self.db.query(OrthoImmobilisation).filter(
            OrthoImmobilisation.id == immob_id, OrthoImmobilisation.is_deleted.is_(False)).first()
        if not m:
            raise NotFoundError("Immobilisation not found.")
        m.removed_date = removed_date or date.today()
        aid = m.assessment_id
        self.db.commit()
        return self.get_assessment(aid)

    # -- procedures ----------------------------------------------------
    def list_procedures(self, *, patient_id: Optional[int], status: Optional[str],
                        skip: int, limit: int):
        q = self.db.query(OrthoProcedure).filter(OrthoProcedure.is_deleted.is_(False))
        if patient_id:
            q = q.filter(OrthoProcedure.patient_id == patient_id)
        if status:
            q = q.filter(OrthoProcedure.status == OrthoProcedureStatus(status))
        total = q.count()
        rows = q.order_by(OrthoProcedure.id.desc()).offset(skip).limit(limit).all()
        return [self._proc_dict(p) for p in rows], total

    def create_procedure(self, data: dict, actor) -> dict:
        if not data.get("patient_id"):
            raise BadRequestError("patient_id is required.")
        if not data.get("procedure_name"):
            raise BadRequestError("procedure_name is required.")
        p = OrthoProcedure(
            patient_id=data["patient_id"], visit_id=data.get("visit_id"),
            assessment_id=data.get("assessment_id"),
            procedure_code=data.get("procedure_code"), procedure_name=data["procedure_name"],
            laterality=OrthoLaterality(data.get("laterality") or "NOT_APPLICABLE"),
            status=OrthoProcedureStatus(data.get("status") or "PLANNED"),
            cost=Decimal(str(data["cost"])) if data.get("cost") is not None else None,
            planned_date=data.get("planned_date"), performed_date=data.get("performed_date"),
            performed_by_staff_id=data.get("performed_by_staff_id"), note=data.get("note"),
        )
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return self._proc_dict(p)

    def update_procedure(self, proc_id: int, data: dict, actor) -> dict:
        p = self.db.query(OrthoProcedure).filter(
            OrthoProcedure.id == proc_id, OrthoProcedure.is_deleted.is_(False)).first()
        if not p:
            raise NotFoundError("Procedure not found.")
        for f in ("procedure_code", "procedure_name", "planned_date", "performed_date", "note"):
            if f in data and data[f] is not None:
                setattr(p, f, data[f])
        if data.get("laterality"):
            p.laterality = OrthoLaterality(data["laterality"])
        if data.get("cost") is not None:
            p.cost = Decimal(str(data["cost"]))
        if data.get("status"):
            p.status = OrthoProcedureStatus(data["status"])
            if data["status"] == "COMPLETED" and not p.performed_date:
                p.performed_date = date.today()
                if not p.performed_by_staff_id:
                    p.performed_by_staff_id = self._staff_id_for_user(actor)
        self.db.commit()
        self.db.refresh(p)
        return self._proc_dict(p)

    # -- worklist & stats ---------------------------------------------
    def worklist(self, *, limit: int = 50):
        rows = (self.db.query(OrthoAssessment).filter(OrthoAssessment.is_deleted.is_(False))
                .order_by(OrthoAssessment.id.desc()).limit(limit).all())
        return [self._assessment_dict(a) for a in rows]

    def stats(self) -> dict:
        assessments = self.db.query(func.count(OrthoAssessment.id)).filter(
            OrthoAssessment.is_deleted.is_(False)).scalar() or 0
        open_a = self.db.query(func.count(OrthoAssessment.id)).filter(
            OrthoAssessment.is_deleted.is_(False),
            OrthoAssessment.status == EncounterStatus.OPEN).scalar() or 0
        fractures = self.db.query(func.count(OrthoFracture.id)).filter(
            OrthoFracture.is_deleted.is_(False)).scalar() or 0
        active_casts = self.db.query(func.count(OrthoImmobilisation.id)).filter(
            OrthoImmobilisation.is_deleted.is_(False),
            OrthoImmobilisation.removed_date.is_(None)).scalar() or 0
        planned = self.db.query(func.count(OrthoProcedure.id)).filter(
            OrthoProcedure.is_deleted.is_(False),
            OrthoProcedure.status == OrthoProcedureStatus.PLANNED).scalar() or 0
        completed = self.db.query(func.count(OrthoProcedure.id)).filter(
            OrthoProcedure.is_deleted.is_(False),
            OrthoProcedure.status == OrthoProcedureStatus.COMPLETED).scalar() or 0
        revenue = self.db.query(func.coalesce(func.sum(OrthoProcedure.cost), 0)).filter(
            OrthoProcedure.is_deleted.is_(False),
            OrthoProcedure.status == OrthoProcedureStatus.COMPLETED).scalar() or 0
        return {
            "assessments_total": assessments, "assessments_open": open_a,
            "fractures_total": fractures, "active_immobilisations": active_casts,
            "procedures_planned": planned, "procedures_completed": completed,
            "completed_revenue": _d(revenue),
        }
