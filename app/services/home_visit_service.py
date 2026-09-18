# app/services/home_visit_service.py
from __future__ import annotations

"""Home Visit management service (scheduling, lifecycle, documentation)."""

import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    AlertSeverity,
    AlertType,
    HomeVisitStatus,
    MonitoringReadingType,
    MonitoringSource,
)
from app.core.exceptions import BadRequestError
from app.core.logger import get_logger
from app.models.home_health_models import HomeVisit, HomeVisitNote
from app.repositories.home_visit_repository import HomeVisitRepository
from app.repositories.remote_monitoring_repository import RemoteMonitoringRepository
from app.services.clinical_alert_service import ClinicalAlertService

logger = get_logger(__name__)

_TERMINAL = {HomeVisitStatus.COMPLETED, HomeVisitStatus.CANCELLED, HomeVisitStatus.MISSED}

# Allowed forward transitions for the field-visit lifecycle.
_ALLOWED: dict[HomeVisitStatus, set[HomeVisitStatus]] = {
    HomeVisitStatus.REQUESTED: {HomeVisitStatus.APPROVED, HomeVisitStatus.ASSIGNED, HomeVisitStatus.CANCELLED},
    HomeVisitStatus.APPROVED: {HomeVisitStatus.ASSIGNED, HomeVisitStatus.CANCELLED},
    HomeVisitStatus.ASSIGNED: {HomeVisitStatus.EN_ROUTE, HomeVisitStatus.CANCELLED, HomeVisitStatus.MISSED},
    HomeVisitStatus.EN_ROUTE: {HomeVisitStatus.ARRIVED, HomeVisitStatus.CANCELLED, HomeVisitStatus.MISSED},
    HomeVisitStatus.ARRIVED: {HomeVisitStatus.IN_PROGRESS, HomeVisitStatus.CANCELLED},
    HomeVisitStatus.IN_PROGRESS: {HomeVisitStatus.COMPLETED, HomeVisitStatus.CANCELLED},
    HomeVisitStatus.COMPLETED: set(),
    HomeVisitStatus.CANCELLED: set(),
    HomeVisitStatus.MISSED: set(),
}

_TIMESTAMP_FIELD = {
    HomeVisitStatus.EN_ROUTE: "en_route_at",
    HomeVisitStatus.ARRIVED: "arrived_at",
    HomeVisitStatus.IN_PROGRESS: "started_at",
    HomeVisitStatus.COMPLETED: "completed_at",
}

# Documentation vitals -> monitoring reading mapping
_VITAL_READINGS = [
    ("temperature_celsius", MonitoringReadingType.TEMPERATURE, "°C"),
    ("pulse_rate", MonitoringReadingType.PULSE, "bpm"),
    ("respiratory_rate", MonitoringReadingType.RESPIRATORY_RATE, "/min"),
    ("oxygen_saturation", MonitoringReadingType.OXYGEN_SATURATION, "%"),
    ("blood_glucose", MonitoringReadingType.BLOOD_GLUCOSE, "mg/dL"),
    ("weight_kg", MonitoringReadingType.WEIGHT, "kg"),
    ("pain_score", MonitoringReadingType.PAIN_SCORE, "/10"),
]


