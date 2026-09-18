# app/services/remote_monitoring_service.py
from __future__ import annotations

"""Remote Patient Monitoring service."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.models.home_health_models import MonitoringDevice, MonitoringReading
from app.repositories.remote_monitoring_repository import RemoteMonitoringRepository
from app.services.clinical_alert_service import ClinicalAlertService

logger = get_logger(__name__)


class RemoteMonitoringService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = RemoteMonitoringRepository(db)
        self.alerts = ClinicalAlertService(db)

    # -- devices --
    def register_device(self, payload, *, actor_user_id: Optional[int] = None) -> MonitoringDevice:
        self.repository.get_required_patient(payload.patient_id)
        data = payload.model_dump(exclude_unset=True)
        data["assigned_at"] = datetime.now(timezone.utc)
        data["created_by_id"] = actor_user_id
        device = self.repository.create_device(**data)
        self.db.commit()
        self.db.refresh(device)
        return device

    def list_devices(self, **kwargs):
        return self.repository.list_devices(**kwargs)

    # -- readings --
    def record_reading(self, payload, *, actor_user_id: Optional[int] = None):
        self.repository.get_required_patient(payload.patient_id)
        data = payload.model_dump(exclude_unset=True)
        data.setdefault("recorded_at", datetime.now(timezone.utc))
        data["received_at"] = datetime.now(timezone.utc)
        data["recorded_by_user_id"] = actor_user_id
        data["created_by_id"] = actor_user_id

        reading = self.repository.create_reading(**data)

        # Early-warning evaluation (flushes the alert row, no commit yet).
        alert = None
        try:
            alert = self.alerts.evaluate_reading(reading)
        except Exception as exc:  # never let evaluation break capture
            logger.warning("Alert evaluation failed for reading %s: %s", reading.id, exc)

        self.db.commit()
        self.db.refresh(reading)

        if alert is not None:
            self.alerts.dispatch_alert(alert)

        return reading, alert

    def list_readings(self, **kwargs):
        return self.repository.list_readings(**kwargs)

    def trend(self, *, patient_id: int, reading_type: str, limit: int = 100):
        self.repository.get_required_patient(patient_id)
        points = self.repository.trend(patient_id=patient_id, reading_type=reading_type, limit=limit)
        unit = points[-1].unit if points else None
        return points, unit

    # -- thresholds --
    def upsert_threshold(self, payload) -> object:
        if payload.patient_id is not None:
            self.repository.get_required_patient(payload.patient_id)
        fields = payload.model_dump(exclude_unset=True, exclude={"reading_type", "patient_id"})
        row = self.repository.upsert_threshold(
            reading_type=payload.reading_type,
            patient_id=payload.patient_id,
            **fields,
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_thresholds(self, **kwargs):
        return self.repository.list_thresholds(**kwargs)
