# app/api/v1/endpoints/remote_monitoring_routes.py
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.remote_monitoring_schemas import (
    MonitoringDeviceCreateSchema,
    MonitoringDeviceListResponseSchema,
    MonitoringDeviceResponseSchema,
    MonitoringReadingActionResponseSchema,
    MonitoringReadingCreateSchema,
    MonitoringReadingListResponseSchema,
    MonitoringThresholdListResponseSchema,
    MonitoringThresholdResponseSchema,
    MonitoringThresholdUpsertSchema,
    MonitoringTrendResponseSchema,
)
from app.services.remote_monitoring_service import RemoteMonitoringService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/remote-monitoring",
    tags=["Home Health - Remote Monitoring"],
    dependencies=[Depends(require_plan_feature("clinical"))],
)

_READ = require_permission("REMOTE_MONITORING_READ", "REMOTE_MONITORING_RECORD", "REMOTE_MONITORING_MANAGE")


def get_service(db: Annotated[Session, Depends(get_db)]) -> RemoteMonitoringService:
    return RemoteMonitoringService(db)


# ----- Devices -----
@router.get("/devices", response_model=MonitoringDeviceListResponseSchema, summary="List monitoring devices")
def list_devices(
    _: Annotated[User, Depends(_READ)],
    service: Annotated[RemoteMonitoringService, Depends(get_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    patient_id: Optional[int] = Query(None),
):
    items, total = service.list_devices(patient_id=patient_id, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit, message="Devices fetched successfully.")


@router.post("/devices", response_model=MonitoringDeviceResponseSchema, status_code=status.HTTP_201_CREATED, summary="Register a monitoring device")
def register_device(
    payload: MonitoringDeviceCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[RemoteMonitoringService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("REMOTE_MONITORING_MANAGE", "REMOTE_MONITORING_RECORD"))],
):
    device = service.register_device(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Device registered.", "device": device}


# ----- Readings -----
@router.get("/readings", response_model=MonitoringReadingListResponseSchema, summary="List monitoring readings")
def list_readings(
    _: Annotated[User, Depends(_READ)],
    service: Annotated[RemoteMonitoringService, Depends(get_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    patient_id: Optional[int] = Query(None),
    reading_type: Optional[str] = Query(None),
    care_plan_id: Optional[int] = Query(None),
    home_visit_id: Optional[int] = Query(None),
    abnormal_only: bool = Query(False),
    from_dt: Optional[datetime] = Query(None),
    to_dt: Optional[datetime] = Query(None),
):
    items, total = service.list_readings(
        patient_id=patient_id, reading_type=reading_type, care_plan_id=care_plan_id,
        home_visit_id=home_visit_id, abnormal_only=abnormal_only, from_dt=from_dt, to_dt=to_dt,
        skip=skip, limit=limit,
    )
    return paginate_response(items=items, total=total, skip=skip, limit=limit, message="Readings fetched successfully.")


@router.post("/readings", response_model=MonitoringReadingActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Record a monitoring reading")
def record_reading(
    payload: MonitoringReadingCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[RemoteMonitoringService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("REMOTE_MONITORING_RECORD", "REMOTE_MONITORING_MANAGE"))],
):
    reading, alert = service.record_reading(payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Reading recorded.",
        "reading": reading,
        "alert_raised": alert is not None,
        "alert_id": alert.id if alert else None,
        "alert_severity": str(alert.severity) if alert else None,
    }


@router.get("/patients/{patient_id}/trends", response_model=MonitoringTrendResponseSchema, summary="Reading trend for a patient")
def patient_trend(
    patient_id: int,
    _: Annotated[User, Depends(_READ)],
    service: Annotated[RemoteMonitoringService, Depends(get_service)],
    reading_type: str = Query(..., description="Measurement type, e.g. BLOOD_PRESSURE"),
    limit: int = Query(100, ge=1, le=500),
):
    points, unit = service.trend(patient_id=patient_id, reading_type=reading_type, limit=limit)
    return {
        "success": True,
        "message": "Trend fetched successfully.",
        "patient_id": patient_id,
        "reading_type": reading_type,
        "unit": unit,
        "points": points,
        "count": len(points),
    }


# ----- Thresholds -----
@router.get("/thresholds", response_model=MonitoringThresholdListResponseSchema, summary="List monitoring thresholds")
def list_thresholds(
    _: Annotated[User, Depends(_READ)],
    service: Annotated[RemoteMonitoringService, Depends(get_service)],
    patient_id: Optional[int] = Query(None),
    include_defaults: bool = Query(True),
):
    items = service.list_thresholds(patient_id=patient_id, include_defaults=include_defaults)
    return paginate_response(items=items, total=len(items), skip=0, limit=len(items) or 1, message="Thresholds fetched successfully.")


@router.post("/thresholds", response_model=MonitoringThresholdResponseSchema, summary="Create/update a monitoring threshold")
def upsert_threshold(
    payload: MonitoringThresholdUpsertSchema,
    service: Annotated[RemoteMonitoringService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("REMOTE_MONITORING_MANAGE"))],
):
    row = service.upsert_threshold(payload)
    return {"success": True, "message": "Threshold saved.", "threshold": row}
