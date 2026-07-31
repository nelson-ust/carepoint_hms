# app/schemas/patient_loyalty_schemas.py
"""
Schemas for the patient-facing loyalty endpoints (points balance, transaction
history, and earn/redeem actions) consumed by the Patient Loyalty page.

These sit on top of the existing PatientLoyalty / LoyaltyTransaction models but
expose a flat, UI-friendly shape (integer points, ``reason``/``created_at``
aliases) rather than the richer internal records.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PatientPointsRead(BaseModel):
    patient_id: int
    total_points: int = 0
    last_updated_at: Optional[datetime] = None


class LoyaltyTransactionRead(BaseModel):
    id: int
    patient_id: int
    points: int
    transaction_type: str
    reason: str = ""
    created_at: Optional[datetime] = None


class LoyaltyHistoryResponse(BaseModel):
    success: bool = True
    message: str = "Loyalty history fetched successfully."
    items: List[LoyaltyTransactionRead] = Field(default_factory=list)
    count: int = 0
    meta: dict = Field(default_factory=dict)


class PointsMutationRequest(BaseModel):
    patient_id: int
    points: int = Field(..., gt=0, description="Whole number of points to award or redeem.")
    reason: str = Field("", max_length=500)


class PointsMutationResponse(BaseModel):
    success: bool = True
    balance: int = 0
    message: str = ""