class HomeVisitService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = HomeVisitRepository(db)
        self.alerts = ClinicalAlertService(db)

    # -- helpers --
    def _generate_code(self) -> str:
        for _ in range(10):
            code = f"HV-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3).upper()}"
            if not self.repository.code_exists(code):
                return code
        return f"HV-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(5).upper()}"

    def _decorate(self, visit: HomeVisit) -> HomeVisit:
        try:
            p = self.repository.get_patient(visit.patient_id)
            visit.patient_name = (
                " ".join(x for x in [getattr(p, "first_name", None), getattr(p, "last_name", None)] if x).strip()
                if p else None
            )
        except Exception:
            visit.patient_name = None
        try:
            visit.assigned_staff_name = self.repository.staff_display_name(visit.assigned_staff_id)
        except Exception:
            visit.assigned_staff_name = None
        return visit

    # -- CRUD / lifecycle --
    def create(self, payload, *, actor_user_id: Optional[int] = None) -> HomeVisit:
        self.repository.get_required_patient(payload.patient_id)
        if payload.assigned_staff_id and not self.repository.get_staff(payload.assigned_staff_id):
            raise BadRequestError(message="Assigned staff not found.", detail={"assigned_staff_id": payload.assigned_staff_id})

        data = payload.model_dump(exclude_unset=True)
        data["visit_code"] = self._generate_code()
        data["requested_by_user_id"] = actor_user_id
        data["created_by_id"] = actor_user_id
        initial = HomeVisitStatus.ASSIGNED if payload.assigned_staff_id else HomeVisitStatus.REQUESTED
        data["status"] = initial

        visit = self.repository.create(**data)
        self.repository.add_status_event(
            home_visit_id=visit.id,
            from_status=None,
            to_status=initial,
            note="Home visit created.",
            changed_by_user_id=actor_user_id,
        )
        self.db.commit()
        self.db.refresh(visit)
        return self._decorate(visit)

    def get(self, visit_id: int) -> HomeVisit:
        return self._decorate(self.repository.get_required_by_id(visit_id))

    def list(self, **kwargs):
        items, total = self.repository.list(**kwargs)
        for v in items:
            self._decorate(v)
        return items, total

    def update(self, visit_id: int, payload) -> HomeVisit:
        visit = self.repository.get_required_by_id(visit_id)
        if visit.status in _TERMINAL:
            raise BadRequestError(message="Cannot edit a closed home visit.")
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(visit, k, v)
        self.db.commit()
        self.db.refresh(visit)
        return self._decorate(visit)

    def assign(self, visit_id: int, payload, *, actor_user_id: Optional[int] = None) -> HomeVisit:
        visit = self.repository.get_required_by_id(visit_id)
        if visit.status in _TERMINAL:
            raise BadRequestError(message="Cannot assign a closed home visit.")
        if not self.repository.get_staff(payload.assigned_staff_id):
            raise BadRequestError(message="Assigned staff not found.", detail={"assigned_staff_id": payload.assigned_staff_id})
        visit.assigned_staff_id = payload.assigned_staff_id
        if payload.eta_minutes is not None:
            visit.eta_minutes = payload.eta_minutes
        if visit.status in (HomeVisitStatus.REQUESTED, HomeVisitStatus.APPROVED):
            prev = visit.status
            visit.status = HomeVisitStatus.ASSIGNED
            self.repository.add_status_event(
                home_visit_id=visit.id, from_status=prev, to_status=HomeVisitStatus.ASSIGNED,
                note=payload.note or "Caregiver assigned.", changed_by_user_id=actor_user_id,
            )
        self.db.commit()
        self.db.refresh(visit)
        self._notify_assignment(visit)
        return self._decorate(visit)

    def change_status(self, visit_id: int, payload, *, actor_user_id: Optional[int] = None) -> HomeVisit:
        visit = self.repository.get_required_by_id(visit_id)
        target = payload.status
        allowed = _ALLOWED.get(visit.status, set())
        if target not in allowed:
            raise BadRequestError(
                message=f"Cannot move a home visit from {visit.status} to {target}.",
                detail={"from": str(visit.status), "to": str(target), "allowed": [str(a) for a in allowed]},
            )
        prev = visit.status
        visit.status = target
        ts_field = _TIMESTAMP_FIELD.get(target)
        if ts_field:
            setattr(visit, ts_field, datetime.now(timezone.utc))
        if payload.eta_minutes is not None:
            visit.eta_minutes = payload.eta_minutes

        self.repository.add_status_event(
            home_visit_id=visit.id,
            from_status=prev,
            to_status=target,
            note=payload.note,
            latitude=payload.latitude,
            longitude=payload.longitude,
            changed_by_user_id=actor_user_id,
        )
        self.db.commit()
        self.db.refresh(visit)

        if target == HomeVisitStatus.MISSED:
            try:
                self.alerts.raise_alert(
                    patient_id=visit.patient_id,
                    alert_type=AlertType.MISSED_VISIT,
                    severity=AlertSeverity.WARNING,
                    title="Home visit missed",
                    message=f"Home visit {visit.visit_code} was marked missed.",
                    home_visit_id=visit.id,
                    care_plan_id=visit.care_plan_id,
                    dedupe_key=f"missed_visit:{visit.id}",
                )
            except Exception as exc:
                logger.warning("Missed-visit alert failed for %s: %s", visit.id, exc)

        return self._decorate(visit)

    def cancel(self, visit_id: int, payload, *, actor_user_id: Optional[int] = None) -> HomeVisit:
        visit = self.repository.get_required_by_id(visit_id)
        if visit.status in _TERMINAL:
            raise BadRequestError(message="Home visit is already closed.")
        prev = visit.status
        visit.status = HomeVisitStatus.CANCELLED
        visit.cancellation_reason = payload.reason
        self.repository.add_status_event(
            home_visit_id=visit.id, from_status=prev, to_status=HomeVisitStatus.CANCELLED,
            note=payload.reason, changed_by_user_id=actor_user_id,
        )
        self.db.commit()
        self.db.refresh(visit)
        return self._decorate(visit)

    def list_events(self, visit_id: int):
        self.repository.get_required_by_id(visit_id)
        return self.repository.list_events(visit_id)

    # -- documentation --
    def get_note(self, visit_id: int) -> Optional[HomeVisitNote]:
        self.repository.get_required_by_id(visit_id)
        return self.repository.get_note(visit_id)

    def upsert_note(self, visit_id: int, payload, *, actor_user_id: Optional[int] = None) -> HomeVisitNote:
        visit = self.repository.get_required_by_id(visit_id)
        data = payload.model_dump(exclude_unset=True)
        record_vitals = data.pop("record_vitals_as_readings", True)

        note = self.repository.get_note(visit_id)
        if note is None:
            note = self.repository.create_note(
                home_visit_id=visit_id, patient_id=visit.patient_id, created_by_id=actor_user_id, **data
            )
        else:
            for k, v in data.items():
                setattr(note, k, v)
        if data.get("signed_by_staff_id") and note.signed_at is None:
            note.signed_at = datetime.now(timezone.utc)

        # Auto-advance an in-progress visit to completed when documented + signed.
        if note.signed_at and visit.status == HomeVisitStatus.IN_PROGRESS:
            visit.status = HomeVisitStatus.COMPLETED
            visit.completed_at = datetime.now(timezone.utc)
            self.repository.add_status_event(
                home_visit_id=visit.id, from_status=HomeVisitStatus.IN_PROGRESS,
                to_status=HomeVisitStatus.COMPLETED, note="Auto-completed on signed documentation.",
                changed_by_user_id=actor_user_id,
            )

        alerts = []
        if record_vitals:
            alerts = self._persist_vitals_as_readings(visit, note, actor_user_id)

        self.db.commit()
        self.db.refresh(note)

        for a in alerts:
            if a is not None:
                self.alerts.dispatch_alert(a)
        return note

    def _persist_vitals_as_readings(self, visit: HomeVisit, note: HomeVisitNote, actor_user_id: Optional[int]):
        mon_repo = RemoteMonitoringRepository(self.db)
        alerts = []
        now = datetime.now(timezone.utc)

        # Blood pressure (paired)
        if note.systolic_bp is not None and note.diastolic_bp is not None:
            r = mon_repo.create_reading(
                patient_id=visit.patient_id, care_plan_id=visit.care_plan_id, home_visit_id=visit.id,
                reading_type=MonitoringReadingType.BLOOD_PRESSURE, source=MonitoringSource.CAREGIVER,
                systolic=note.systolic_bp, diastolic=note.diastolic_bp, unit="mmHg",
                recorded_at=now, received_at=now, recorded_by_user_id=actor_user_id,
            )
            alerts.append(self._safe_eval(r))

        for field, rtype, unit in _VITAL_READINGS:
            val = getattr(note, field, None)
            if val is None:
                continue
            r = mon_repo.create_reading(
                patient_id=visit.patient_id, care_plan_id=visit.care_plan_id, home_visit_id=visit.id,
                reading_type=rtype, source=MonitoringSource.CAREGIVER,
                primary_value=val, unit=unit,
                recorded_at=now, received_at=now, recorded_by_user_id=actor_user_id,
            )
            alerts.append(self._safe_eval(r))
        return alerts

    def _safe_eval(self, reading):
        try:
            return self.alerts.evaluate_reading(reading)
        except Exception as exc:
            logger.warning("Alert eval failed for reading %s: %s", getattr(reading, "id", "?"), exc)
            return None

    def _notify_assignment(self, visit: HomeVisit) -> None:
        try:
            from app.core.enums import NotificationEvent
            from app.models.all_models import StaffProfile, User
            from app.services.notification_dispatcher import NotificationDispatcher

            if not visit.assigned_staff_id:
                return
            user = (
                self.db.query(User)
                .join(StaffProfile, StaffProfile.user_id == User.id)
                .filter(StaffProfile.id == visit.assigned_staff_id, User.is_deleted.is_(False))
                .first()
            )
            if not user:
                return
            NotificationDispatcher(self.db).dispatch(
                event=NotificationEvent.SYSTEM_ALERT,
                recipients=[user],
                subject="New home visit assigned",
                body=f"You have been assigned home visit {visit.visit_code}.",
                context={"home_visit_id": visit.id, "patient_id": visit.patient_id},
            )
        except Exception as exc:
            logger.warning("Assignment notification failed for visit %s: %s", visit.id, exc)
