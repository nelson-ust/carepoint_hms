# app/services/visit_timeline_service.py
"""
Visit timeline: one chronological, auditable stream of everything that
happened during a patient encounter.

The timeline is a READ MODEL — assembled on demand from the authoritative
clinical tables (triage, consultations, orders, results, prescriptions,
dispensing, procedures, billing, admission, discharge and the visit-flow
routing steps). Nothing is duplicated into a side table, so the timeline can
never drift from the record of truth, and every entry carries its timestamp,
staff member, department and reference.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models import all_models as m


def _iso(v: Any) -> Optional[str]:
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v) if v else None


def _val(v: Any) -> Any:
    return getattr(v, "value", v)


class VisitTimelineService:
    """Assemble the chronological activity stream for one visit."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def build(self, visit_id: int) -> dict:
        visit = (
            self.db.query(m.Visit)
            .filter(m.Visit.id == visit_id, m.Visit.is_deleted.is_(False))
            .first()
        )
        if visit is None:
            raise NotFoundError(message="Visit not found.")

        events: list[dict] = []
        staff_ids: set[int] = set()
        user_ids: set[int] = set()

        def add(at: Any, *, type_: str, title: str, department: Optional[str] = None,
                notes: Optional[str] = None, ref: Optional[str] = None,
                staff_profile_id: Optional[int] = None, user_id: Optional[int] = None) -> None:
            if at is None:
                return
            if staff_profile_id:
                staff_ids.add(staff_profile_id)
            if user_id:
                user_ids.add(user_id)
            events.append({
                "at": _iso(at), "type": type_, "title": title,
                "department": department, "notes": notes, "ref": ref,
                "staff_profile_id": staff_profile_id, "user_id": user_id,
            })

        sdp_names = {
            s.id: s.name for s in self.db.query(m.ServiceDeliveryPoint)
            .filter(m.ServiceDeliveryPoint.is_deleted.is_(False)).all()
        }

        # ----- Visit lifecycle ------------------------------------------------
        add(getattr(visit, "check_in_time", None) or getattr(visit, "date_created", None),
            type_="VISIT_STARTED", title="Visit initiated", department="Registration",
            ref=getattr(visit, "visit_number", None),
            user_id=getattr(visit, "created_by_id", None))
        if getattr(visit, "check_out_time", None):
            add(visit.check_out_time, type_="VISIT_COMPLETED", title="Visit completed",
                department="Front desk")

        # ----- Care-pathway routing steps -------------------------------------
        for step in (
            self.db.query(m.VisitFlowStep)
            .filter(m.VisitFlowStep.visit_id == visit_id,
                    m.VisitFlowStep.is_deleted.is_(False))
            .order_by(m.VisitFlowStep.step_order).all()
        ):
            dept = sdp_names.get(step.service_delivery_point_id)
            if getattr(step, "started_at", None):
                add(step.started_at, type_="ROUTED",
                    title=f"Routed to {dept or 'service point'}",
                    department=dept, user_id=getattr(step, "routed_by_id", None))
            if getattr(step, "completed_at", None):
                add(step.completed_at, type_="STEP_CLOSED",
                    title=f"{dept or 'Service point'} {'skipped' if step.is_skipped else 'completed'}",
                    department=dept, notes=getattr(step, "notes", None))

        # ----- Triage + vitals ------------------------------------------------
        for t in self.db.query(m.TriageAssessment).filter(
                m.TriageAssessment.visit_id == visit_id,
                m.TriageAssessment.is_deleted.is_(False)).all():
            add(getattr(t, "assessed_at", None) or getattr(t, "date_created", None),
                type_="TRIAGE", title="Triage assessment recorded", department="Triage",
                notes=getattr(t, "notes", None) or getattr(t, "complaint", None),
                staff_profile_id=getattr(t, "staff_profile_id", None)
                or getattr(t, "assessed_by_staff_id", None))
        for v in self.db.query(m.VitalSign).filter(
                m.VitalSign.visit_id == visit_id,
                m.VitalSign.is_deleted.is_(False)).all():
            bits = []
            for label, attr in (("BP", "blood_pressure"), ("Temp", "temperature"),
                                ("Pulse", "pulse_rate"), ("Resp", "respiratory_rate"),
                                ("SpO2", "oxygen_saturation"), ("Wt", "weight"),
                                ("Ht", "height"), ("BMI", "bmi"),
                                ("Glucose", "blood_sugar")):
                val = getattr(v, attr, None)
                if val not in (None, ""):
                    bits.append(f"{label} {val}")
            add(getattr(v, "recorded_at", None) or getattr(v, "date_created", None),
                type_="VITALS", title="Vital signs recorded", department="Triage",
                notes=" · ".join(bits) or None,
                staff_profile_id=getattr(v, "recorded_by_staff_id", None)
                or getattr(v, "staff_profile_id", None))

        # ----- Consultations --------------------------------------------------
        for c in self.db.query(m.Consultation).filter(
                m.Consultation.visit_id == visit_id,
                m.Consultation.is_deleted.is_(False)).all():
            add(getattr(c, "started_at", None) or getattr(c, "date_created", None),
                type_="CONSULTATION", title="Consultation", department="Consulting room",
                notes=getattr(c, "presenting_complaint", None)
                or getattr(c, "assessment", None) or getattr(c, "notes", None),
                staff_profile_id=getattr(c, "doctor_staff_id", None)
                or getattr(c, "staff_profile_id", None))

        # ----- Laboratory -----------------------------------------------------
        for o in self.db.query(m.LabOrder).filter(
                m.LabOrder.visit_id == visit_id,
                m.LabOrder.is_deleted.is_(False)).all():
            add(getattr(o, "ordered_at", None) or getattr(o, "date_created", None),
                type_="LAB_ORDERED", title="Laboratory investigations requested",
                department="Laboratory", ref=getattr(o, "order_no", None) or getattr(o, "order_number", None),
                staff_profile_id=getattr(o, "ordered_by_staff_id", None))
            for item in getattr(o, "items", []) or []:
                result = getattr(item, "result", None)
                if result is not None and getattr(result, "released_at", None):
                    add(result.released_at, type_="LAB_RESULT",
                        title=f"Result released — {getattr(getattr(item, 'lab_test_catalog', None), 'name', None) or getattr(item, 'test_name', None) or 'test'}",
                        department="Laboratory",
                        notes=(f"{result.result_value or ''} {result.unit_of_measure or ''}".strip()
                               or getattr(result, "result_text", None)),
                        ref=getattr(o, "order_no", None) or getattr(o, "order_number", None),
                        staff_profile_id=getattr(result, "verified_by_staff_id", None)
                        or getattr(result, "entered_by_staff_id", None))

        # ----- Radiology ------------------------------------------------------
        for r in self.db.query(m.RadiologyOrder).filter(
                m.RadiologyOrder.visit_id == visit_id,
                m.RadiologyOrder.is_deleted.is_(False)).all():
            add(getattr(r, "ordered_at", None) or getattr(r, "date_created", None),
                type_="RADIOLOGY_ORDERED", title="Radiology requested",
                department="Radiology", ref=getattr(r, "order_number", None),
                staff_profile_id=getattr(r, "ordered_by_staff_id", None))
            if getattr(r, "reported_at", None):
                add(r.reported_at, type_="RADIOLOGY_REPORT",
                    title="Radiology report available", department="Radiology",
                    notes=getattr(r, "findings", None),
                    staff_profile_id=getattr(r, "reported_by_staff_id", None))

        # ----- Medications ----------------------------------------------------
        for p in self.db.query(m.Prescription).filter(
                m.Prescription.visit_id == visit_id,
                m.Prescription.is_deleted.is_(False)).all():
            add(getattr(p, "prescribed_at", None) or getattr(p, "date_created", None),
                type_="PRESCRIBED", title="Medications prescribed",
                department="Consulting room",
                staff_profile_id=getattr(p, "prescribed_by_staff_id", None)
                or getattr(p, "doctor_staff_id", None))
        for d in self.db.query(m.Dispense).filter(
                m.Dispense.visit_id == visit_id,
                m.Dispense.is_deleted.is_(False)).all():
            add(getattr(d, "dispensed_at", None) or getattr(d, "date_created", None),
                type_="DISPENSED", title="Medications dispensed", department="Pharmacy",
                staff_profile_id=getattr(d, "dispensed_by_staff_id", None))

        # ----- Procedures -----------------------------------------------------
        for pr in self.db.query(m.ProcedureOrder).filter(
                m.ProcedureOrder.visit_id == visit_id,
                m.ProcedureOrder.is_deleted.is_(False)).all():
            add(getattr(pr, "performed_at", None) or getattr(pr, "date_created", None),
                type_="PROCEDURE", title="Procedure", department="Procedure room",
                notes=getattr(pr, "notes", None),
                staff_profile_id=getattr(pr, "performed_by_staff_id", None)
                or getattr(pr, "ordered_by_staff_id", None))

        # ----- Billing --------------------------------------------------------
        for inv in self.db.query(m.Invoice).filter(
                m.Invoice.visit_id == visit_id,
                m.Invoice.is_deleted.is_(False)).all():
            add(getattr(inv, "date_created", None), type_="INVOICE",
                title="Invoice raised", department="Billing",
                ref=getattr(inv, "invoice_number", None),
                notes=(f"Total {getattr(inv, 'total_amount', None)}"
                       if getattr(inv, "total_amount", None) is not None else None))
            for pay in getattr(inv, "payments", []) or []:
                add(getattr(pay, "payment_date", None) or getattr(pay, "date_created", None),
                    type_="PAYMENT", title="Payment received", department="Billing",
                    notes=(f"{getattr(pay, 'amount', '')} via "
                           f"{_val(getattr(pay, 'payment_method', '')) or 'payment'}").strip(),
                    user_id=getattr(pay, "received_by_id", None))

        # ----- Admission / discharge ------------------------------------------
        for adm in self.db.query(m.Admission).filter(
                m.Admission.visit_id == visit_id,
                m.Admission.is_deleted.is_(False)).all():
            add(getattr(adm, "admission_date", None) or getattr(adm, "date_created", None),
                type_="ADMITTED", title="Patient admitted", department="Ward",
                staff_profile_id=getattr(adm, "admitting_staff_id", None))
            dis = getattr(adm, "discharge", None)
            if dis is not None:
                add(getattr(dis, "discharge_date", None) or getattr(dis, "date_created", None),
                    type_="DISCHARGED", title="Patient discharged", department="Ward",
                    notes=getattr(dis, "discharge_summary", None),
                    staff_profile_id=getattr(dis, "discharged_by_staff_id", None))

        # ----- Resolve staff/user display names in bulk -----------------------
        staff_names: dict[int, str] = {}
        if staff_ids:
            rows = (
                self.db.query(m.StaffProfile, m.User)
                .outerjoin(m.User, m.User.id == m.StaffProfile.user_id)
                .filter(m.StaffProfile.id.in_(staff_ids)).all()
            )
            for sp, u in rows:
                name = (f"{getattr(u, 'first_name', '') or ''} "
                        f"{getattr(u, 'last_name', '') or ''}").strip()
                staff_names[sp.id] = name or sp.staff_no
        user_names: dict[int, str] = {}
        if user_ids:
            for u in self.db.query(m.User).filter(m.User.id.in_(user_ids)).all():
                name = f"{u.first_name or ''} {u.last_name or ''}".strip()
                user_names[u.id] = name or u.username

        for e in events:
            e["staff_name"] = (
                staff_names.get(e.pop("staff_profile_id") or 0)
                or user_names.get(e.pop("user_id") or 0)
            )

        events.sort(key=lambda e: e["at"] or "")

        return {
            "visit_id": visit_id,
            "visit_number": getattr(visit, "visit_number", None),
            "status": str(_val(visit.status)) if getattr(visit, "status", None) else None,
            "events": events,
            "count": len(events),
        }
