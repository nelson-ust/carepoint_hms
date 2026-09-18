# app/repositories/clinical_alert_repository.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import AlertStatus
from app.core.exceptions import NotFoundError
from app.models.all_models import Patient
from app.models.home_health_models import ClinicalAlert, EarlyWarningRule


class ClinicalAlertRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_required_patient(self, patient_id: int) -> Patient:
        p = (
            self.db.query(Patient)
            .filter(Patient.id == patient_id, Patient.is_deleted.is_(False))
            .first()
        )
        if not p:
            raise NotFoundError(message="Patient not found.", detail={"patient_id": patient_id})
        return p

    def patient_name(self, patient_id: int) -> Optional[str]:
        row = (
            self.db.query(Patient.first_name, Patient.last_name)
            .filter(Patient.id == patient_id)
            .first()
        )
        if not row:
            return None
        return " ".join(x for x in [row[0], row[1]] if x).strip() or None

    # -- alerts --
    def create(self, **kwargs) -> ClinicalAlert:
        kwargs.setdefault("triggered_at", datetime.now(timezone.utc))
        a = ClinicalAlert(**kwargs)
        self.db.add(a)
        self.db.flush()
        self.db.refresh(a)
        return a

    def get_by_id(self, alert_id: int) -> Optional[ClinicalAlert]:
        return (
            self.db.query(ClinicalAlert)
            .filter(ClinicalAlert.id == alert_id, ClinicalAlert.is_deleted.is_(False))
            .first()
        )

    def get_required(self, alert_id: int) -> ClinicalAlert:
        a = self.get_by_id(alert_id)
        if not a:
            raise NotFoundError(message="Alert not found.", detail={"alert_id": alert_id})
        return a

    def find_recent_by_dedupe(self, dedupe_key: str, *, window_minutes: int = 60) -> Optional[ClinicalAlert]:
        if not dedupe_key:
            return None
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        return (
            self.db.query(ClinicalAlert)
            .filter(
                ClinicalAlert.dedupe_key == dedupe_key,
                ClinicalAlert.is_deleted.is_(False),
                ClinicalAlert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED, AlertStatus.IN_REVIEW, AlertStatus.ESCALATED]),
                ClinicalAlert.triggered_at >= cutoff,
            )
            .order_by(ClinicalAlert.triggered_at.desc())
            .first()
        )

    def list(
        self,
        *,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
        patient_id: Optional[int] = None,
        assigned_to_staff_id: Optional[int] = None,
        open_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ClinicalAlert], int]:
        query = self.db.query(ClinicalAlert).filter(ClinicalAlert.is_deleted.is_(False))
        if open_only:
            query = query.filter(
                ClinicalAlert.status.in_(
                    [AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED, AlertStatus.IN_REVIEW, AlertStatus.ESCALATED]
                )
            )
        if status:
            query = query.filter(ClinicalAlert.status == status)
        if severity:
            query = query.filter(ClinicalAlert.severity == severity)
        if alert_type:
            query = query.filter(ClinicalAlert.alert_type == alert_type)
        if patient_id:
            query = query.filter(ClinicalAlert.patient_id == patient_id)
        if assigned_to_staff_id:
            query = query.filter(ClinicalAlert.assigned_to_staff_id == assigned_to_staff_id)
        total = query.with_entities(func.count(ClinicalAlert.id)).scalar() or 0
        items = (
            query.order_by(ClinicalAlert.triggered_at.desc(), ClinicalAlert.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def summary(self) -> dict:
        open_states = [AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED, AlertStatus.IN_REVIEW, AlertStatus.ESCALATED]
        base = self.db.query(ClinicalAlert).filter(
            ClinicalAlert.is_deleted.is_(False),
            ClinicalAlert.status.in_(open_states),
        )
        open_total = base.with_entities(func.count(ClinicalAlert.id)).scalar() or 0
        by_sev = dict(
            base.with_entities(ClinicalAlert.severity, func.count(ClinicalAlert.id))
            .group_by(ClinicalAlert.severity)
            .all()
        )
        by_status = dict(
            self.db.query(ClinicalAlert.status, func.count(ClinicalAlert.id))
            .filter(ClinicalAlert.is_deleted.is_(False))
            .group_by(ClinicalAlert.status)
            .all()
        )
        return {
            "open_total": int(open_total),
            "by_severity": {str(k): int(v) for k, v in by_sev.items()},
            "by_status": {str(k): int(v) for k, v in by_status.items()},
        }

    # -- rules --
    def create_rule(self, **kwargs) -> EarlyWarningRule:
        r = EarlyWarningRule(**kwargs)
        self.db.add(r)
        self.db.flush()
        self.db.refresh(r)
        return r

    def get_rule(self, rule_id: int) -> EarlyWarningRule:
        r = (
            self.db.query(EarlyWarningRule)
            .filter(EarlyWarningRule.id == rule_id, EarlyWarningRule.is_deleted.is_(False))
            .first()
        )
        if not r:
            raise NotFoundError(message="Rule not found.", detail={"rule_id": rule_id})
        return r

    def list_rules(
        self, *, reading_type: Optional[str] = None, active_only: bool = True
    ) -> list[EarlyWarningRule]:
        query = self.db.query(EarlyWarningRule).filter(EarlyWarningRule.is_deleted.is_(False))
        if active_only:
            query = query.filter(EarlyWarningRule.is_active.is_(True))
        if reading_type:
            query = query.filter(EarlyWarningRule.reading_type == reading_type)
        return query.order_by(EarlyWarningRule.id.asc()).all()
