# app/schemas/patient_portal_schemas.py
from __future__ import annotations

from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, ConfigDict

from app.schemas.patient_schemas import PatientReadSchema
from app.schemas.membership_card_schemas import MembershipCardRead, MembershipCardTransactionRead
from app.schemas.notification_schema import NotificationReadSchema
from app.schemas.lab_result_schema import LabResultReadSchema


class PatientPortalProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient: PatientReadSchema
    username: str
    email: str


class PatientPortalDashboard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient: PatientReadSchema
    card: Optional[MembershipCardRead] = None
    wallet_balance: Decimal = Decimal("0.00")
    recent_transactions: List[MembershipCardTransactionRead] = []
    recent_lab_results: List[LabResultReadSchema] = []
    unread_notifications_count: int = 0


class PatientFundCardRequest(BaseModel):
    amount: Decimal


class PatientPortalOTPRequest(BaseModel):
    identifier: str  # email or phone
    delivery_method: str = "EMAIL"  # EMAIL or SMS


class PatientPortalOTPVerify(BaseModel):
    identifier: str
    otp_code: str
    challenge_reference: Optional[str] = None
