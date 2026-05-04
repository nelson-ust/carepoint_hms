# app/schemas/patient_portal_schema.py
from __future__ import annotations

"""
Pydantic schemas for the patient-portal OTP login flow.

The flow is two-step:
1. ``PatientPortalRequestOtpSchema`` — patient identifies themselves by
   email, phone or hospital number; a 5-digit OTP is generated, stored
   hashed, and dispatched via email or SMS.
2. ``PatientPortalVerifyOtpSchema``  — the patient submits the OTP they
   received; on success a JWT pair (access + refresh) is issued and the
   patient is granted portal access.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================
# REQUEST OTP
# ============================================================


class PatientPortalRequestOtpSchema(BaseModel):
    """Step 1 — request that an OTP be sent."""

    identifier: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description=(
            "Email address, phone number, or hospital (MRN) number used to "
            "identify the patient."
        ),
    )
    channel: Optional[str] = Field(
        None,
        description=(
            "Optional override of the delivery channel: EMAIL or SMS. "
            "When omitted the service infers the channel from the identifier."
        ),
    )

    @field_validator("identifier")
    @classmethod
    def normalize_identifier(cls, v: str) -> str:
        return v.strip()

    @field_validator("channel")
    @classmethod
    def normalize_channel(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        n = v.strip().upper()
        if n not in {"EMAIL", "SMS"}:
            raise ValueError("channel must be EMAIL or SMS.")
        return n


# ============================================================
# VERIFY OTP
# ============================================================


class PatientPortalVerifyOtpSchema(BaseModel):
    """Step 2 — verify the OTP and exchange for a JWT."""

    otp_id: int = Field(..., description="OTP challenge id returned by request-otp.")
    otp_code: str = Field(..., min_length=4, max_length=10)

    @field_validator("otp_code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        normalized = v.strip()
        if not normalized.isdigit():
            raise ValueError("otp_code must be numeric.")
        return normalized


# ============================================================
# RESEND OTP
# ============================================================


class PatientPortalResendOtpSchema(BaseModel):
    """Resend the active OTP to the original channel + destination."""

    otp_id: int


# ============================================================
# RESPONSES
# ============================================================


class PatientPortalRequestOtpResponseSchema(BaseModel):
    """
    Response for the OTP-request step.

    Fields are intentionally minimal — we never echo the OTP itself or
    even the full destination back to the client. The ``masked_destination``
    field is a hint for the UI ("Code sent to ne****@live.com") so the
    patient can confirm the right address was used without leaking the
    full PII.
    """

    success: bool = True
    message: str = "OTP dispatched."
    otp_id: int
    channel: str
    masked_destination: str
    expires_in_seconds: int


class PortalTokenSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PatientPortalLoginResponseSchema(BaseModel):
    """Response for a successful OTP verification."""

    success: bool = True
    message: str = "Patient portal access granted."
    tokens: PortalTokenSchema
    patient_id: int
    user_id: int
    hospital_number: str
    full_name: str


class PatientPortalErrorResponseSchema(BaseModel):
    success: bool = False
    message: str
    error_code: Optional[str] = None
    detail: Optional[dict] = None
