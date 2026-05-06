from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

# ── Loyalty Program Schemas ──────────────────────────────────────────

class LoyaltyProgramBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    points_per_currency_unit: Optional[Decimal] = None
    minimum_redemption_points: Optional[Decimal] = None
    is_auto_enroll: bool = False

class LoyaltyProgramCreateSchema(LoyaltyProgramBase):
    pass

class LoyaltyProgramReadSchema(LoyaltyProgramBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# ── Facility Network Schemas ─────────────────────────────────────────

class FacilityNetworkBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    head_office_facility_id: Optional[int] = None

class FacilityNetworkCreateSchema(FacilityNetworkBase):
    pass

class FacilityNetworkReadSchema(FacilityNetworkBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
