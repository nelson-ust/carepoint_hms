# app/schemas/appointment_schemas.py
from __future__ import annotations

"""
Pydantic schemas for the appointment scheduling module (Stage 7).

Exposes the request/response shapes used by:
- ``app/services/appointment_service.py``
- ``app/api/v1/endpoints/appointment_routes.py``
- ``app/services/patient_registration_service.py`` (when a patient checks
  in against an existing appointment)

Lifecycle reflected in these schemas:
    SCHEDULED -> ARRIVED -> IN_PROGRESS -> COMPLETED
                      \\-> MISSED
                      \\-> CANCELLED
                      \\-> RESCHEDULED  (creates a new SCHEDULED row)
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ============================================================
# REQUESTS
# ============================================================


class AppointmentCreateSchema(BaseModel):
    """Book a new appointment."""

    patient_id: int
    facility_id: Optional[int] = Field(
        None,
        description="Multi-branch scoping. If omitted, inferred from the SDP if possible.",
    )
    service_delivery_point_id: Optional[int] = None
    staff_profile_id: Optional[int] = Field(
        None,
        description="Optional clinician booking. Used by double-booking checks.",
    )
    scheduled_start_at: datetime
    scheduled_end_at: Optional[datetime] = None
    reason: Optional[str] = Field(None, max_length=4000)


class AppointmentRescheduleSchema(BaseModel):
    """Reschedule an existing appointment to a new slot."""

    new_scheduled_start_at: datetime
    new_scheduled_end_at: Optional[datetime] = None
    reason: Optional[str] = Field(None, max_length=2000)


class AppointmentCancelSchema(BaseModel):
    """Cancel an appointment with an optional reason."""

    reason: Optional[str] = Field(None, max_length=2000)


class AppointmentCheckInSchema(BaseModel):
    """
    Mark an appointment as ARRIVED and (optionally) initiate the visit.

    When ``initiate_visit`` is True, the service hands off to
    :class:`VisitService.initiate_visit` so the patient is queued at the
    appropriate service-delivery-point in one round-trip.
    """

    initiate_visit: bool = True
    visit_flow_template_id: Optional[int] = None
    create_first_flow_step: bool = True
    create_queue_ticket: bool = True
    fast_track: bool = False
    use_appointment_service_point: bool = True
    visit_reason: Optional[str] = Field(None, max_length=2000)


class AppointmentNoShowSchema(BaseModel):
    """Mark an appointment as MISSED (no-show)."""

    note: Optional[str] = Field(None, max_length=2000)


# ============================================================
# RESPONSES
# ============================================================


class AppointmentReadSchema(BaseModel):
    """Detailed appointment record returned by API endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    appointment_code: str
    patient_id: int
    facility_id: Optional[int] = None
    service_delivery_point_id: Optional[int] = None
    staff_profile_id: Optional[int] = None
    scheduled_start_at: datetime
    scheduled_end_at: Optional[datetime] = None
    reason: Optional[str] = None
    status: str
    
    # Demographic & Context Details (Populated via model_validator)
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    staff_name: Optional[str] = None
    service_delivery_point_name: Optional[str] = None
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_names(cls, data: Any) -> Any:
        if hasattr(data, "patient") and data.patient:
            data.patient_name = f"{data.patient.first_name} {data.patient.last_name}"
            data.patient_phone = data.patient.phone_number
        
        if hasattr(data, "staff_profile") and data.staff_profile:
            # Assumes StaffProfile has a user relationship with name fields
            user = getattr(data.staff_profile, "user", None)
            if user:
                data.staff_name = f"{user.first_name} {user.last_name}"
        
        if hasattr(data, "service_delivery_point") and data.service_delivery_point:
            data.service_delivery_point_name = data.service_delivery_point.name
            
        return data


class AppointmentListResponseSchema(BaseModel):
    """Paginated appointment list."""

    success: bool = True
    message: str = "Appointments fetched successfully."
    items: list[AppointmentReadSchema]
    count: int
    meta: dict


class AppointmentActionResponseSchema(BaseModel):
    """Single-appointment action response wrapper."""

    success: bool = True
    message: str
    appointment: AppointmentReadSchema


class AppointmentCheckInResponseSchema(BaseModel):
    """
    Check-in response. Includes the visit + queue echo block when the visit
    was initiated as part of the same request.
    """

    success: bool = True
    message: str
    appointment: AppointmentReadSchema
    visit_id: Optional[int] = None
    visit_code: Optional[str] = None
    queue_ticket_id: Optional[int] = None
    queue_number: Optional[str] = None
    queue_position: Optional[int] = None
    first_service_delivery_point_id: Optional[int] = None


class AppointmentAvailabilityResponseSchema(BaseModel):
    """Response for an availability lookup."""

    success: bool = True
    message: str = "Availability fetched successfully."
    available: bool
    conflicts: list[AppointmentReadSchema] = Field(default_factory=list)
