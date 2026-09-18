# app/services/clinical_alert_service.py
from __future__ import annotations

"""
Clinical Alerts / Early-Warning engine.

Responsibilities
----------------
* Evaluate remote-monitoring readings against per-patient / tenant thresholds
  and configurable early-warning rules, producing an escalating severity
  (Information -> Warning -> Urgent -> Emergency).
* Raise de-duplicated ``ClinicalAlert`` records and dispatch multi-channel
  notifications to the clinical care team (reusing ``NotificationDispatcher``).
* Drive the acknowledge -> review -> resolve / escalate workflow.
* Provide a generic ``raise_alert`` used by other home-health services
  (e.g. missed visit / missed task).
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    AlertComparator,
    AlertSeverity,
    AlertStatus,
    AlertType,
    MonitoringReadingType,
)
from app.core.exceptions import BadRequestError
from app.core.logger import get_logger
from app.models.home_health_models import ClinicalAlert, MonitoringReading
from app.repositories.clinical_alert_repository import ClinicalAlertRepository

logger = get_logger(__name__)

_SEVERITY_ORDER = {
    AlertSeverity.INFORMATION: 0,
    AlertSeverity.WARNING: 1,
    AlertSeverity.URGENT: 2,
    AlertSeverity.EMERGENCY: 3,
}

# Sensible built-in fallback bounds used when no DB threshold is configured.
# (normal_low, normal_high, critical_low, critical_high) — for BP these apply
# to the systolic component; diastolic uses DEFAULT_BP_DIASTOLIC.
_DEFAULT_BOUNDS: dict[MonitoringReadingType, tuple] = {
    MonitoringReadingType.BLOOD_PRESSURE: (90, 140, 80, 180),
    MonitoringReadingType.PULSE: (50, 100, 40, 130),
    MonitoringReadingType.TEMPERATURE: (36.1, 37.8, 35.0, 39.5),
    MonitoringReadingType.BLOOD_GLUCOSE: (70, 180, 54, 300),
    MonitoringReadingType.OXYGEN_SATURATION: (94, 100, 90, 101),
    MonitoringReadingType.RESPIRATORY_RATE: (12, 20, 8, 30),
    MonitoringReadingType.PAIN_SCORE: (0, 4, -1, 8),
}
_DEFAULT_BP_DIASTOLIC = (60, 90)


def _sev_max(a: AlertSeverity, b: AlertSeverity) -> AlertSeverity:
    return a if _SEVERITY_ORDER[a] >= _SEVERITY_ORDER[b] else b


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class ClinicalAlertService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ClinicalAlertRepository(db)

    # =====================================================================
    # Evaluation (early-warning engine)
    # =====================================================================
    def evaluate_reading(self, reading: MonitoringReading) -> Optional[ClinicalAlert]:
        """
        Evaluate a persisted reading. When it breaches a threshold or rule,
        flag the reading and create (flush) a de-duplicated alert. Does NOT
        commit or dispatch — the caller commits then calls ``dispatch_alert``.
        """
        severity, alert_type, detail = self._score(reading)

        if severity is None or severity == AlertSeverity.INFORMATION:
            return None

        # Flag the reading itself
        reading.is_abnormal = True
        reading.severity = severity

        dedupe_key = f"reading:{reading.patient_id}:{reading.reading_type}:{severity}"
        existing = self.repository.find_recent_by_dedupe(dedupe_key, window_minutes=60)
        if existing:
            logger.info(
                "Suppressing duplicate alert for patient %s (%s) within window.",
                reading.patient_id, reading.reading_type,
            )
            return None

        title = f"{self._reading_label(reading.reading_type)} — {severity.value.title()}"
        alert = self.repository.create(
            patient_id=reading.patient_id,
            care_plan_id=reading.care_plan_id,
            home_visit_id=reading.home_visit_id,
            reading_id=reading.id,
            alert_type=alert_type,
            severity=severity,
            status=AlertStatus.OPEN,
            title=title,
            message=detail,
            context={
                "reading_type": str(reading.reading_type),
                "primary_value": _to_float(reading.primary_value),
                "systolic": reading.systolic,
                "diastolic": reading.diastolic,
                "unit": reading.unit,
            },
            dedupe_key=dedupe_key,
            triggered_at=datetime.now(timezone.utc),
        )
        return alert

    def _score(self, reading: MonitoringReading):
        """Return (severity, alert_type, detail) for a reading. severity may be None."""
        rt = reading.reading_type

        # 1) Threshold-based (patient override -> tenant default -> built-in)
        severity, alert_type, detail = self._score_by_threshold(reading)

        # 2) Configured early-warning rules can raise the severity
        rule_sev, rule_type, rule_detail = self._score_by_rules(reading)
        if rule_sev is not None:
            if severity is None:
                severity, alert_type, detail = rule_sev, rule_type, rule_detail
            else:
                if _SEVERITY_ORDER[rule_sev] > _SEVERITY_ORDER[severity]:
                    severity, alert_type, detail = rule_sev, rule_type, rule_detail

        return severity, (alert_type or AlertType.ABNORMAL_VITALS), detail

    def _score_by_threshold(self, reading: MonitoringReading):
        from app.repositories.remote_monitoring_repository import RemoteMonitoringRepository

        rt = reading.reading_type
        mon_repo = RemoteMonitoringRepository(self.db)
        row = mon_repo.resolve_threshold(reading_type=str(rt), patient_id=reading.patient_id)

        if reading.reading_type == MonitoringReadingType.BLOOD_PRESSURE:
            return self._score_bp(reading, row)

        value = _to_float(reading.primary_value)
        if value is None:
            return None, None, None

        if row is not None:
            nlow = _to_float(row.min_normal)
            nhigh = _to_float(row.max_normal)
            clow = _to_float(row.critical_low)
            chigh = _to_float(row.critical_high)
        else:
            bounds = _DEFAULT_BOUNDS.get(rt)
            if not bounds:
                return None, None, None
            nlow, nhigh, clow, chigh = (float(b) for b in bounds)

        return self._classify(reading.reading_type, value, nlow, nhigh, clow, chigh, reading.unit)

    def _score_bp(self, reading: MonitoringReading, row):
        sys = reading.systolic
        dia = reading.diastolic
        if sys is None and dia is None:
            return None, None, None
        if row is not None:
            nlow = _to_float(row.min_normal)
            nhigh = _to_float(row.max_normal)
            clow = _to_float(row.critical_low)
            chigh = _to_float(row.critical_high)
            dlow = _to_float(row.min_normal_secondary)
            dhigh = _to_float(row.max_normal_secondary)
        else:
            nlow, nhigh, clow, chigh = _DEFAULT_BOUNDS[MonitoringReadingType.BLOOD_PRESSURE]
            dlow, dhigh = _DEFAULT_BP_DIASTOLIC

        sev_s, type_s, det_s = self._classify(
            MonitoringReadingType.BLOOD_PRESSURE, float(sys) if sys is not None else None,
            nlow, nhigh, clow, chigh, "mmHg", component="Systolic",
        )
        # diastolic: normal band only -> warning if outside
        sev_d = AlertSeverity.INFORMATION
        det_d = None
        if dia is not None and dlow is not None and dhigh is not None:
            if dia < dlow or dia > dhigh:
                sev_d = AlertSeverity.WARNING
                det_d = f"Diastolic {dia} mmHg outside {dlow:.0f}-{dhigh:.0f}."
        severity = _sev_max(sev_s or AlertSeverity.INFORMATION, sev_d)
        if severity == AlertSeverity.INFORMATION:
            return None, None, None
        alert_type = AlertType.HIGH_BLOOD_PRESSURE
        if sys is not None and nlow is not None and sys < nlow:
            alert_type = AlertType.LOW_BLOOD_PRESSURE
        detail = " ".join(d for d in [det_s, det_d] if d) or f"BP {sys}/{dia} mmHg abnormal."
        return severity, alert_type, detail

    def _classify(self, rt, value, nlow, nhigh, clow, chigh, unit, component: str = ""):
        if value is None:
            return None, None, None
        label = (component + " ") if component else ""
        u = unit or ""
        # Critical breach
        if clow is not None and value < clow:
            sev = AlertSeverity.EMERGENCY if rt == MonitoringReadingType.OXYGEN_SATURATION else AlertSeverity.URGENT
            return sev, self._type_for(rt, low=True), f"{label}{value:g}{u} below critical {clow:g}."
        if chigh is not None and value > chigh:
            return AlertSeverity.URGENT, self._type_for(rt, low=False), f"{label}{value:g}{u} above critical {chigh:g}."
        # Warning band
        if nlow is not None and value < nlow:
            return AlertSeverity.WARNING, self._type_for(rt, low=True), f"{label}{value:g}{u} below normal {nlow:g}."
        if nhigh is not None and value > nhigh:
            return AlertSeverity.WARNING, self._type_for(rt, low=False), f"{label}{value:g}{u} above normal {nhigh:g}."
        return AlertSeverity.INFORMATION, None, None

    @staticmethod
    def _type_for(rt, *, low: bool) -> AlertType:
        if rt == MonitoringReadingType.OXYGEN_SATURATION:
            return AlertType.LOW_OXYGEN
        if rt == MonitoringReadingType.BLOOD_GLUCOSE:
            return AlertType.LOW_GLUCOSE if low else AlertType.HIGH_GLUCOSE
        if rt == MonitoringReadingType.BLOOD_PRESSURE:
            return AlertType.LOW_BLOOD_PRESSURE if low else AlertType.HIGH_BLOOD_PRESSURE
        if rt == MonitoringReadingType.WEIGHT:
            return AlertType.WEIGHT_CHANGE
        return AlertType.ABNORMAL_VITALS

    def _score_by_rules(self, reading: MonitoringReading):
        rules = self.repository.list_rules(reading_type=str(reading.reading_type), active_only=True)
        if not rules:
            return None, None, None
        value = _to_float(reading.primary_value)
        if value is None and reading.reading_type == MonitoringReadingType.BLOOD_PRESSURE:
            value = _to_float(reading.systolic)
        if value is None:
            return None, None, None

        best = None
        for r in rules:
            t = _to_float(r.threshold_value)
            th = _to_float(r.threshold_value_high)
            hit = False
            if r.comparator == AlertComparator.GREATER_THAN and t is not None:
                hit = value > t
            elif r.comparator == AlertComparator.GREATER_OR_EQUAL and t is not None:
                hit = value >= t
            elif r.comparator == AlertComparator.LESS_THAN and t is not None:
                hit = value < t
            elif r.comparator == AlertComparator.LESS_OR_EQUAL and t is not None:
                hit = value <= t
            elif r.comparator == AlertComparator.EQUAL and t is not None:
                hit = value == t
            elif r.comparator == AlertComparator.OUTSIDE_RANGE and t is not None and th is not None:
                hit = value < t or value > th
            if hit:
                if best is None or _SEVERITY_ORDER[r.severity] > _SEVERITY_ORDER[best.severity]:
                    best = r
        if best is None:
            return None, None, None
        return best.severity, best.alert_type, f"Rule '{best.name}' matched (value {value:g})."

    @staticmethod
    def _reading_label(rt) -> str:
        return str(rt).replace("_", " ").title()

    # =====================================================================
    # Raising + workflow
    # =====================================================================
    def raise_alert(
        self,
        *,
        patient_id: int,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: Optional[str] = None,
        care_plan_id: Optional[int] = None,
        home_visit_id: Optional[int] = None,
        assigned_to_staff_id: Optional[int] = None,
        context: Optional[dict] = None,
        dedupe_key: Optional[str] = None,
        dedupe_window_minutes: int = 60,
        commit: bool = True,
        dispatch: bool = True,
    ) -> Optional[ClinicalAlert]:
        """Generic alert entrypoint for other services and manual creation."""
        if dedupe_key:
            existing = self.repository.find_recent_by_dedupe(dedupe_key, window_minutes=dedupe_window_minutes)
            if existing:
                return existing
        alert = self.repository.create(
            patient_id=patient_id,
            alert_type=alert_type,
            severity=severity,
            status=AlertStatus.OPEN,
            title=title,
            message=message,
            care_plan_id=care_plan_id,
            home_visit_id=home_visit_id,
            assigned_to_staff_id=assigned_to_staff_id,
            context=context,
            dedupe_key=dedupe_key,
            triggered_at=datetime.now(timezone.utc),
        )
        if commit:
            self.db.commit()
        if dispatch:
            self.dispatch_alert(alert)
        return alert

    def create_manual(self, payload, *, actor_user_id: Optional[int] = None) -> ClinicalAlert:
        self.repository.get_required_patient(payload.patient_id)
        return self.raise_alert(
            patient_id=payload.patient_id,
            alert_type=payload.alert_type,
            severity=payload.severity,
            title=payload.title,
            message=payload.message,
            care_plan_id=payload.care_plan_id,
            home_visit_id=payload.home_visit_id,
            assigned_to_staff_id=payload.assigned_to_staff_id,
            context=payload.context,
            dedupe_key=None,
        )

    def get(self, alert_id: int) -> ClinicalAlert:
        return self._decorate(self.repository.get_required(alert_id))

    def list(self, **kwargs):
        items, total = self.repository.list(**kwargs)
        for a in items:
            self._decorate(a)
        return items, total

    def summary(self) -> dict:
        return self.repository.summary()

    def acknowledge(self, alert_id: int, *, actor_user_id: Optional[int], note: Optional[str] = None) -> ClinicalAlert:
        a = self.repository.get_required(alert_id)
        if a.status in (AlertStatus.RESOLVED, AlertStatus.DISMISSED):
            raise BadRequestError(message="Alert is already closed.")
        a.status = AlertStatus.ACKNOWLEDGED
        a.acknowledged_by_user_id = actor_user_id
        a.acknowledged_at = datetime.now(timezone.utc)
        if note:
            a.message = f"{a.message or ''}\n[Ack] {note}".strip()
        self.db.commit()
        self.db.refresh(a)
        return self._decorate(a)

    def resolve(self, alert_id: int, *, actor_user_id: Optional[int], resolution_note: Optional[str] = None) -> ClinicalAlert:
        a = self.repository.get_required(alert_id)
        a.status = AlertStatus.RESOLVED
        a.resolved_by_user_id = actor_user_id
        a.resolved_at = datetime.now(timezone.utc)
        a.resolution_note = resolution_note
        self.db.commit()
        self.db.refresh(a)
        return self._decorate(a)

    def dismiss(self, alert_id: int, *, actor_user_id: Optional[int], note: Optional[str] = None) -> ClinicalAlert:
        a = self.repository.get_required(alert_id)
        a.status = AlertStatus.DISMISSED
        a.resolved_by_user_id = actor_user_id
        a.resolved_at = datetime.now(timezone.utc)
        a.resolution_note = note
        self.db.commit()
        self.db.refresh(a)
        return self._decorate(a)

    def escalate(self, alert_id: int, *, actor_user_id: Optional[int], escalated_to_staff_id: Optional[int] = None, note: Optional[str] = None) -> ClinicalAlert:
        a = self.repository.get_required(alert_id)
        a.status = AlertStatus.ESCALATED
        a.escalated_at = datetime.now(timezone.utc)
        if escalated_to_staff_id:
            a.escalated_to_staff_id = escalated_to_staff_id
            a.assigned_to_staff_id = escalated_to_staff_id
        if note:
            a.message = (a.message or "") + f"\n[Escalation] {note}"
        self.db.commit()
        self.db.refresh(a)
        self.dispatch_alert(a, escalated=True)
        return self._decorate(a)

    # -- rules --
    def create_rule(self, payload) -> "EarlyWarningRule":  # type: ignore[name-defined]
        r = self.repository.create_rule(
            name=payload.name,
            description=payload.description,
            reading_type=payload.reading_type,
            comparator=payload.comparator,
            threshold_value=payload.threshold_value,
            threshold_value_high=payload.threshold_value_high,
            alert_type=payload.alert_type,
            severity=payload.severity,
            auto_escalate=payload.auto_escalate,
            notify_roles=payload.notify_roles,
        )
        self.db.commit()
        self.db.refresh(r)
        return r

    def update_rule(self, rule_id: int, payload):
        r = self.repository.get_rule(rule_id)
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(r, k, v)
        self.db.commit()
        self.db.refresh(r)
        return r

    def list_rules(self, **kwargs):
        return self.repository.list_rules(**kwargs)

    # =====================================================================
    # Notification dispatch
    # =====================================================================
    def _decorate(self, alert: ClinicalAlert) -> ClinicalAlert:
        try:
            alert.patient_name = self.repository.patient_name(alert.patient_id)
        except Exception:
            alert.patient_name = None
        return alert

    def dispatch_alert(self, alert: ClinicalAlert, *, escalated: bool = False) -> None:
        try:
            from app.core.enums import NotificationEvent
            from app.models.all_models import Role, User, UserRoleAssociation
            from app.services.notification_dispatcher import NotificationDispatcher

            care_team = (
                self.db.query(User)
                .join(UserRoleAssociation, UserRoleAssociation.user_id == User.id)
                .join(Role, Role.id == UserRoleAssociation.role_id)
                .filter(
                    Role.code.in_(["DOCTOR", "NURSE", "CLINICIAN", "TENANT_ADMIN", "HOME_HEALTH_COORDINATOR"]),
                    User.is_deleted.is_(False),
                )
                .all()
            )
            if not care_team:
                return
            urgent = alert.severity in (AlertSeverity.URGENT, AlertSeverity.EMERGENCY)
            prefix = "ESCALATED — " if escalated else ""
            NotificationDispatcher(self.db).dispatch(
                event=NotificationEvent.SYSTEM_ALERT,
                recipients=care_team,
                subject=f"{prefix}{alert.severity.value.title()} clinical alert",
                body=f"{alert.title}. {alert.message or ''}".strip(),
                context={
                    "alert_id": alert.id,
                    "patient_id": alert.patient_id,
                    "severity": str(alert.severity),
                    "alert_type": str(alert.alert_type),
                },
                suppress_quiet_hours=not urgent,
            )
        except Exception as exc:
            logger.warning("Alert dispatch failed for alert %s: %s", getattr(alert, "id", "?"), exc)
