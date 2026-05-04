# app/schemas/vital_sign_schema.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# Reasonable adult ranges. Validation rejects clearly impossible inputs but
# allows out-of-range clinically relevant values (those should be flagged in
# the UI, not blocked at the API layer).
TEMPERATURE_MIN = Decimal("25.0")
TEMPERATURE_MAX = Decimal("45.0")
PULSE_MIN = 20
PULSE_MAX = 250
RESP_MIN = 4
RESP_MAX = 80
SBP_MIN = 40
SBP_MAX = 260
DBP_MIN = 20
DBP_MAX = 200
SPO2_MIN = Decimal("50.0")
SPO2_MAX = Decimal("100.0")
WEIGHT_MIN = Decimal("0.5")
WEIGHT_MAX = Decimal("400.0")
HEIGHT_MIN = Decimal("30.0")
HEIGHT_MAX = Decimal("260.0")
PAIN_MIN = 0
PAIN_MAX = 10



class VitalSignCreateSchema(BaseModel):
    visit_id: int
    recorded_by_staff_id: Optional[int] = None
    temperature_celsius: Optional[Decimal] = None
    pulse_rate: Optional[int] = None
    respiratory_rate: Optional[int] = None
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    oxygen_saturation: Optional[Decimal] = None
    weight_kg: Optional[Decimal] = None
    height_cm: Optional[Decimal] = None
    bmi: Optional[Decimal] = None
    pain_score: Optional[int] = None

    @field_validator("temperature_celsius")
    @classmethod
    def validate_temperature(cls, v):
        if v is None:
            return v
        if v < TEMPERATURE_MIN or v > TEMPERATURE_MAX:
            raise ValueError(f"temperature_celsius must be between {TEMPERATURE_MIN} and {TEMPERATURE_MAX}.")
        return v

    @field_validator("pulse_rate")
    @classmethod
    def validate_pulse(cls, v):
        if v is None:
            return v
        if v < PULSE_MIN or v > PULSE_MAX:
            raise ValueError(f"pulse_rate must be between {PULSE_MIN} and {PULSE_MAX}.")
        return v

    @field_validator("respiratory_rate")
    @classmethod
    def validate_resp(cls, v):
        if v is None:
            return v
        if v < RESP_MIN or v > RESP_MAX:
            raise ValueError(f"respiratory_rate must be between {RESP_MIN} and {RESP_MAX}.")
        return v

    @field_validator("systolic_bp")
    @classmethod
    def validate_sbp(cls, v):
        if v is None:
            return v
        if v < SBP_MIN or v > SBP_MAX:
            raise ValueError(f"systolic_bp must be between {SBP_MIN} and {SBP_MAX}.")
        return v

    @field_validator("diastolic_bp")
    @classmethod
    def validate_dbp(cls, v):
        if v is None:
            return v
        if v < DBP_MIN or v > DBP_MAX:
            raise ValueError(f"diastolic_bp must be between {DBP_MIN} and {DBP_MAX}.")
        return v

    @field_validator("oxygen_saturation")
    @classmethod
    def validate_spo2(cls, v):
        if v is None:
            return v
        if v < SPO2_MIN or v > SPO2_MAX:
            raise ValueError(f"oxygen_saturation must be between {SPO2_MIN} and {SPO2_MAX}.")
        return v

    @field_validator("weight_kg")
    @classmethod
    def validate_weight(cls, v):
        if v is None:
            return v
        if v < WEIGHT_MIN or v > WEIGHT_MAX:
            raise ValueError(f"weight_kg must be between {WEIGHT_MIN} and {WEIGHT_MAX}.")
        return v

    @field_validator("height_cm")
    @classmethod
    def validate_height(cls, v):
        if v is None:
            return v
        if v < HEIGHT_MIN or v > HEIGHT_MAX:
            raise ValueError(f"height_cm must be between {HEIGHT_MIN} and {HEIGHT_MAX}.")
        return v

    @field_validator("pain_score")
    @classmethod
    def validate_pain(cls, v):
        if v is None:
            return v
        if v < PAIN_MIN or v > PAIN_MAX:
            raise ValueError(f"pain_score must be between {PAIN_MIN} and {PAIN_MAX}.")
        return v

    @model_validator(mode="after")
    def validate_bp_relationship(self):
        if self.systolic_bp is not None and self.diastolic_bp is not None:
            if self.diastolic_bp >= self.systolic_bp:
                raise ValueError("diastolic_bp must be less than systolic_bp.")
        return self


class VitalSignReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    recorded_by_staff_id: Optional[int] = None
    temperature_celsius: Optional[Decimal] = None
    pulse_rate: Optional[int] = None
    respiratory_rate: Optional[int] = None
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    oxygen_saturation: Optional[Decimal] = None
    weight_kg: Optional[Decimal] = None
    height_cm: Optional[Decimal] = None
    bmi: Optional[Decimal] = None
    pain_score: Optional[int] = None
    recorded_at: datetime
    created_at: Optional[datetime] = None


class VitalSignListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Vital signs fetched successfully."
    items: list[VitalSignReadSchema]
    count: int
    meta: dict


class VitalSignActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    vital_sign: VitalSignReadSchema
