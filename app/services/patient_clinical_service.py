# app/services/patient_clinical_service.py
from __future__ import annotations

"""
Chronic-care support for clinicians: the patient problem list and a
vitals-trend analytics layer that indicates whether a patient is improving,
stable, or worsening across their visits.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.all_models import Patient, PatientProblem, Visit, VitalSign
from app.schemas.patient_problem_schemas import (
    PatientProblemCreateSchema,
    PatientProblemUpdateSchema,
)


# ---------------------------------------------------------------------------
# Vitals-trend configuration
# ---------------------------------------------------------------------------
# For each metric we declare a clinically-sensible target. "improving" means
# the latest reading is meaningfully CLOSER to target than the earliest;
# "worsening" means it moved away. ``target=None`` marks a metric with no
# universal good direction (e.g. weight) — we report the raw trend only.

_METRICS: list[dict] = [
    {"key": "systolic_bp", "label": "Systolic BP", "unit": "mmHg", "target": 120.0, "eps": 4.0},
    {"key": "diastolic_bp", "label": "Diastolic BP", "unit": "mmHg", "target": 80.0, "eps": 3.0},
    {"key": "pulse_rate", "label": "Pulse", "unit": "bpm", "target": 75.0, "eps": 4.0},
    {"key": "respiratory_rate", "label": "Respiratory rate", "unit": "/min", "target": 16.0, "eps": 2.0},
    {"key": "temperature_celsius", "label": "Temperature", "unit": "°C", "target": 37.0, "eps": 0.3},
    {"key": "oxygen_saturation", "label": "SpO₂", "unit": "%", "target": 99.0, "eps": 1.0},
    {"key": "bmi", "label": "BMI", "unit": "kg/m²", "target": 22.0, "eps": 0.5},
    {"key": "pain_score", "label": "Pain score", "unit": "/10", "target": 0.0, "eps": 0.5},
    {"key": "mews_score", "label": "MEWS", "unit": "", "target": 0.0, "eps": 0.5},
    {"key": "weight_kg", "label": "Weight", "unit": "kg", "target": None, "eps": 0.5},
]


class PatientClinicalService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Problem list
    # ------------------------------------------------------------------
    def _get_patient(self, patient_id: int) -> Patient:
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if patient is None:
            raise NotFoundError(message="Patient not found.", detail={"patient_id": patient_id})
        return patient

    def list_problems(self, patient_id: int, *, active_only: bool = False) -> list[PatientProblem]:
        self._get_patient(patient_id)
        q = self.db.query(PatientProblem).filter(
            PatientProblem.patient_id == patient_id,
            PatientProblem.is_deleted.is_(False),
        )
        if active_only:
            from app.core.enums import ProblemStatus

            q = q.filter(PatientProblem.status != ProblemStatus.RESOLVED)
        return q.order_by(PatientProblem.id.desc()).all()

    def get_problem(self, patient_id: int, problem_id: int) -> PatientProblem:
        problem = (
            self.db.query(PatientProblem)
            .filter(
                PatientProblem.id == problem_id,
                PatientProblem.patient_id == patient_id,
                PatientProblem.is_deleted.is_(False),
            )
            .first()
        )
        if problem is None:
            raise NotFoundError(message="Problem not found.", detail={"problem_id": problem_id})
        return problem

    def create_problem(
        self,
        patient_id: int,
        payload: PatientProblemCreateSchema,
        *,
        diagnosed_by_user_id: Optional[int] = None,
    ) -> PatientProblem:
        self._get_patient(patient_id)
        problem = PatientProblem(
            patient_id=patient_id,
            condition_name=payload.condition_name.strip(),
            condition_code=(payload.condition_code or None),
            category=(payload.category or None),
            status=payload.status,
            is_chronic=payload.is_chronic,
            onset_date=payload.onset_date,
            resolved_date=payload.resolved_date,
            severity=(payload.severity or None),
            notes=(payload.notes or None),
            diagnosed_by_user_id=diagnosed_by_user_id,
            last_reviewed_at=datetime.now(timezone.utc),
        )
        self.db.add(problem)
        self.db.commit()
        self.db.refresh(problem)
        return problem

    def update_problem(
        self, patient_id: int, problem_id: int, payload: PatientProblemUpdateSchema
    ) -> PatientProblem:
        problem = self.get_problem(patient_id, problem_id)
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(problem, field, value)
        problem.last_reviewed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(problem)
        return problem

    def delete_problem(self, patient_id: int, problem_id: int) -> None:
        problem = self.get_problem(patient_id, problem_id)
        problem.is_deleted = True
        self.db.commit()

    # ------------------------------------------------------------------
    # Vitals trends
    # ------------------------------------------------------------------
    def _assess(self, metric: dict, first: float, latest: float) -> tuple[str, str]:
        """Return (assessment, direction) for a metric's first vs latest reading."""
        direction = "flat"
        if latest > first:
            direction = "up"
        elif latest < first:
            direction = "down"

        target = metric.get("target")
        if target is None:
            # No universal good direction (e.g. weight) — report trend only.
            return ("trend_only", direction)

        eps = float(metric.get("eps") or 0.0)
        d_first = abs(first - target)
        d_latest = abs(latest - target)
        if d_latest < d_first - eps:
            return ("improving", direction)
        if d_latest > d_first + eps:
            return ("worsening", direction)
        return ("stable", direction)

    def clinical_trends(self, patient_id: int) -> dict:
        self._get_patient(patient_id)

        rows = (
            self.db.query(VitalSign)
            .join(Visit, Visit.id == VitalSign.visit_id)
            .filter(
                Visit.patient_id == patient_id,
                VitalSign.is_deleted.is_(False),
            )
            .order_by(VitalSign.recorded_at.asc())
            .all()
        )

        metrics: list[dict] = []
        improving = worsening = stable = 0

        for metric in _METRICS:
            key = metric["key"]
            points = []
            for r in rows:
                raw = getattr(r, key, None)
                if raw is None or r.recorded_at is None:
                    continue
                try:
                    points.append({"date": r.recorded_at, "value": float(raw)})
                except (TypeError, ValueError):
                    continue

            entry = {
                "key": key,
                "label": metric["label"],
                "unit": metric["unit"] or None,
                "points": points,
                "first_value": None,
                "latest_value": None,
                "delta": None,
                "assessment": "insufficient_data",
                "direction": None,
            }

            if len(points) >= 2:
                first = points[0]["value"]
                latest = points[-1]["value"]
                entry["first_value"] = round(first, 2)
                entry["latest_value"] = round(latest, 2)
                entry["delta"] = round(latest - first, 2)
                assessment, direction = self._assess(metric, first, latest)
                entry["assessment"] = assessment
                entry["direction"] = direction
                if assessment == "improving":
                    improving += 1
                elif assessment == "worsening":
                    worsening += 1
                elif assessment == "stable":
                    stable += 1
            elif len(points) == 1:
                entry["latest_value"] = round(points[0]["value"], 2)

            metrics.append(entry)

        return {
            "patient_id": patient_id,
            "metrics": metrics,
            "improving": improving,
            "worsening": worsening,
            "stable": stable,
        }
