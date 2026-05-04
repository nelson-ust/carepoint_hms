from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from app.core.enums import FacilityType, FacilityStatus

class FacilityBase(BaseModel):
    code: str
    name: str
    facility_type: FacilityType = FacilityType.MAIN_HOSPITAL
    status: FacilityStatus = FacilityStatus.ACTIVE
    phone_number: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    timezone: Optional[str] = "Africa/Lagos"

class FacilityCreate(FacilityBase):
    network_id: Optional[int] = None
    parent_facility_id: Optional[int] = None

class FacilityUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[FacilityStatus] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    address_line_1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None

class FacilityRead(FacilityBase):
    id: int
    network_id: Optional[int] = None
    parent_facility_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
