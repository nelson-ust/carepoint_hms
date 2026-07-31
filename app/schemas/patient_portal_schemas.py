# app/schemas/patient_portal_schemas.py
from __future__ import annotations

from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.patient_schemas import PatientReadSchema
from app.schemas.membership_card_schemas import MembershipCardRead, MembershipCardTransactionRead
from app.schemas.notification_schema import NotificationReadSchema
from app.schemas.lab_result_schema import LabResultReadSchema
from app.schemas.appointment_schemas import AppointmentReadSchema


class PatientPortalProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient: PatientReadSchema
    username: str
    email: str


class PortalProfileUpdateSchema(BaseModel):
    """
    Fields a patient may self-edit from the portal profile page.

    Deliberately restricted: identity/clinical fields (name, DOB, gender,
    blood group, MRN, etc.) are NOT editable here — only contact details, the
    national ID, and emergency / next-of-kin information.
    """

    # Personal details
    national_identifier: Optional[str] = Field(None, max_length=100)
    national_identifier_type: Optional[str] = Field(None, max_length=50)

    # Contact information
    phone_number: Optional[str] = Field(None, max_length=30)
    alternate_phone_number: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = None

    # Emergency contact & next of kin
    emergency_contact_name: Optional[str] = Field(None, max_length=200)
    emergency_contact_phone: Optional[str] = Field(None, max_length=30)
    emergency_contact_relationship: Optional[str] = Field(None, max_length=100)
    next_of_kin_name: Optional[str] = Field(None, max_length=200)
    next_of_kin_phone: Optional[str] = Field(None, max_length=30)
    next_of_kin_relationship: Optional[str] = Field(None, max_length=100)


class PatientPortalDashboard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient: PatientReadSchema
    card: Optional[MembershipCardRead] = None
    wallet_balance: Decimal = Decimal("0.00")
    recent_transactions: List[MembershipCardTransactionRead] = []
    recent_lab_results: List[LabResultReadSchema] = []
    unread_notifications_count: int = 0
    recent_notifications: List[NotificationReadSchema] = []


class PatientPortalAppointments(BaseModel):
    """
    The patient's complete appointment history for the portal, arranged so the
    UI can foreground the *current* (next upcoming) appointment while still
    giving access to everything ever scheduled.

    ``upcoming`` holds future, still-active appointments sorted soonest-first;
    ``next_appointment`` is simply the first of those (the one to emphasise).
    ``past`` holds everything else — completed, cancelled, missed, or already
    elapsed — sorted most-recent-first.
    """

    model_config = ConfigDict(from_attributes=True)

    total: int = 0
    upcoming_count: int = 0
    past_count: int = 0
    next_appointment: Optional[AppointmentReadSchema] = None
    upcoming: List[AppointmentReadSchema] = []
    past: List[AppointmentReadSchema] = []


class PatientPortalBranding(BaseModel):
    """
    Public branding for a hospital's patient portal — hospital name, logo and
    theme colours. Served unauthenticated (resolved from the X-Tenant-Code
    header) so the portal can render the hospital's identity on every page.
    """

    hospital_name: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None


class PatientFundCardRequest(BaseModel):
    amount: Decimal


class PatientPortalOTPRequest(BaseModel):
    identifier: str  # email or phone
    delivery_method: str = "EMAIL"  # EMAIL or SMS


class PatientPortalOTPVerify(BaseModel):
    identifier: str
    otp_code: str
    challenge_reference: Optional[str] = None
