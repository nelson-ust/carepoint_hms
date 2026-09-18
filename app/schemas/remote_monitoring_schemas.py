# app/schemas/remote_monitoring_schemas.py
from __future__ import annotations

"""Pydantic schemas for Remote Patient Monitoring."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import MonitoringDeviceType, MonitoringReadingType, MonitoringSource


# ---- Device ----
class MonitoringDeviceCreateSchema(BaseModel):
    patient_id: int
    device_type: MonitoringDeviceType = MonitoringDeviceType.OTHER
    name: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    identifier: Optional[str] = None
    connection_type: MonitoringSource = MonitoringSource.MANUAL
    notes: Optional[str] = None


class MonitoringDeviceReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    device_type: str
    name: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    identifier: Optional[str] = None
    connection_type: str
    assigned_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    notes: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


# ---- Reading ----
class MonitoringReadingCreateSchema(BaseModel):
    patient_id: int
    care_plan_id: Optional[int] = None
    home_visit_id: Optional[int] = None
    device_id: Optional[int] = None
    reading_type: MonitoringReadingType
    source: MonitoringSource = MonitoringSource.MANUAL
    primary_value: Optional[Decimal] = None
    secondary_value: Optional[Decimal] = None
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    unit: Optional[str] = None
    raw: Optional[dict] = None
    recorded_at: Optional[datetime] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_value_present(self):
        if self.reading_type == MonitoringReadingType.BLOOD_PRESSURE:
            if self.systolic is None or self.diastolic is None:
                raise ValueError("Blood pressure readings require both systolic and diastolic.")
        else:
            if self.primary_value is None and self.raw is None:
                raise ValueError("A reading requires primary_value (or a raw payload).")
        return self


class MonitoringReadingReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    care_plan_id: Optional[int] = None
    home_visit_id: Optional[int] = None
    device_id: Optional[int] = None
    reading_type: str
    source: str
    primary_value: Optional[Decimal] = None
    secondary_value: Optional[Decimal] = None
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    unit: Optional[str] = None
    raw: Optional[dict] = None
    is_abnormal: bool = False
    severity: Optional[str] = None
    recorded_at: datetime
    received_at: Optional[datetime] = None
    recorded_by_user_id: Optional[int] = None
    notes: Optional[str] = None


# ---- Threshold ----
class MonitoringThresholdUpsertSchema(BaseModel):
    patient_id: Optional[int] = None
    reading_type: MonitoringReadingType
    unit: Optional[str] = None
    min_normal: Optional[Decimal] = None
    max_normal: Optional[Decimal] = None
    critical_low: Optional[Decimal] = None
    critical_high: Optional[Decimal] = None
    min_normal_secondary: Optional[Decimal] = None
    max_normal_secondary: Optional[Decimal] = None


class MonitoringThresholdReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: Optional[int] = None
    reading_type: str
    unit: Optional[str] = None
    min_normal: Optional[Decimal] = None
    max_normal: Optional[Decimal] = None
    critical_low: Optional[Decimal] = None
    critical_high: Optional[Decimal] = None
    min_normal_secondary: Optional[Decimal] = None
    max_normal_secondary: Optional[Decimal] = None
    is_active: bool = True


# ---- Trend ----
class TrendPointSchema(BaseModel):
    recorded_at: datetime
    primary_value: Optional[Decimal] = None
    secondary_value: Optional[Decimal] = None
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    is_abnormal: bool = False
    severity: Optional[str] = None


class MonitoringTrendResponseSchema(BaseModel):
    success: bool = True
    message: str = "Trend fetched successfully."
    patient_id: int
    reading_type: str
    unit: Optional[str] = None
    points: list[TrendPointSchema]
    count: int


# ---- Response wrappers ----
class MonitoringReadingActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    reading: MonitoringReadingReadSchema
    alert_raised: bool = False
    alert_id: Optional[int] = None
    alert_severity: Optional[str] = None


class MonitoringDeviceResponseSchema(BaseModel):
    success: bool = True
    message: str
    device: MonitoringDeviceReadSchema


class MonitoringReadingListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Readings fetched successfully."
    items: list[MonitoringReadingReadSchema]
    count: int
    meta: dict


class MonitoringDeviceListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Devices fetched successfully."
    items: list[MonitoringDeviceReadSchema]
    count: int
    meta: dict


class MonitoringThresholdResponseSchema(BaseModel):
    success: bool = True
    message: str
    threshold: MonitoringThresholdReadSchema


class MonitoringThresholdListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Thresholds fetched successfully."
    items: list[MonitoringThresholdReadSchema]
    count: int
    meta: dict
