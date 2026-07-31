from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from app.core.enums import FacilityType, FacilityStatus

# --- FACILITY NETWORK SCHEMAS ---

class FacilityNetworkBase(BaseModel):
    """
    Base schema for hospital networks/chains.
    """
    name: str = Field(..., description="Name of the hospital network")
    code: str = Field(..., description="Unique identifying code for the network")
    description: Optional[str] = Field(None, description="Detailed description of the network")

class FacilityNetworkCreate(FacilityNetworkBase):
    """
    Schema for creating a new hospital network.
    """
    head_office_facility_id: Optional[int] = Field(None, description="Optional ID of the facility acting as head office")

class FacilityNetworkUpdate(BaseModel):
    """
    Schema for updating an existing hospital network.
    """
    name: Optional[str] = None
    description: Optional[str] = None
    head_office_facility_id: Optional[int] = None

class FacilityNetworkRead(FacilityNetworkBase):
    """
    Schema for reading hospital network details.
    """
    id: int
    head_office_facility_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# --- FACILITY SERVICE AREA SCHEMAS ---

class FacilityServiceAreaBase(BaseModel):
    """
    Base schema for facility catchment/service areas.
    """
    area_name: str = Field(..., description="Name of the catchment area")
    region_code: Optional[str] = Field(None, description="Regional code for reporting purposes")
    notes: Optional[str] = Field(None, description="Additional notes about the service area")

class FacilityServiceAreaCreate(FacilityServiceAreaBase):
    """
    Schema for creating a new service area for a facility.
    """
    facility_id: int = Field(..., description="ID of the facility this area belongs to")

class FacilityServiceAreaUpdate(BaseModel):
    """
    Schema for updating an existing service area.
    """
    area_name: Optional[str] = None
    region_code: Optional[str] = None
    notes: Optional[str] = None

class FacilityServiceAreaRead(FacilityServiceAreaBase):
    """
    Schema for reading service area details.
    """
    id: int
    facility_id: int

    model_config = ConfigDict(from_attributes=True)


# --- FACILITY SCHEMAS ---

class FacilityBase(BaseModel):
    """
    Base schema for hospital facilities/branches.
    """
    code: str = Field(..., description="Unique code for the facility")
    name: str = Field(..., description="Official name of the facility")
    facility_type: FacilityType = Field(FacilityType.MAIN_HOSPITAL, description="Type of facility")
    status: FacilityStatus = Field(FacilityStatus.ACTIVE, description="Current operational status")
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
    """
    Schema for creating a new facility.
    """
    network_id: Optional[int] = Field(None, description="ID of the network this facility belongs to")
    parent_facility_id: Optional[int] = Field(None, description="ID of the parent facility if this is a sub-branch")

class FacilityUpdate(BaseModel):
    """
    Schema for updating an existing facility.

    Covers every operator-editable attribute so the management UI can present a
    complete edit form. ``code`` is intentionally omitted — it is the facility's
    immutable business identifier.
    """
    name: Optional[str] = None
    facility_type: Optional[FacilityType] = None
    status: Optional[FacilityStatus] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    timezone: Optional[str] = None
    network_id: Optional[int] = None
    parent_facility_id: Optional[int] = None

class FacilityRead(FacilityBase):
    """
    Schema for reading facility details, including related network and service areas.
    """
    id: int
    network_id: Optional[int] = None
    parent_facility_id: Optional[int] = None
    
    # Nested relationships
    network: Optional[FacilityNetworkRead] = None
    service_areas: List[FacilityServiceAreaRead] = []

    model_config = ConfigDict(from_attributes=True)
