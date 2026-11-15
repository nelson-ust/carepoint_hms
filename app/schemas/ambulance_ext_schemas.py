# app/schemas/ambulance_ext_schemas.py
from __future__ import annotations

"""Schemas for extended ambulance EMS processes (crew, PCR, fuel, trip billing)."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class CrewCreateSchema(BaseModel):
    role: str = "PARAMEDIC"
    staff_profile_id: Optional[int] = None
    member_name: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class PCRUpsertSchema(BaseModel):
    chief_complaint: Optional[str] = None
    blood_pressure: Optional[str] = Field(None, max_length=20)
    pulse_rate: Optional[int] = Field(None, ge=0, le=400)
    temperature_celsius: Optional[Decimal] = None
    oxygen_saturation: Optional[int] = Field(None, ge=0, le=100)
    respiratory_rate: Optional[int] = Field(None, ge=0, le=120)
    interventions: Optional[str] = None
    medications_given: Optional[str] = None
    condition_on_handover: Optional[str] = Field(None, max_length=255)
    receiving_facility: Optional[str] = Field(None, max_length=255)
    receiving_staff: Optional[str] = Field(None, max_length=255)
    narrative: Optional[str] = None


class FuelCreateSchema(BaseModel):
    litres: Decimal = Field(..., gt=0)
    cost: Optional[Decimal] = None
    odometer: Optional[Decimal] = None
    station: Optional[str] = Field(None, max_length=255)
    filled_by: Optional[str] = Field(None, max_length=255)
    logged_at: Optional[datetime] = None
    notes: Optional[str] = None


class TripChargeCreateSchema(BaseModel):
    description: Optional[str] = Field(None, max_length=255)
    amount: Decimal = Field(..., ge=0)
    payer_name: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class ChargeStatusSchema(BaseModel):
    status: str  # PAID / WAIVED


class AmbExtListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Fetched successfully."
    items: list[dict]
    count: int
    meta: dict


class AmbExtActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    data: dict
