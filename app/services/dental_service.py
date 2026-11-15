# app/services/dental_service.py
from __future__ import annotations

"""
Service layer for the Dental clinic module.

Covers the dental examination / odontogram (DentalChart + DentalToothRecord)
and the treatment plan of planned / completed procedures (DentalProcedure).
Designed so a standalone dental clinic can run its whole clinical encounter on
top of the shared patient / visit / billing backbone.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.enums import DentalProcedureStatus, DentalToothCondition, EncounterStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    DentalChart,
    DentalProcedure,
    DentalToothRecord,
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


class DentalService:
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
            "id": p.id,
            "name": f"{p.first_name} {p.last_name}",
            "hospital_number": p.hospital_number,
            "gender": getattr(p.gender, "value", p.gender) if p.gender else None,
            "age": _age(p.date_of_birth),
            "phone_number": p.phone_number,
        }

    def _tooth_dict(self, t: DentalToothRecord) -> dict:
        return {
            "id": t.id, "tooth_number": t.tooth_number,
            "condition": getattr(t.condition, "value", t.condition),
            "surfaces": t.surfaces, "mobility": t.mobility, "note": t.note,
        }

    def _proc_dict(self, p: DentalProcedure) -> dict:
        return {
            "id": p.id, "patient_id": p.patient_id, "visit_id": p.visit_id,
            "chart_id": p.chart_id, "tooth_number": p.tooth_number, "surfaces": p.surfaces,
            "procedure_code": p.procedure_code, "procedure_name": p.procedure_name,
            "status": getattr(p.status, "value", p.status), "cost": _d(p.cost),
            "planned_date": p.planned_date.isoformat() if p.planned_date else None,
            "performed_date": p.performed_date.isoformat() if p.performed_date else None,
            "performed_by_staff_id": p.performed_by_staff_id,
            "performed_by": self._staff_name(p.performed_by_staff_id),
            "note": p.note,
            "created_at": p.created_at.isoformat() if getattr(p, "created_at", None) else None,
        }

    def _chart_dict(self, c: DentalChart, *, full: bool = False) -> dict:
        d = {
            "id": c.id, "patient_id": c.patient_id, "visit_id": c.visit_id,
            "consultation_id": c.consultation_id,
            "clinician_staff_id": c.clinician_staff_id,
            "clinician": self._staff_name(c.clinician_staff_id),
            "status": getattr(c.status, "value", c.status),
            "numbering_system": c.numbering_system, "dentition": c.dentition,
            "chief_complaint": c.chief_complaint, "oral_hygiene": c.oral_hygiene,
            "occlusion_note": c.occlusion_note, "soft_tissue_note": c.soft_tissue_note,
            "periodontal_summary": c.periodontal_summary, "xray_findings": c.xray_findings,
            "note": c.note,
            "examined_at": c.examined_at.isoformat() if c.examined_at else None,
            "created_at": c.created_at.isoformat() if getattr(c, "created_at", None) else None,
            "patient": self._patient_brief(c.patient_id),
        }
        if full:
            teeth = sorted([t for t in c.teeth if not t.is_deleted], key=lambda t: t.tooth_number)
            d["teeth"] = [self._tooth_dict(t) for t in teeth]
            procs = (self.db.query(DentalProcedure)
                     .filter(DentalProcedure.is_deleted.is_(False),
                             DentalProcedure.chart_id == c.id)
                     .order_by(DentalProcedure.id.desc()).all())
            d["procedures"] = [self._proc_dict(p) for p in procs]
        else:
            d["teeth_charted"] = self.db.query(func.count(DentalToothRecord.id)).filter(
                DentalToothRecord.is_deleted.is_(False),
                DentalToothRecord.chart_id == c.id).scalar() or 0
        return d

    def list_charts(self, *, patient_id: Optional[int], skip: int, limit: int):
        q = self.db.query(DentalChart).filter(DentalChart.is_deleted.is_(False))
        if patient_id:
            q = q.filter(DentalChart.patient_id == patient_id)
        total = q.count()
        rows = (q.order_by(DentalChart.id.desc()).offset(skip).limit(limit).all())
        return [self._chart_dict(c) for c in rows], total

    def get_chart(self, chart_id: int) -> dict:
        c = (self.db.query(DentalChart)
             .options(selectinload(DentalChart.teeth))
             .filter(DentalChart.id == chart_id, DentalChart.is_deleted.is_(False)).first())
        if not c:
            raise NotFoundError("Dental chart not found.")
        return self._chart_dict(c, full=True)

    def create_chart(self, data: dict, actor) -> dict:
        patient_id = data.get("patient_id")
        if not patient_id:
            raise BadRequestError("patient_id is required.")
        if not self.db.query(Patient.id).filter(Patient.id == patient_id,
                                                Patient.is_deleted.is_(False)).first():
            raise NotFoundError("Patient not found.")
        c = DentalChart(
            patient_id=patient_id,
            visit_id=data.get("visit_id"),
            consultation_id=data.get("consultation_id"),
            clinician_staff_id=data.get("clinician_staff_id") or self._staff_id_for_user(actor),
            numbering_system=(data.get("numbering_system") or "FDI"),
            dentition=(data.get("dentition") or "PERMANENT"),
            chief_complaint=data.get("chief_complaint"),
            oral_hygiene=data.get("oral_hygiene"),
            occlusion_note=data.get("occlusion_note"),
            soft_tissue_note=data.get("soft_tissue_note"),
            periodontal_summary=data.get("periodontal_summary"),
            xray_findings=data.get("xray_findings"),
            note=data.get("note"),
            examined_at=datetime.now(timezone.utc),
        )
        self.db.add(c)
        self.db.commit()
        self.db.refresh(c)
        return self._chart_dict(c, full=True)

    def update_chart(self, chart_id: int, data: dict) -> dict:
        c = self.db.query(DentalChart).filter(
            DentalChart.id == chart_id, DentalChart.is_deleted.is_(False)).first()
        if not c:
            raise NotFoundError("Dental chart not found.")
        for f in ("chief_complaint", "oral_hygiene", "occlusion_note", "soft_tissue_note",
                  "periodontal_summary", "xray_findings", "note", "numbering_system",
                  "dentition", "clinician_staff_id"):
            if f in data and data[f] is not None:
                setattr(c, f, data[f])
        if data.get("status"):
            c.status = EncounterStatus(data["status"])
        self.db.commit()
        self.db.refresh(c)
        return self._chart_dict(c, full=True)

    def set_teeth(self, chart_id: int, teeth: list[dict]) -> dict:
        c = self.db.query(DentalChart).filter(
            DentalChart.id == chart_id, DentalChart.is_deleted.is_(False)).first()
        if not c:
            raise NotFoundError("Dental chart not found.")
        existing = {t.tooth_number: t for t in
                    self.db.query(DentalToothRecord).filter(
                        DentalToothRecord.is_deleted.is_(False),
                        DentalToothRecord.chart_id == chart_id).all()}
        for row in teeth:
            tn = row.get("tooth_number")
            if tn is None:
                continue
            cond = row.get("condition") or "HEALTHY"
            rec = existing.get(tn)
            is_clear = (cond == "HEALTHY" and not row.get("surfaces") and not row.get("note")
                        and not row.get("mobility"))
            if rec:
                if is_clear:
                    rec.is_deleted = True
                    continue
                rec.condition = DentalToothCondition(cond)
                rec.surfaces = row.get("surfaces")
                rec.mobility = row.get("mobility")
                rec.note = row.get("note")
            elif not is_clear:
                self.db.add(DentalToothRecord(
                    chart_id=chart_id, patient_id=c.patient_id, tooth_number=tn,
                    condition=DentalToothCondition(cond), surfaces=row.get("surfaces"),
                    mobility=row.get("mobility"), note=row.get("note")))
        self.db.commit()
        self.db.refresh(c)
        return self.get_chart(chart_id)

    def list_procedures(self, *, patient_id: Optional[int], status: Optional[str],
                        skip: int, limit: int):
        q = self.db.query(DentalProcedure).filter(DentalProcedure.is_deleted.is_(False))
        if patient_id:
            q = q.filter(DentalProcedure.patient_id == patient_id)
        if status:
            q = q.filter(DentalProcedure.status == DentalProcedureStatus(status))
        total = q.count()
        rows = q.order_by(DentalProcedure.id.desc()).offset(skip).limit(limit).all()
        return [self._proc_dict(p) for p in rows], total

    def create_procedure(self, data: dict, actor) -> dict:
        if not data.get("patient_id"):
            raise BadRequestError("patient_id is required.")
        if not data.get("procedure_name"):
            raise BadRequestError("procedure_name is required.")
        p = DentalProcedure(
            patient_id=data["patient_id"], visit_id=data.get("visit_id"),
            chart_id=data.get("chart_id"), tooth_number=data.get("tooth_number"),
            surfaces=data.get("surfaces"), procedure_code=data.get("procedure_code"),
            procedure_name=data["procedure_name"],
            status=DentalProcedureStatus(data.get("status") or "PLANNED"),
            cost=Decimal(str(data["cost"])) if data.get("cost") is not None else None,
            planned_date=data.get("planned_date"),
            performed_date=data.get("performed_date"),
            performed_by_staff_id=data.get("performed_by_staff_id"),
            note=data.get("note"),
        )
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return self._proc_dict(p)

    def update_procedure(self, proc_id: int, data: dict, actor) -> dict:
        p = self.db.query(DentalProcedure).filter(
            DentalProcedure.id == proc_id, DentalProcedure.is_deleted.is_(False)).first()
        if not p:
            raise NotFoundError("Procedure not found.")
        for f in ("procedure_code", "procedure_name", "tooth_number", "surfaces",
                  "planned_date", "performed_date", "note"):
            if f in data and data[f] is not None:
                setattr(p, f, data[f])
        if data.get("cost") is not None:
            p.cost = Decimal(str(data["cost"]))
        if data.get("status"):
            p.status = DentalProcedureStatus(data["status"])
            if data["status"] == "COMPLETED" and not p.performed_date:
                p.performed_date = date.today()
                if not p.performed_by_staff_id:
                    p.performed_by_staff_id = self._staff_id_for_user(actor)
        self.db.commit()
        self.db.refresh(p)
        return self._proc_dict(p)

    def worklist(self, *, limit: int = 50):
        rows = (self.db.query(DentalChart)
                .filter(DentalChart.is_deleted.is_(False))
                .order_by(DentalChart.id.desc()).limit(limit).all())
        return [self._chart_dict(c) for c in rows]

    def stats(self) -> dict:
        charts = self.db.query(func.count(DentalChart.id)).filter(
            DentalChart.is_deleted.is_(False)).scalar() or 0
        open_charts = self.db.query(func.count(DentalChart.id)).filter(
            DentalChart.is_deleted.is_(False),
            DentalChart.status == EncounterStatus.OPEN).scalar() or 0
        planned = self.db.query(func.count(DentalProcedure.id)).filter(
            DentalProcedure.is_deleted.is_(False),
            DentalProcedure.status == DentalProcedureStatus.PLANNED).scalar() or 0
        completed = self.db.query(func.count(DentalProcedure.id)).filter(
            DentalProcedure.is_deleted.is_(False),
            DentalProcedure.status == DentalProcedureStatus.COMPLETED).scalar() or 0
        revenue = self.db.query(func.coalesce(func.sum(DentalProcedure.cost), 0)).filter(
            DentalProcedure.is_deleted.is_(False),
            DentalProcedure.status == DentalProcedureStatus.COMPLETED).scalar() or 0
        dist_rows = (self.db.query(DentalToothRecord.condition, func.count(DentalToothRecord.id))
                     .filter(DentalToothRecord.is_deleted.is_(False))
                     .group_by(DentalToothRecord.condition).all())
        distribution = [{"condition": getattr(c, "value", c), "count": n} for c, n in dist_rows]
        return {
            "charts_total": charts, "charts_open": open_charts,
            "procedures_planned": planned, "procedures_completed": completed,
            "completed_revenue": _d(revenue), "condition_distribution": distribution,
        }
