# app/schemas/ambulance_schemas.py
from __future__ import annotations

"""
Pydantic schemas for the ambulance / emergency-transport module (Stage 15).

Covers the full operational surface:

- ``Ambulance``                — vehicle master data with operational status
- ``AmbulanceDriver``          — driver assignment + license tracking
- ``AmbulanceEquipment``       — kit + expiry tracking
- ``AmbulanceMaintenance``     — maintenance log (scheduled / in-progress / completed)
- ``AmbulanceDispatch``        — dispatch lifecycle from request → completion
- ``AmbulanceIncidentReport``  — incidents during/after a dispatch
- Readiness                    — derived state: AVAILABLE + has primary driver +
                                 no critical equipment expired + no in-progress maintenance
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================
# AMBULANCE
# ============================================================


class AmbulanceCreateSchema(BaseModel):
    """Add a new ambulance to the fleet."""

    code: str = Field(..., min_length=1, max_length=100)
    plate_number: str = Field(..., min_length=1, max_length=100)
    model: Optional[str] = Field(None, max_length=150)
    manufacturer: Optional[str] = Field(None, max_length=150)
    year_of_manufacture: Optional[int] = Field(None, ge=1900, le=2100)
    color: Optional[str] = Field(None, max_length=50)
    current_mileage: Optional[Decimal] = None
    notes: Optional[str] = None

    @field_validator("code", "plate_number")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "")


class AmbulanceUpdateSchema(BaseModel):
    """Edit ambulance master data fields."""

    model: Optional[str] = Field(None, max_length=150)
    manufacturer: Optional[str] = Field(None, max_length=150)
    year_of_manufacture: Optional[int] = Field(None, ge=1900, le=2100)
    color: Optional[str] = Field(None, max_length=50)
    current_mileage: Optional[Decimal] = None
    notes: Optional[str] = None


class AmbulanceStatusUpdateSchema(BaseModel):
    """Change operational status (AVAILABLE / DISPATCHED / IN_TRANSIT / OUT_OF_SERVICE / UNDER_MAINTENANCE)."""

    new_status: str
    reason: Optional[str] = Field(None, max_length=2000)

    @field_validator("new_status")
    @classmethod
    def normalize_status(cls, v: str) -> str:
        normalized = v.strip().upper()
        allowed = {"AVAILABLE", "DISPATCHED", "IN_TRANSIT", "OUT_OF_SERVICE", "UNDER_MAINTENANCE"}
        if normalized not in allowed:
            raise ValueError(f"new_status must be one of {sorted(allowed)}.")
        return normalized


class AmbulanceReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    plate_number: str
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    year_of_manufacture: Optional[int] = None
    color: Optional[str] = None
    status: str
    current_mileage: Optional[Decimal] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AmbulanceListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Ambulances fetched successfully."
    items: list[AmbulanceReadSchema]
    count: int
    meta: dict


class AmbulanceActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    ambulance: AmbulanceReadSchema


class AmbulanceReadinessResponseSchema(BaseModel):
    """
    Readiness summary for an ambulance.

    ``ready=True`` requires:
    - status == AVAILABLE
    - at least one assigned driver with non-expired license
    - no equipment expired (best-effort, only when expiry_date is set)
    - no maintenance in IN_PROGRESS state
    """

    success: bool = True
    message: str = "Readiness computed successfully."
    ambulance_id: int
    ready: bool
    reasons: list[str] = Field(default_factory=list)
    primary_driver_id: Optional[int] = None
    expired_equipment_ids: list[int] = Field(default_factory=list)
    open_maintenance_ids: list[int] = Field(default_factory=list)


# ============================================================
# DRIVER
# ============================================================


class AmbulanceDriverCreateSchema(BaseModel):
    """Register a driver and (optionally) assign them to an ambulance."""

    staff_profile_id: int
    ambulance_id: Optional[int] = None
    driver_license_no: str = Field(..., min_length=1, max_length=100)
    license_expiry_date: Optional[date] = None
    is_primary_driver: bool = False
    emergency_response_certified: bool = False
    notes: Optional[str] = None

    @field_validator("driver_license_no")
    @classmethod
    def normalize_license(cls, v: str) -> str:
        return v.strip().upper()


class AmbulanceDriverUpdateSchema(BaseModel):
    license_expiry_date: Optional[date] = None
    is_primary_driver: Optional[bool] = None
    emergency_response_certified: Optional[bool] = None
    ambulance_id: Optional[int] = None
    notes: Optional[str] = None


class AmbulanceDriverReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    staff_profile_id: int
    ambulance_id: Optional[int] = None
    driver_license_no: str
    license_expiry_date: Optional[date] = None
    is_primary_driver: bool = False
    emergency_response_certified: bool = False
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AmbulanceDriverListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Drivers fetched successfully."
    items: list[AmbulanceDriverReadSchema]
    count: int
    meta: dict


class AmbulanceDriverActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    driver: AmbulanceDriverReadSchema


# ============================================================
# EQUIPMENT
# ============================================================


class AmbulanceEquipmentCreateSchema(BaseModel):
    ambulance_id: int
    equipment_name: str = Field(..., min_length=1, max_length=255)
    equipment_code: Optional[str] = Field(None, max_length=100)
    quantity: Decimal = Decimal("1")
    condition_status: Optional[str] = Field(None, max_length=100)
    expiry_date: Optional[date] = None
    notes: Optional[str] = None


class AmbulanceEquipmentUpdateSchema(BaseModel):
    equipment_name: Optional[str] = Field(None, min_length=1, max_length=255)
    quantity: Optional[Decimal] = None
    condition_status: Optional[str] = Field(None, max_length=100)
    expiry_date: Optional[date] = None
    notes: Optional[str] = None


class AmbulanceEquipmentReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ambulance_id: int
    equipment_name: str
    equipment_code: Optional[str] = None
    quantity: Decimal
    condition_status: Optional[str] = None
    expiry_date: Optional[date] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class AmbulanceEquipmentListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Equipment items fetched successfully."
    items: list[AmbulanceEquipmentReadSchema]
    count: int
    meta: dict


class AmbulanceEquipmentActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    equipment: AmbulanceEquipmentReadSchema


# ============================================================
# MAINTENANCE
# ============================================================


class AmbulanceMaintenanceCreateSchema(BaseModel):
    """Schedule or record a maintenance event."""

    ambulance_id: int
    maintenance_type: Optional[str] = Field(None, max_length=100)
    issue_description: Optional[str] = None
    service_provider: Optional[str] = Field(None, max_length=255)
    maintenance_date: datetime
    cost: Optional[Decimal] = None
    mileage_at_service: Optional[Decimal] = None


class AmbulanceMaintenanceUpdateSchema(BaseModel):
    """Update / progress / complete a maintenance event."""

    maintenance_status: Optional[str] = Field(None, description="SCHEDULED / IN_PROGRESS / COMPLETED / CANCELLED")
    completed_date: Optional[datetime] = None
    issue_description: Optional[str] = None
    service_provider: Optional[str] = Field(None, max_length=255)
    cost: Optional[Decimal] = None
    mileage_at_service: Optional[Decimal] = None

    @field_validator("maintenance_status")
    @classmethod
    def normalize_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip().upper()
        allowed = {"SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED"}
        if normalized not in allowed:
            raise ValueError(f"maintenance_status must be one of {sorted(allowed)}.")
        return normalized


class AmbulanceMaintenanceReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ambulance_id: int
    maintenance_status: str
    maintenance_type: Optional[str] = None
    issue_description: Optional[str] = None
    service_provider: Optional[str] = None
    maintenance_date: datetime
    completed_date: Optional[datetime] = None
    cost: Optional[Decimal] = None
    mileage_at_service: Optional[Decimal] = None


class AmbulanceMaintenanceListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Maintenance records fetched successfully."
    items: list[AmbulanceMaintenanceReadSchema]
    count: int
    meta: dict


class AmbulanceMaintenanceActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    maintenance: AmbulanceMaintenanceReadSchema


# ============================================================
# DISPATCH
# ============================================================


class AmbulanceDispatchCreateSchema(BaseModel):
    """
    Open a new dispatch ticket.

    Either ``ambulance_id`` or ``driver_id`` may be omitted at request time
    (status PENDING). Use the assign / depart / arrive / complete endpoints
    to walk the lifecycle.
    """

    ambulance_id: Optional[int] = None
    driver_id: Optional[int] = None
    patient_id: Optional[int] = None
    visit_id: Optional[int] = None
    pickup_location: Optional[str] = None
    destination_location: Optional[str] = None
    incident_description: Optional[str] = None
    requested_at: Optional[datetime] = Field(None, description="Defaults to now (UTC).")


class AmbulanceDispatchAssignSchema(BaseModel):
    ambulance_id: int
    driver_id: Optional[int] = None
    note: Optional[str] = None


class AmbulanceDispatchTransitionSchema(BaseModel):
    """Generic transition payload used by depart / arrive / complete / cancel."""

    note: Optional[str] = None


class AmbulanceDispatchReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dispatch_no: str
    ambulance_id: int
    driver_id: Optional[int] = None
    patient_id: Optional[int] = None
    visit_id: Optional[int] = None
    dispatch_status: str
    pickup_location: Optional[str] = None
    destination_location: Optional[str] = None
    incident_description: Optional[str] = None
    requested_at: datetime
    assigned_at: Optional[datetime] = None
    departed_at: Optional[datetime] = None
    arrived_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class AmbulanceDispatchListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Dispatches fetched successfully."
    items: list[AmbulanceDispatchReadSchema]
    count: int
    meta: dict


class AmbulanceDispatchActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    dispatch: AmbulanceDispatchReadSchema


# ============================================================
# INCIDENT REPORT
# ============================================================


class AmbulanceIncidentReportCreateSchema(BaseModel):
    dispatch_id: int
    reported_by_staff_id: Optional[int] = None
    severity: str = Field("MEDIUM")
    incident_date: Optional[datetime] = None
    summary: str = Field(..., min_length=1)
    action_taken: Optional[str] = None
    follow_up_required: bool = False

    @field_validator("severity")
    @classmethod
    def normalize_severity(cls, v: str) -> str:
        normalized = v.strip().upper()
        allowed = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError(f"severity must be one of {sorted(allowed)}.")
        return normalized


class AmbulanceIncidentReportReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dispatch_id: int
    reported_by_staff_id: Optional[int] = None
    severity: str
    incident_date: datetime
    summary: str
    action_taken: Optional[str] = None
    follow_up_required: bool = False
    created_at: Optional[datetime] = None


class AmbulanceIncidentReportListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Incident reports fetched successfully."
    items: list[AmbulanceIncidentReportReadSchema]
    count: int
    meta: dict


class AmbulanceIncidentReportActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    incident: AmbulanceIncidentReportReadSchema
