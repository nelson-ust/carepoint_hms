# app/repositories/remote_monitoring_repository.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.all_models import Patient
from app.models.home_health_models import (
    MonitoringDevice,
    MonitoringReading,
    MonitoringThreshold,
)


class RemoteMonitoringRepository:
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

    # -- devices --
    def create_device(self, **kwargs) -> MonitoringDevice:
        d = MonitoringDevice(**kwargs)
        self.db.add(d)
        self.db.flush()
        self.db.refresh(d)
        return d

    def get_device(self, device_id: int) -> MonitoringDevice:
        d = (
            self.db.query(MonitoringDevice)
            .filter(MonitoringDevice.id == device_id, MonitoringDevice.is_deleted.is_(False))
            .first()
        )
        if not d:
            raise NotFoundError(message="Device not found.", detail={"device_id": device_id})
        return d

    def list_devices(
        self, *, patient_id: Optional[int] = None, skip: int = 0, limit: int = 50
    ) -> tuple[list[MonitoringDevice], int]:
        query = self.db.query(MonitoringDevice).filter(MonitoringDevice.is_deleted.is_(False))
        if patient_id:
            query = query.filter(MonitoringDevice.patient_id == patient_id)
        total = query.with_entities(func.count(MonitoringDevice.id)).scalar() or 0
        items = query.order_by(MonitoringDevice.id.desc()).offset(skip).limit(limit).all()
        return items, int(total)

    # -- readings --
    def create_reading(self, **kwargs) -> MonitoringReading:
        kwargs.setdefault("recorded_at", datetime.now(timezone.utc))
        kwargs.setdefault("received_at", datetime.now(timezone.utc))
        r = MonitoringReading(**kwargs)
        self.db.add(r)
        self.db.flush()
        self.db.refresh(r)
        return r

    def get_reading(self, reading_id: int) -> MonitoringReading:
        r = (
            self.db.query(MonitoringReading)
            .filter(MonitoringReading.id == reading_id, MonitoringReading.is_deleted.is_(False))
            .first()
        )
        if not r:
            raise NotFoundError(message="Reading not found.", detail={"reading_id": reading_id})
        return r

    def list_readings(
        self,
        *,
        patient_id: Optional[int] = None,
        reading_type: Optional[str] = None,
        care_plan_id: Optional[int] = None,
        home_visit_id: Optional[int] = None,
        abnormal_only: bool = False,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[MonitoringReading], int]:
        query = self.db.query(MonitoringReading).filter(MonitoringReading.is_deleted.is_(False))
        if patient_id:
            query = query.filter(MonitoringReading.patient_id == patient_id)
        if reading_type:
            query = query.filter(MonitoringReading.reading_type == reading_type)
        if care_plan_id:
            query = query.filter(MonitoringReading.care_plan_id == care_plan_id)
        if home_visit_id:
            query = query.filter(MonitoringReading.home_visit_id == home_visit_id)
        if abnormal_only:
            query = query.filter(MonitoringReading.is_abnormal.is_(True))
        if from_dt:
            query = query.filter(MonitoringReading.recorded_at >= from_dt)
        if to_dt:
            query = query.filter(MonitoringReading.recorded_at < to_dt)
        total = query.with_entities(func.count(MonitoringReading.id)).scalar() or 0
        items = (
            query.order_by(MonitoringReading.recorded_at.desc(), MonitoringReading.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def trend(
        self, *, patient_id: int, reading_type: str, limit: int = 100
    ) -> list[MonitoringReading]:
        return (
            self.db.query(MonitoringReading)
            .filter(
                MonitoringReading.patient_id == patient_id,
                MonitoringReading.reading_type == reading_type,
                MonitoringReading.is_deleted.is_(False),
            )
            .order_by(MonitoringReading.recorded_at.asc())
            .limit(limit)
            .all()
        )

    # -- thresholds --
    def resolve_threshold(
        self, *, reading_type: str, patient_id: Optional[int]
    ) -> Optional[MonitoringThreshold]:
        """Patient-specific threshold if present, else the tenant default (patient_id NULL)."""
        if patient_id is not None:
            specific = (
                self.db.query(MonitoringThreshold)
                .filter(
                    MonitoringThreshold.reading_type == reading_type,
                    MonitoringThreshold.patient_id == patient_id,
                    MonitoringThreshold.is_deleted.is_(False),
                    MonitoringThreshold.is_active.is_(True),
                )
                .first()
            )
            if specific:
                return specific
        return (
            self.db.query(MonitoringThreshold)
            .filter(
                MonitoringThreshold.reading_type == reading_type,
                MonitoringThreshold.patient_id.is_(None),
                MonitoringThreshold.is_deleted.is_(False),
                MonitoringThreshold.is_active.is_(True),
            )
            .first()
        )

    def find_threshold_row(
        self, *, reading_type: str, patient_id: Optional[int]
    ) -> Optional[MonitoringThreshold]:
        q = self.db.query(MonitoringThreshold).filter(
            MonitoringThreshold.reading_type == reading_type,
            MonitoringThreshold.is_deleted.is_(False),
        )
        if patient_id is None:
            q = q.filter(MonitoringThreshold.patient_id.is_(None))
        else:
            q = q.filter(MonitoringThreshold.patient_id == patient_id)
        return q.first()

    def upsert_threshold(self, *, reading_type: str, patient_id: Optional[int], **fields) -> MonitoringThreshold:
        row = self.find_threshold_row(reading_type=reading_type, patient_id=patient_id)
        if row:
            for k, v in fields.items():
                setattr(row, k, v)
            row.is_active = True
        else:
            row = MonitoringThreshold(reading_type=reading_type, patient_id=patient_id, **fields)
            self.db.add(row)
        self.db.flush()
        self.db.refresh(row)
        return row

    def list_thresholds(
        self, *, patient_id: Optional[int] = None, include_defaults: bool = True
    ) -> list[MonitoringThreshold]:
        query = self.db.query(MonitoringThreshold).filter(MonitoringThreshold.is_deleted.is_(False))
        if patient_id is not None:
            if include_defaults:
                query = query.filter(
                    (MonitoringThreshold.patient_id == patient_id)
                    | (MonitoringThreshold.patient_id.is_(None))
                )
            else:
                query = query.filter(MonitoringThreshold.patient_id == patient_id)
        return query.order_by(MonitoringThreshold.reading_type.asc()).all()
