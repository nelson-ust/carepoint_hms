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
    DentalProcedureCatalog,
    DentalRecall,
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
            "catalog_id": p.catalog_id,
            "billed_at": p.billed_at.isoformat() if getattr(p, "billed_at", None) else None,
            "is_billed": p.billed_at is not None,
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
        # A catalogue selection fills in name / code / cost when not supplied.
        catalog_id = data.get("catalog_id")
        if catalog_id is not None:
            cat = self.db.query(DentalProcedureCatalog).filter(
                DentalProcedureCatalog.id == catalog_id,
                DentalProcedureCatalog.is_deleted.is_(False)).first()
            if not cat:
                raise NotFoundError("Catalogue procedure not found.")
            if not data.get("procedure_name"):
                data["procedure_name"] = cat.name
            if not data.get("procedure_code"):
                data["procedure_code"] = cat.code
            if data.get("cost") is None:
                data["cost"] = cat.default_cost
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
            catalog_id=catalog_id,
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
        recalls_due = self.db.query(func.count(DentalRecall.id)).filter(
            DentalRecall.is_deleted.is_(False),
            DentalRecall.status.in_(["DUE", "SCHEDULED"]),
            DentalRecall.due_date <= date.today()).scalar() or 0
        unbilled = self.db.query(func.count(DentalProcedure.id)).filter(
            DentalProcedure.is_deleted.is_(False),
            DentalProcedure.status == DentalProcedureStatus.COMPLETED,
            DentalProcedure.billed_at.is_(None),
            DentalProcedure.cost.isnot(None)).scalar() or 0
        return {
            "charts_total": charts, "charts_open": open_charts,
            "procedures_planned": planned, "procedures_completed": completed,
            "completed_revenue": _d(revenue), "condition_distribution": distribution,
            "recalls_due": recalls_due, "procedures_unbilled": unbilled,
        }

    # ======================================================================
    # PROCEDURE CATALOGUE (price list)
    # ======================================================================
    def _catalog_dict(self, c: DentalProcedureCatalog) -> dict:
        return {
            "id": c.id, "code": c.code, "name": c.name, "category": c.category,
            "default_cost": _d(c.default_cost), "tooth_specific": c.tooth_specific,
            "billable_service_id": c.billable_service_id, "is_active": c.is_active,
            "description": c.description,
        }

    def list_catalog(self, *, search: Optional[str] = None, category: Optional[str] = None,
                     active_only: bool = False, skip: int = 0, limit: int = 200):
        q = self.db.query(DentalProcedureCatalog).filter(
            DentalProcedureCatalog.is_deleted.is_(False))
        if active_only:
            q = q.filter(DentalProcedureCatalog.is_active.is_(True))
        if category:
            q = q.filter(DentalProcedureCatalog.category == category)
        if search:
            like = f"%{search.strip()}%"
            q = q.filter(DentalProcedureCatalog.name.ilike(like) |
                         DentalProcedureCatalog.code.ilike(like))
        total = q.count()
        rows = (q.order_by(DentalProcedureCatalog.category, DentalProcedureCatalog.name)
                .offset(skip).limit(limit).all())
        return [self._catalog_dict(c) for c in rows], total

    def create_catalog(self, data: dict) -> dict:
        if not data.get("name"):
            raise BadRequestError("name is required.")
        c = DentalProcedureCatalog(
            code=(data.get("code") or None),
            name=data["name"].strip(),
            category=(data.get("category") or None),
            default_cost=Decimal(str(data.get("default_cost") or 0)),
            tooth_specific=bool(data.get("tooth_specific") or False),
            billable_service_id=data.get("billable_service_id"),
            is_active=data.get("is_active", True),
            description=(data.get("description") or None),
        )
        self.db.add(c)
        self.db.commit()
        self.db.refresh(c)
        return self._catalog_dict(c)

    def update_catalog(self, cat_id: int, data: dict) -> dict:
        c = self.db.query(DentalProcedureCatalog).filter(
            DentalProcedureCatalog.id == cat_id,
            DentalProcedureCatalog.is_deleted.is_(False)).first()
        if not c:
            raise NotFoundError("Catalogue entry not found.")
        for f in ("code", "name", "category", "tooth_specific", "billable_service_id",
                  "is_active", "description"):
            if f in data and data[f] is not None:
                setattr(c, f, data[f])
        if data.get("default_cost") is not None:
            c.default_cost = Decimal(str(data["default_cost"]))
        self.db.commit()
        self.db.refresh(c)
        return self._catalog_dict(c)

    def delete_catalog(self, cat_id: int) -> None:
        c = self.db.query(DentalProcedureCatalog).filter(
            DentalProcedureCatalog.id == cat_id,
            DentalProcedureCatalog.is_deleted.is_(False)).first()
        if not c:
            raise NotFoundError("Catalogue entry not found.")
        c.is_deleted = True
        self.db.commit()

    # ======================================================================
    # RECALLS (preventive-care follow-ups)
    # ======================================================================
    def _recall_dict(self, r: DentalRecall) -> dict:
        today = date.today()
        overdue = r.status in ("DUE", "SCHEDULED") and r.due_date is not None and r.due_date < today
        return {
            "id": r.id, "patient_id": r.patient_id, "chart_id": r.chart_id,
            "recall_type": r.recall_type,
            "due_date": r.due_date.isoformat() if r.due_date else None,
            "interval_months": r.interval_months, "status": r.status, "note": r.note,
            "created_by_staff_id": r.created_by_staff_id,
            "created_by": self._staff_name(r.created_by_staff_id),
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "is_overdue": bool(overdue),
            "patient": self._patient_brief(r.patient_id),
        }

    def list_recalls(self, *, patient_id: Optional[int] = None, status: Optional[str] = None,
                     due_before: Optional[date] = None, skip: int = 0, limit: int = 100):
        q = self.db.query(DentalRecall).filter(DentalRecall.is_deleted.is_(False))
        if patient_id:
            q = q.filter(DentalRecall.patient_id == patient_id)
        if status:
            q = q.filter(DentalRecall.status == status.upper())
        if due_before:
            q = q.filter(DentalRecall.due_date <= due_before)
        total = q.count()
        rows = (q.order_by(DentalRecall.due_date.asc()).offset(skip).limit(limit).all())
        return [self._recall_dict(r) for r in rows], total

    def create_recall(self, data: dict, actor) -> dict:
        patient_id = data.get("patient_id")
        if not patient_id:
            raise BadRequestError("patient_id is required.")
        if not data.get("due_date"):
            raise BadRequestError("due_date is required.")
        if not self.db.query(Patient.id).filter(
                Patient.id == patient_id, Patient.is_deleted.is_(False)).first():
            raise NotFoundError("Patient not found.")
        r = DentalRecall(
            patient_id=patient_id, chart_id=data.get("chart_id"),
            recall_type=(data.get("recall_type") or None),
            due_date=data["due_date"], interval_months=data.get("interval_months"),
            status=(data.get("status") or "DUE").upper(),
            note=data.get("note"),
            created_by_staff_id=self._staff_id_for_user(actor),
        )
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return self._recall_dict(r)

    def update_recall(self, recall_id: int, data: dict) -> dict:
        r = self.db.query(DentalRecall).filter(
            DentalRecall.id == recall_id, DentalRecall.is_deleted.is_(False)).first()
        if not r:
            raise NotFoundError("Recall not found.")
        for f in ("recall_type", "due_date", "interval_months", "note", "chart_id"):
            if f in data and data[f] is not None:
                setattr(r, f, data[f])
        if data.get("status"):
            r.status = data["status"].upper()
            if r.status == "COMPLETED" and r.completed_at is None:
                r.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(r)
        return self._recall_dict(r)

    # ======================================================================
    # TREATMENT-PLAN BILLING
    # ======================================================================
    def bill_chart(self, chart_id: int, *, procedure_ids: Optional[list[int]] = None,
                   actor=None) -> dict:
        """Push a chart's billable procedures onto the patient's visit charge
        sheet (reusing the shared billing engine), then mark them billed.

        Bills the given ``procedure_ids`` when supplied, otherwise every
        un-billed procedure on the chart that carries a cost."""
        from app.services.billing_service import BillingService

        chart = self.db.query(DentalChart).filter(
            DentalChart.id == chart_id, DentalChart.is_deleted.is_(False)).first()
        if not chart:
            raise NotFoundError("Dental chart not found.")
        if not chart.visit_id:
            raise BadRequestError(
                "This chart is not linked to a visit, so its procedures cannot be "
                "billed. Attach the chart to a visit first.")

        q = self.db.query(DentalProcedure).filter(
            DentalProcedure.is_deleted.is_(False),
            DentalProcedure.chart_id == chart_id,
            DentalProcedure.billed_at.is_(None))
        if procedure_ids:
            q = q.filter(DentalProcedure.id.in_(procedure_ids))
        procs = q.all()
        billable = [p for p in procs if p.cost is not None and Decimal(str(p.cost)) > 0]
        if not billable:
            raise BadRequestError(
                "No un-billed procedures with a cost were found on this chart.")

        # Resolve the ledger link from each procedure's catalogue entry (if any).
        cat_ids = {p.catalog_id for p in billable if p.catalog_id}
        bs_by_cat: dict[int, Optional[int]] = {}
        if cat_ids:
            for c in self.db.query(DentalProcedureCatalog).filter(
                    DentalProcedureCatalog.id.in_(cat_ids)).all():
                bs_by_cat[c.id] = c.billable_service_id

        items = []
        for p in billable:
            items.append({
                "billable_service_id": bs_by_cat.get(p.catalog_id) if p.catalog_id else None,
                "service_name": p.procedure_name,
                "service_code": p.procedure_code,
                "quantity": 1,
                "unit_price": p.cost,
                "discount_amount": 0,
                "source_reference": f"DENTAL-PROC-{p.id}",
            })

        actor_user_id = getattr(actor, "id", None)
        summary = BillingService(self.db).record_visit_services(
            chart.visit_id, items, rendered_by_user_id=actor_user_id)

        now = datetime.now(timezone.utc)
        for p in billable:
            p.billed_at = now
        self.db.commit()

        return {
            "billed_count": len(billable),
            "billed_procedure_ids": [p.id for p in billable],
            "billing": summary,
        }
