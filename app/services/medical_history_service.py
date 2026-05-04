# app/services/medical_history_service.py
from __future__ import annotations

"""
Patient medical-history aggregation service.

This service exists so a clinician landing on a patient (or on a fresh
visit for a patient) can see the full clinical context in one call:

- demographic header + chronic-condition / allergy summary
- prior visits and their priority / status
- consultations (subjective / objective / assessment / plan)
- diagnoses (across all visits)
- triage assessments + vital-sign trend
- lab orders + results (with the four-eyes verified release values)
- radiology orders + finalised reports
- prescriptions + dispense status
- procedure orders (clinic-room)
- surgical cases (theatre)
- inpatient admissions

It is intentionally read-only and pure SQLAlchemy. No state changes, no
audit events — just an information dump that any front-end or worklist
can render without doing 12 round-trips to other endpoints.
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import NotFoundError
from app.models.all_models import (
    Admission,
    Consultation,
    Diagnosis,
    Drug,
    LabOrder,
    LabOrderItem,
    LabResult,
    LabTestCatalog,
    Patient,
    Prescription,
    PrescriptionItem,
    ProcedureCatalog,
    ProcedureOrder,
    RadiologyOrder,
    RadiologyReport,
    SurgicalCase,
    SurgicalProcedureCatalog,
    TriageAssessment,
    Visit,
    VitalSign,
)


def _years_between(d1: date, d2: date) -> int:
    """Whole-year difference, accounting for partial years."""
    years = d2.year - d1.year
    if (d2.month, d2.day) < (d1.month, d1.day):
        years -= 1
    return max(years, 0)


class PatientMedicalHistoryService:
    """Aggregator for a patient's full medical history."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ----- demographic header ----------------------------------------------

    def _demographic_dict(self, patient: Patient) -> dict:
        age_years: Optional[int] = None
        if patient.date_of_birth is not None:
            age_years = _years_between(patient.date_of_birth, date.today())
        return {
            "id": patient.id,
            "hospital_number": patient.hospital_number,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "middle_name": patient.middle_name,
            "date_of_birth": patient.date_of_birth,
            "age_years": age_years,
            "gender": str(patient.gender) if patient.gender else None,
            "blood_group": str(patient.blood_group) if patient.blood_group else None,
            "genotype": str(patient.genotype) if patient.genotype else None,
            "allergies": patient.allergies,
            "patient_type": str(patient.patient_type) if patient.patient_type else None,
            "phone_number": patient.phone_number,
            "email": patient.email,
            # ``chronic_conditions`` is reserved for future extension.
            "chronic_conditions": None,
        }

    # ----- per-relationship loaders ----------------------------------------

    def _visits_for_patient(self, patient_id: int) -> list[Visit]:
        return list(
            self.db.query(Visit)
            .filter(Visit.patient_id == patient_id, Visit.is_deleted.is_(False))
            .order_by(Visit.visit_date.desc())
            .all()
        )

    def _consultations(self, visit_ids: list[int]) -> list[Consultation]:
        if not visit_ids:
            return []
        return list(
            self.db.query(Consultation)
            .filter(
                Consultation.visit_id.in_(visit_ids),
                Consultation.is_deleted.is_(False),
            )
            .order_by(Consultation.consultation_started_at.desc().nullslast())
            .all()
        )

    def _diagnoses(self, visit_ids: list[int]) -> list[Diagnosis]:
        if not visit_ids:
            return []
        return list(
            self.db.query(Diagnosis)
            .filter(
                Diagnosis.visit_id.in_(visit_ids),
                Diagnosis.is_deleted.is_(False),
            )
            .order_by(Diagnosis.id.desc())
            .all()
        )

    def _triage_assessments(self, visit_ids: list[int]) -> list[TriageAssessment]:
        if not visit_ids:
            return []
        return list(
            self.db.query(TriageAssessment)
            .filter(
                TriageAssessment.visit_id.in_(visit_ids),
                TriageAssessment.is_deleted.is_(False),
            )
            .order_by(TriageAssessment.id.desc())
            .all()
        )

    def _vital_signs(self, visit_ids: list[int]) -> list[VitalSign]:
        if not visit_ids:
            return []
        return list(
            self.db.query(VitalSign)
            .filter(
                VitalSign.visit_id.in_(visit_ids),
                VitalSign.is_deleted.is_(False),
            )
            .order_by(VitalSign.recorded_at.desc())
            .all()
        )

    def _lab_orders(self, visit_ids: list[int]) -> list[LabOrder]:
        if not visit_ids:
            return []
        return list(
            self.db.query(LabOrder)
            .options(
                selectinload(LabOrder.items)
                .selectinload(LabOrderItem.lab_test_catalog),
                selectinload(LabOrder.items).selectinload(LabOrderItem.result),
            )
            .filter(
                LabOrder.visit_id.in_(visit_ids),
                LabOrder.is_deleted.is_(False),
            )
            .order_by(LabOrder.ordered_at.desc())
            .all()
        )

    def _radiology_orders(self, visit_ids: list[int]) -> list[RadiologyOrder]:
        if not visit_ids:
            return []
        return list(
            self.db.query(RadiologyOrder)
            .options(selectinload(RadiologyOrder.items))
            .filter(
                RadiologyOrder.visit_id.in_(visit_ids),
                RadiologyOrder.is_deleted.is_(False),
            )
            .order_by(RadiologyOrder.ordered_at.desc())
            .all()
        )

    def _radiology_reports_for_orders(
        self, radiology_orders: list[RadiologyOrder]
    ) -> dict[int, list[RadiologyReport]]:
        """Map each order id → list of finalised / released reports."""
        if not radiology_orders:
            return {}
        order_item_ids: list[int] = []
        order_id_by_item_id: dict[int, int] = {}
        for order in radiology_orders:
            for item in order.items or []:
                order_item_ids.append(item.id)
                order_id_by_item_id[item.id] = order.id
        if not order_item_ids:
            return {}
        # RadiologyReport sits on the exam, which sits on the order item.
        from app.models.all_models import RadiologyExam

        rows = (
            self.db.query(RadiologyReport, RadiologyExam.order_item_id)
            .join(RadiologyExam, RadiologyExam.id == RadiologyReport.exam_id)
            .filter(
                RadiologyExam.order_item_id.in_(order_item_ids),
                RadiologyReport.is_deleted.is_(False),
            )
            .order_by(RadiologyReport.id.desc())
            .all()
        )
        result: dict[int, list[RadiologyReport]] = {}
        for report, order_item_id in rows:
            order_id = order_id_by_item_id.get(order_item_id)
            if order_id is None:
                continue
            result.setdefault(order_id, []).append(report)
        return result

    def _prescriptions(self, visit_ids: list[int]) -> list[Prescription]:
        if not visit_ids:
            return []
        return list(
            self.db.query(Prescription)
            .options(
                selectinload(Prescription.items).selectinload(PrescriptionItem.drug)
            )
            .filter(
                Prescription.visit_id.in_(visit_ids),
                Prescription.is_deleted.is_(False),
            )
            .order_by(Prescription.prescribed_at.desc())
            .all()
        )

    def _procedure_orders(self, visit_ids: list[int]) -> list[ProcedureOrder]:
        if not visit_ids:
            return []
        return list(
            self.db.query(ProcedureOrder)
            .options(selectinload(ProcedureOrder.procedure_catalog))
            .filter(
                ProcedureOrder.visit_id.in_(visit_ids),
                ProcedureOrder.is_deleted.is_(False),
            )
            .order_by(ProcedureOrder.ordered_at.desc())
            .all()
        )

    def _surgical_cases(self, patient_id: int) -> list[SurgicalCase]:
        # Surgical cases are tied to the patient directly, not just the visit.
        rows = (
            self.db.query(SurgicalCase, SurgicalProcedureCatalog.name)
            .join(
                SurgicalProcedureCatalog,
                SurgicalProcedureCatalog.id == SurgicalCase.procedure_catalog_id,
            )
            .filter(
                SurgicalCase.patient_id == patient_id,
                SurgicalCase.is_deleted.is_(False),
            )
            .order_by(SurgicalCase.id.desc())
            .all()
        )
        # Stash procedure name as a transient attribute the dict-builder can
        # read without a second query per row.
        out: list[SurgicalCase] = []
        for case, proc_name in rows:
            setattr(case, "_procedure_name", proc_name)
            out.append(case)
        return out

    def _admissions(self, patient_id: int) -> list[Admission]:
        return list(
            self.db.query(Admission)
            .filter(
                Admission.patient_id == patient_id,
                Admission.is_deleted.is_(False),
            )
            .order_by(Admission.admitted_at.desc())
            .all()
        )

    # ----- entry-shape converters -----------------------------------------

    def _visit_dict(self, v: Visit) -> dict:
        return {
            "id": v.id,
            "visit_code": v.visit_code,
            "visit_date": v.visit_date,
            "status": str(v.status),
            "priority": str(v.priority) if v.priority else None,
            "visit_reason": v.visit_reason,
            "first_service_delivery_point_id": v.first_service_delivery_point_id,
            "current_service_delivery_point_id": v.current_service_delivery_point_id,
        }

    def _consultation_dict(self, c: Consultation) -> dict:
        return {
            "id": c.id,
            "visit_id": c.visit_id,
            "clinician_staff_id": c.clinician_staff_id,
            "status": str(c.status),
            "subjective_note": c.subjective_note,
            "objective_note": c.objective_note,
            "assessment_note": c.assessment_note,
            "plan_note": c.plan_note,
            "consultation_started_at": c.consultation_started_at,
            "consultation_ended_at": c.consultation_ended_at,
        }

    def _diagnosis_dict(self, d: Diagnosis) -> dict:
        return {
            "id": d.id,
            "visit_id": d.visit_id,
            "consultation_id": d.consultation_id,
            "diagnosis_code": d.diagnosis_code,
            "diagnosis_text": d.diagnosis_name,
            "diagnosis_type": d.diagnosis_type,
            "is_primary": None,
            "diagnosed_at": getattr(d, "created_at", None),
        }

    def _lab_result_dict(self, r: LabResult) -> dict:
        return {
            "id": r.id,
            "result_status": str(r.result_status),
            "result_value": r.result_value,
            "result_text": r.result_text,
            "unit_of_measure": r.unit_of_measure,
            "reference_range": r.reference_range,
            "interpretation": r.interpretation,
            "released_at": r.released_at,
        }

    def _lab_order_item_dict(self, item: LabOrderItem) -> dict:
        test = item.lab_test_catalog
        return {
            "id": item.id,
            "lab_test_catalog_id": item.lab_test_catalog_id,
            "lab_test_name": test.name if test else None,
            "status": str(item.status),
            "specimen_id": item.specimen_id,
            "sample_collected_at": item.sample_collected_at,
            "result": (
                self._lab_result_dict(item.result) if item.result is not None else None
            ),
        }

    def _lab_order_dict(self, o: LabOrder) -> dict:
        return {
            "id": o.id,
            "visit_id": o.visit_id,
            "order_no": o.order_no,
            "status": str(o.status),
            "clinical_note": o.clinical_note,
            "ordered_at": o.ordered_at,
            "items": [
                self._lab_order_item_dict(i)
                for i in (o.items or [])
                if not getattr(i, "is_deleted", False)
            ],
        }

    def _radiology_order_dict(
        self,
        o: RadiologyOrder,
        reports_by_order_id: dict[int, list[RadiologyReport]],
    ) -> dict:
        return {
            "id": o.id,
            "visit_id": o.visit_id,
            "order_no": o.order_no,
            "status": str(o.status),
            "priority": str(o.priority) if o.priority else None,
            "clinical_indication": getattr(o, "clinical_indication", None),
            "ordered_at": o.ordered_at,
            "items": [
                {
                    "id": i.id,
                    "procedure_catalog_id": i.procedure_catalog_id,
                    "status": str(i.status),
                    "laterality": i.laterality,
                    "notes": i.notes,
                }
                for i in (o.items or [])
                if not getattr(i, "is_deleted", False)
            ],
            "reports": [
                {
                    "id": r.id,
                    "status": str(r.status),
                    "findings": r.findings,
                    "impression": r.impression,
                    "recommendations": r.recommendations,
                    "finalized_at": r.finalized_at,
                    "released_at": r.released_at,
                }
                for r in reports_by_order_id.get(o.id, [])
            ],
        }

    def _prescription_item_dict(self, pi: PrescriptionItem) -> dict:
        drug = pi.drug
        # Build a free-form dosage instruction summary so the clinician
        # doesn't have to glue four fields together by eye.
        dosage_bits = [pi.dosage, pi.frequency, pi.duration]
        if pi.route:
            dosage_bits.append(f"({pi.route})")
        dosage_instruction = " ".join(b for b in dosage_bits if b) or None
        return {
            "id": pi.id,
            "drug_id": pi.drug_id,
            "drug_name": drug.name if drug else None,
            "strength": drug.strength if drug else None,
            "dosage_form": drug.dosage_form if drug else None,
            "dosage_instruction": dosage_instruction,
            "quantity_prescribed": pi.quantity_prescribed,
            "quantity_dispensed": pi.quantity_dispensed,
            "status": (
                "DISPENSED" if (pi.quantity_dispensed or 0) >= (pi.quantity_prescribed or 0)
                else "PARTIAL" if (pi.quantity_dispensed or 0) > 0
                else "PENDING"
            ),
        }

    def _prescription_dict(self, p: Prescription) -> dict:
        return {
            "id": p.id,
            "visit_id": p.visit_id,
            "prescription_no": p.prescription_no,
            "status": str(p.status),
            "note": p.note,
            "prescribed_at": p.prescribed_at,
            "items": [
                self._prescription_item_dict(i)
                for i in (p.items or [])
                if not getattr(i, "is_deleted", False)
            ],
        }

    def _procedure_order_dict(self, po: ProcedureOrder) -> dict:
        catalog = po.procedure_catalog
        return {
            "id": po.id,
            "visit_id": po.visit_id,
            "status": str(po.status),
            "procedure_catalog_id": po.procedure_catalog_id,
            "procedure_name": catalog.name if catalog else None,
            "notes": po.notes,
            "ordered_at": po.ordered_at,
            "started_at": None,
            "completed_at": po.performed_at,
        }

    def _surgical_case_dict(self, sc: SurgicalCase) -> dict:
        return {
            "id": sc.id,
            "case_no": sc.case_no,
            "visit_id": sc.visit_id,
            "status": str(sc.status),
            "procedure_catalog_id": sc.procedure_catalog_id,
            "procedure_name": getattr(sc, "_procedure_name", None),
            "is_emergency": bool(sc.is_emergency),
            "asa_class": str(sc.asa_class) if sc.asa_class else None,
            "anaesthesia_type": (
                str(sc.anaesthesia_type) if sc.anaesthesia_type else None
            ),
            "scheduled_start_at": sc.scheduled_start_at,
            "incision_at": sc.incision_at,
            "closure_at": sc.closure_at,
            "diagnosis_text": sc.diagnosis_text,
            "findings_text": sc.findings_text,
        }

    def _admission_dict(self, a: Admission) -> dict:
        return {
            "id": a.id,
            "admission_no": a.admission_no,
            "visit_id": a.visit_id,
            "ward_id": a.ward_id,
            "bed_id": a.bed_id,
            "admission_status": str(a.admission_status),
            "admission_reason": a.admission_reason,
            "admitted_at": a.admitted_at,
            "expected_discharge_at": a.expected_discharge_at,
            "actual_discharge_at": a.actual_discharge_at,
        }

    def _triage_dict(self, t: TriageAssessment) -> dict:
        return {
            "id": t.id,
            "visit_id": t.visit_id,
            "triage_priority": str(t.priority) if t.priority else None,
            "chief_complaint": t.chief_complaint,
            "history_of_present_illness": None,
            "triage_notes": t.triage_note,
            "assessed_at": getattr(t, "created_at", None),
        }

    def _vital_dict(self, v: VitalSign) -> dict:
        return {
            "id": v.id,
            "visit_id": v.visit_id,
            "recorded_at": v.recorded_at,
            "temperature_c": v.temperature_celsius,
            "pulse_bpm": v.pulse_rate,
            "respiratory_rate": v.respiratory_rate,
            "systolic_bp": v.systolic_bp,
            "diastolic_bp": v.diastolic_bp,
            "spo2_percent": int(v.oxygen_saturation) if v.oxygen_saturation is not None else None,
            "weight_kg": v.weight_kg,
            "height_cm": v.height_cm,
            "bmi": v.bmi,
            "pain_score": v.pain_score,
            "notes": None,
        }

    # ----- public entrypoint ----------------------------------------------

    def get_patient_history(
        self,
        patient_id: int,
        *,
        include_vital_signs: bool = True,
        max_visits: Optional[int] = None,
    ) -> dict:
        """
        Return the complete medical history for one patient.

        Args:
            patient_id: Patient master row id.
            include_vital_signs: When False, drops the (potentially long)
                vital-sign timeline. Useful for compact views.
            max_visits: When set, restrict the lookup to the most-recent
                ``max_visits`` visits (everything else is filtered against
                that visit-id set).
        """
        patient = (
            self.db.query(Patient)
            .filter(Patient.id == patient_id, Patient.is_deleted.is_(False))
            .first()
        )
        if patient is None:
            raise NotFoundError(
                message="Patient not found.",
                detail={"patient_id": patient_id},
            )

        visits = self._visits_for_patient(patient.id)
        if max_visits is not None and max_visits > 0:
            visits = visits[:max_visits]
        visit_ids = [v.id for v in visits]

        consultations = self._consultations(visit_ids)
        diagnoses = self._diagnoses(visit_ids)
        triage = self._triage_assessments(visit_ids)
        vitals = self._vital_signs(visit_ids) if include_vital_signs else []
        lab_orders = self._lab_orders(visit_ids)
        radiology_orders = self._radiology_orders(visit_ids)
        reports_by_order = self._radiology_reports_for_orders(radiology_orders)
        prescriptions = self._prescriptions(visit_ids)
        procedure_orders = self._procedure_orders(visit_ids)
        surgical_cases = self._surgical_cases(patient.id)
        admissions = self._admissions(patient.id)

        history = {
            "patient": self._demographic_dict(patient),
            "summary": {
                "visits": len(visits),
                "consultations": len(consultations),
                "diagnoses": len(diagnoses),
                "lab_orders": len(lab_orders),
                "radiology_orders": len(radiology_orders),
                "prescriptions": len(prescriptions),
                "procedure_orders": len(procedure_orders),
                "surgical_cases": len(surgical_cases),
                "admissions": len(admissions),
                "triage_assessments": len(triage),
                "vital_signs": len(vitals),
            },
            "allergies": patient.allergies,
            "visits": [self._visit_dict(v) for v in visits],
            "consultations": [self._consultation_dict(c) for c in consultations],
            "diagnoses": [self._diagnosis_dict(d) for d in diagnoses],
            "lab_orders": [self._lab_order_dict(o) for o in lab_orders],
            "radiology_orders": [
                self._radiology_order_dict(o, reports_by_order)
                for o in radiology_orders
            ],
            "prescriptions": [self._prescription_dict(p) for p in prescriptions],
            "procedure_orders": [self._procedure_order_dict(po) for po in procedure_orders],
            "surgical_cases": [self._surgical_case_dict(sc) for sc in surgical_cases],
            "admissions": [self._admission_dict(a) for a in admissions],
            "triage_assessments": [self._triage_dict(t) for t in triage],
            "vital_signs": [self._vital_dict(v) for v in vitals],
        }
        return history

    def get_history_by_visit(
        self,
        visit_id: int,
        **kwargs,
    ) -> dict:
        """Convenience: resolve the patient through a visit, then aggregate."""
        visit = (
            self.db.query(Visit)
            .filter(Visit.id == visit_id, Visit.is_deleted.is_(False))
            .first()
        )
        if visit is None:
            raise NotFoundError(
                message="Visit not found.",
                detail={"visit_id": visit_id},
            )
        return self.get_patient_history(visit.patient_id, **kwargs)
