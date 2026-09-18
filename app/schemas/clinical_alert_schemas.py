# app/schemas/clinical_alert_schemas.py
from __future__ import annotations

"""Pydantic schemas for Clinical Alerts / Early Warning."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.core.enums import (
    AlertComparator,
    AlertSeverity,
    AlertStatus,
    AlertType,
    MonitoringReadingType,
)


# ---- Alert ----
class ClinicalAlertCreateSchema(BaseModel):
    patient_id: int
    care_plan_id: Optional[int] = None
    home_visit_id: Optional[int] = None
    alert_type: AlertType = AlertType.OTHER
    severity: AlertSeverity = AlertSeverity.INFORMATION
    title: str
    message: Optional[str] = None
    assigned_to_staff_id: Optional[int] = None
    context: Optional[dict] = None


class ClinicalAlertReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    care_plan_id: Optional[int] = None
    home_visit_id: Optional[int] = None
    reading_id: Optional[int] = None
    alert_type: str
    severity: str
    status: str
    title: str
    message: Optional[str] = None
    context: Optional[dict] = None
    triggered_at: datetime
    assigned_to_staff_id: Optional[int] = None
    acknowledged_by_user_id: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    escalated_to_staff_id: Optional[int] = None
    resolved_by_user_id: Optional[int] = None
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    patient_name: Optional[str] = None
    created_at: Optional[datetime] = None


class AlertAcknowledgeSchema(BaseModel):
    note: Optional[str] = None


class AlertResolveSchema(BaseModel):
    resolution_note: Optional[str] = None


class AlertEscalateSchema(BaseModel):
    escalated_to_staff_id: Optional[int] = None
    note: Optional[str] = None


# ---- Early-warning rule ----
class EarlyWarningRuleCreateSchema(BaseModel):
    name: str
    description: Optional[str] = None
    reading_type: MonitoringReadingType
    comparator: AlertComparator
    threshold_value: Optional[Decimal] = None
    threshold_value_high: Optional[Decimal] = None
    alert_type: AlertType = AlertType.ABNORMAL_VITALS
    severity: AlertSeverity = AlertSeverity.WARNING
    auto_escalate: bool = False
    notify_roles: Optional[dict] = None


class EarlyWarningRuleUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    comparator: Optional[AlertComparator] = None
    threshold_value: Optional[Decimal] = None
    threshold_value_high: Optional[Decimal] = None
    alert_type: Optional[AlertType] = None
    severity: Optional[AlertSeverity] = None
    auto_escalate: Optional[bool] = None
    notify_roles: Optional[dict] = None
    is_active: Optional[bool] = None


class EarlyWarningRuleReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    reading_type: str
    comparator: str
    threshold_value: Optional[Decimal] = None
    threshold_value_high: Optional[Decimal] = None
    alert_type: str
    severity: str
    auto_escalate: bool = False
    notify_roles: Optional[dict] = None
    is_active: bool = True


# ---- Response wrappers ----
class ClinicalAlertActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    alert: ClinicalAlertReadSchema


class ClinicalAlertListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Alerts fetched successfully."
    items: list[ClinicalAlertReadSchema]
    count: int
    meta: dict


class AlertSummarySchema(BaseModel):
    success: bool = True
    open_total: int = 0
    by_severity: dict = {}
    by_status: dict = {}


class EarlyWarningRuleResponseSchema(BaseModel):
    success: bool = True
    message: str
    rule: EarlyWarningRuleReadSchema


class EarlyWarningRuleListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Rules fetched successfully."
    items: list[EarlyWarningRuleReadSchema]
    count: int
    meta: dict
