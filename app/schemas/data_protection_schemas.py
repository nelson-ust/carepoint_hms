# app/schemas/data_protection_schemas.py
from __future__ import annotations

"""Pydantic schemas for the Data Protection / NDPA module."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---- Consent ----
class ConsentCreateSchema(BaseModel):
    patient_id: Optional[int] = None
    subject_name: str = Field(..., min_length=1, max_length=255)
    consent_type: str
    lawful_basis: str = "CONSENT"
    purpose: Optional[str] = None
    policy_version: Optional[str] = Field(None, max_length=50)
    method: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class ConsentReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: Optional[int] = None
    subject_name: str
    consent_type: str
    status: str
    lawful_basis: str
    purpose: Optional[str] = None
    policy_version: Optional[str] = None
    method: Optional[str] = None
    granted_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


# ---- Data Subject Request ----
class DSRCreateSchema(BaseModel):
    patient_id: Optional[int] = None
    subject_name: str = Field(..., min_length=1, max_length=255)
    subject_contact: Optional[str] = Field(None, max_length=255)
    request_type: str
    details: Optional[str] = None


class DSRUpdateSchema(BaseModel):
    status: Optional[str] = None
    handler_staff_id: Optional[int] = None
    resolution_notes: Optional[str] = None


class DSRReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: Optional[int] = None
    subject_name: str
    subject_contact: Optional[str] = None
    request_type: str
    status: str
    received_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    details: Optional[str] = None
    resolution_notes: Optional[str] = None
    completed_at: Optional[datetime] = None
    overdue: bool = False
    created_at: Optional[datetime] = None


# ---- Breach ----
class BreachCreateSchema(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    severity: str = "MEDIUM"
    discovered_at: Optional[datetime] = None
    data_categories: Optional[str] = None
    subjects_affected: Optional[int] = None


class BreachUpdateSchema(BaseModel):
    status: Optional[str] = None
    severity: Optional[str] = None
    remediation: Optional[str] = None
    subjects_notified: Optional[bool] = None


class BreachReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: Optional[str] = None
    severity: str
    status: str
    discovered_at: Optional[datetime] = None
    notify_due_at: Optional[datetime] = None
    data_categories: Optional[str] = None
    subjects_affected: Optional[int] = None
    ndpc_notified: bool = False
    ndpc_notified_at: Optional[datetime] = None
    subjects_notified: bool = False
    remediation: Optional[str] = None
    notify_overdue: bool = False
    created_at: Optional[datetime] = None


# ---- RoPA ----
class RopaCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    purpose: Optional[str] = None
    lawful_basis: str = "CONSENT"
    data_categories: Optional[str] = None
    data_subjects: Optional[str] = None
    recipients: Optional[str] = None
    retention_period: Optional[str] = Field(None, max_length=255)
    cross_border: bool = False
    cross_border_detail: Optional[str] = None
    owner: Optional[str] = Field(None, max_length=255)


class RopaUpdateSchema(RopaCreateSchema):
    name: Optional[str] = Field(None, max_length=255)


class RopaReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    purpose: Optional[str] = None
    lawful_basis: str
    data_categories: Optional[str] = None
    data_subjects: Optional[str] = None
    recipients: Optional[str] = None
    retention_period: Optional[str] = None
    cross_border: bool = False
    cross_border_detail: Optional[str] = None
    owner: Optional[str] = None
    created_at: Optional[datetime] = None


# ---- Settings ----
class DPSettingsSchema(BaseModel):
    dpo_name: Optional[str] = Field(None, max_length=255)
    dpo_email: Optional[str] = Field(None, max_length=255)
    dpo_phone: Optional[str] = Field(None, max_length=50)
    privacy_policy_version: Optional[str] = Field(None, max_length=50)
    privacy_policy_url: Optional[str] = Field(None, max_length=500)
    privacy_policy_text: Optional[str] = None
    retention_months: Optional[int] = Field(None, ge=0, le=1200)
    breach_notify_hours: Optional[int] = Field(None, ge=1, le=240)
    dsr_response_days: Optional[int] = Field(None, ge=1, le=365)
    ndpc_registered: Optional[bool] = None


# ---- generic responses ----
class DPListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Fetched successfully."
    items: list[dict]
    count: int
    meta: dict


class DPActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    data: dict
