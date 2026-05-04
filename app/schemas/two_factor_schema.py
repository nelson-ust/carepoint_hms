# app/schemas/two_factor_schema.py
from __future__ import annotations

"""
app.schemas.two_factor_schema

Pydantic schemas for the dedicated two-factor administration module.

The user-facing 2FA flows live in app.schemas.auth_schemas (login 2FA,
email/phone verification, OTP setup). This module focuses on admin-facing
operations such as listing challenges, expiring challenges, and reviewing
challenge history.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TwoFactorChallengeReadSchema(BaseModel):
    """
    Detailed two-factor challenge representation.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    challenge_type: str
    purpose: str
    destination: Optional[str] = None
    attempt_count: int = 0
    max_attempts: int = 5
    is_verified: bool = False
    verified_at: Optional[datetime] = None
    expires_at: datetime
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TwoFactorChallengeListResponseSchema(BaseModel):
    """
    Paginated 2FA challenge list response.
    """

    success: bool = True
    message: str = "Two-factor challenges fetched successfully."
    items: list[TwoFactorChallengeReadSchema]
    count: int
    meta: dict


class TwoFactorChallengeActionResponseSchema(BaseModel):
    """
    Generic action response wrapping the affected challenge.
    """

    success: bool = True
    message: str
    challenge: TwoFactorChallengeReadSchema


class TwoFactorPolicyUpdateSchema(BaseModel):
    """
    Schema for admin-driven 2FA policy updates on a target user.
    """

    enable_two_factor: bool = Field(..., description="Master 2FA toggle.")
    reason: Optional[str] = Field(None, max_length=500)


class TwoFactorPolicyResponseSchema(BaseModel):
    """
    Response schema after a 2FA policy change.
    """

    success: bool = True
    message: str
    user_id: int
    is_two_factor_enabled: bool
