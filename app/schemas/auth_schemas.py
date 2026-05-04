from __future__ import annotations

"""
app.schemas.auth_schemas

Pydantic schemas for authentication, authorization-adjacent identity payloads,
password management, OTP verification, and optional two-factor authentication.

Purpose
-------
This module defines request and response schemas for:

- login
- access/refresh token responses
- refresh token exchange
- logout
- password change
- forgot password
- reset password
- OTP verification
- resend OTP
- optional two-factor authentication setup and verification
- authenticated user profile payloads

Design goals
------------
- provide clear request/response contracts for auth endpoints
- support both normal login and login with optional 2FA
- support onboarding verification flows
- support reusable action response payloads
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


# ============================================================
# SHARED / LITE SCHEMAS
# ============================================================

class AuthUserLiteSchema(BaseModel):
    """
    Lightweight authenticated user representation.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    status: Optional[str] = None
    is_superuser: bool = False
    is_email_verified: bool = False
    is_phone_verified: bool = False
    is_two_factor_enabled: bool = False


class AuthRoleLiteSchema(BaseModel):
    """
    Lightweight role representation for auth/profile responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: Optional[str] = None
    description: Optional[str] = None


# ============================================================
# TOKEN SCHEMAS
# ============================================================

class TokenSchema(BaseModel):
    """
    Standard token response schema.
    """

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    refresh_expires_in: Optional[int] = None
    two_factor_required: bool = False
    two_factor_verified: bool = False


class AccessTokenSchema(BaseModel):
    """
    Access-token-only response schema.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None


class RefreshTokenRequestSchema(BaseModel):
    """
    Request schema for refreshing an access token.
    """

    refresh_token: str = Field(..., min_length=1)

    @field_validator("refresh_token")
    @classmethod
    def normalize_refresh_token(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("refresh_token cannot be empty.")
        return normalized


# ============================================================
# LOGIN / LOGOUT SCHEMAS
# ============================================================

class LoginSchema(BaseModel):
    """
    Login request schema.

    Supports login by username, email, or other configured identifier.
    """

    identifier: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)
    remember_me: bool = False

    @field_validator("identifier")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("identifier cannot be empty.")
        return normalized

    @field_validator("password")
    @classmethod
    def normalize_password(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("password cannot be empty.")
        return value


class LoginSuccessSchema(BaseModel):
    """
    Successful login response schema.
    """

    success: bool = True
    message: str = "Login successful."
    user: AuthUserLiteSchema
    tokens: TokenSchema


class LoginPendingTwoFactorSchema(BaseModel):
    """
    Login response schema when 2FA verification is still required.
    """

    success: bool = True
    message: str = "Login successful. Two-factor verification is required."
    user_id: int
    identifier: Optional[str] = None
    two_factor_required: bool = True
    two_factor_method: Optional[str] = None
    challenge_reference: Optional[str] = None


class LogoutRequestSchema(BaseModel):
    """
    Logout request schema.

    Useful when revoking refresh token / session.
    """

    refresh_token: Optional[str] = None
    all_sessions: bool = False

    @field_validator("refresh_token")
    @classmethod
    def normalize_optional_refresh_token(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class LogoutResponseSchema(BaseModel):
    """
    Logout response schema.
    """

    success: bool = True
    message: str = "Logout successful."


# ============================================================
# PASSWORD MANAGEMENT SCHEMAS
# ============================================================

class ChangePasswordSchema(BaseModel):
    """
    Authenticated password change request schema.
    """

    current_password: str = Field(..., min_length=1, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=255)
    confirm_new_password: str = Field(..., min_length=8, max_length=255)

    @field_validator("current_password", "new_password", "confirm_new_password")
    @classmethod
    def validate_password_fields(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Password fields cannot be empty.")
        return value

    @model_validator(mode="after")
    def validate_password_match(self):
        if self.new_password != self.confirm_new_password:
            raise ValueError("New password and confirmation do not match.")
        return self


class ForgotPasswordSchema(BaseModel):
    """
    Forgot-password request schema.

    Supports requesting a password reset by email or other login identifier.
    """

    identifier: str = Field(..., min_length=1, max_length=255)

    @field_validator("identifier")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("identifier cannot be empty.")
        return normalized


class ResetPasswordSchema(BaseModel):
    """
    Password reset completion schema.
    """

    reset_token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=255)
    confirm_new_password: str = Field(..., min_length=8, max_length=255)

    @field_validator("reset_token", "new_password", "confirm_new_password")
    @classmethod
    def normalize_required_fields(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Required field cannot be empty.")
        return value

    @model_validator(mode="after")
    def validate_password_match(self):
        if self.new_password != self.confirm_new_password:
            raise ValueError("New password and confirmation do not match.")
        return self


class PasswordActionResponseSchema(BaseModel):
    """
    Generic response schema for password-related actions.
    """

    success: bool = True
    message: str


# ============================================================
# OTP / 2FA SCHEMAS
# ============================================================

class OTPVerifySchema(BaseModel):
    """
    OTP verification request schema.

    Can be used for:
    - login 2FA verification
    - onboarding verification
    - password-reset verification
    """

    user_id: Optional[int] = None
    identifier: Optional[str] = None
    otp_code: str = Field(..., min_length=1, max_length=20)
    challenge_reference: Optional[str] = None
    purpose: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Examples: LOGIN_2FA, EMAIL_VERIFICATION, PHONE_VERIFICATION, PASSWORD_RESET.",
    )

    @field_validator("identifier", "challenge_reference", "purpose")
    @classmethod
    def normalize_optional_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("otp_code")
    @classmethod
    def normalize_otp_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("otp_code cannot be empty.")
        return normalized

    @model_validator(mode="after")
    def validate_identifier_or_user(self):
        if self.user_id is None and self.identifier is None and self.challenge_reference is None:
            raise ValueError(
                "At least one of user_id, identifier, or challenge_reference must be provided."
            )
        return self


class OTPResendSchema(BaseModel):
    """
    OTP resend request schema.
    """

    user_id: Optional[int] = None
    identifier: Optional[str] = None
    purpose: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Examples: LOGIN_2FA, EMAIL_VERIFICATION, PHONE_VERIFICATION, PASSWORD_RESET.",
    )
    delivery_method: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Examples: EMAIL, SMS, WHATSAPP, AUTHENTICATOR.",
    )

    @field_validator("identifier", "purpose", "delivery_method")
    @classmethod
    def normalize_optional_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None

    @model_validator(mode="after")
    def validate_identifier_or_user(self):
        if self.user_id is None and self.identifier is None:
            raise ValueError("Either user_id or identifier must be provided.")
        return self


class TwoFactorSetupSchema(BaseModel):
    """
    Request schema for enabling/configuring two-factor authentication.
    """

    enable_two_factor: bool = True
    method: str = Field(..., min_length=1, max_length=50)
    enable_email: bool = False
    enable_sms: bool = False
    enable_whatsapp: bool = False
    enable_authenticator: bool = False

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("method cannot be empty.")
        return normalized

    @model_validator(mode="after")
    def validate_method_flags(self):
        if self.enable_two_factor:
            if not any(
                [
                    self.enable_email,
                    self.enable_sms,
                    self.enable_whatsapp,
                    self.enable_authenticator,
                ]
            ):
                raise ValueError(
                    "At least one two-factor delivery option must be enabled when two-factor is enabled."
                )
        return self


class TwoFactorVerifySchema(BaseModel):
    """
    Dedicated two-factor verification schema.
    """

    user_id: Optional[int] = None
    identifier: Optional[str] = None
    otp_code: str = Field(..., min_length=1, max_length=20)
    method: Optional[str] = Field(None, max_length=50)
    challenge_reference: Optional[str] = None

    @field_validator("identifier", "challenge_reference")
    @classmethod
    def normalize_optional_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("otp_code")
    @classmethod
    def normalize_otp_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("otp_code cannot be empty.")
        return normalized

    @model_validator(mode="after")
    def validate_identifier_or_user(self):
        if self.user_id is None and self.identifier is None and self.challenge_reference is None:
            raise ValueError(
                "At least one of user_id, identifier, or challenge_reference must be provided."
            )
        return self


class TwoFactorSetupResponseSchema(BaseModel):
    """
    Response schema for two-factor setup operations.
    """

    success: bool = True
    message: str
    two_factor_enabled: bool
    method: Optional[str] = None
    setup_secret: Optional[str] = None
    provisioning_uri: Optional[str] = None
    qr_code_data: Optional[str] = None


class OTPActionResponseSchema(BaseModel):
    """
    Generic response schema for OTP/verification actions.
    """

    success: bool = True
    message: str
    challenge_reference: Optional[str] = None
    delivery_method: Optional[str] = None


class OTPVerificationSuccessSchema(BaseModel):
    """
    Response schema for successful OTP / 2FA verification.

    Useful for flows that issue tokens after verification.
    """

    success: bool = True
    message: str = "Verification successful."
    verified: bool = True
    user: Optional[AuthUserLiteSchema] = None
    tokens: Optional[TokenSchema] = None


# ============================================================
# EMAIL / PHONE VERIFICATION SCHEMAS
# ============================================================

class EmailVerificationRequestSchema(BaseModel):
    """
    Request schema for email verification resend/request.
    """

    user_id: Optional[int] = None
    email: Optional[EmailStr] = None

    @model_validator(mode="after")
    def validate_user_or_email(self):
        if self.user_id is None and self.email is None:
            raise ValueError("Either user_id or email must be provided.")
        return self


class EmailVerificationConfirmSchema(BaseModel):
    """
    Schema for confirming email verification.
    """

    token: str = Field(..., min_length=1)

    @field_validator("token")
    @classmethod
    def normalize_token(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("token cannot be empty.")
        return normalized


class PhoneVerificationRequestSchema(BaseModel):
    """
    Request schema for phone verification resend/request.
    """

    user_id: Optional[int] = None
    phone_number: Optional[str] = None

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().replace(" ", "")
        return normalized or None

    @model_validator(mode="after")
    def validate_user_or_phone(self):
        if self.user_id is None and self.phone_number is None:
            raise ValueError("Either user_id or phone_number must be provided.")
        return self


class PhoneVerificationConfirmSchema(BaseModel):
    """
    Schema for confirming phone verification.
    """

    token: Optional[str] = None
    otp_code: Optional[str] = None
    challenge_reference: Optional[str] = None

    @field_validator("token", "otp_code", "challenge_reference")
    @classmethod
    def normalize_optional_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_verification_input(self):
        if self.token is None and self.otp_code is None and self.challenge_reference is None:
            raise ValueError("Provide token, otp_code, or challenge_reference.")
        return self


# ============================================================
# AUTHENTICATED USER / SESSION SCHEMAS
# ============================================================

class AuthenticatedUserProfileSchema(BaseModel):
    """
    Detailed authenticated-user profile schema.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: Optional[int] = None
    username: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    first_name: str
    last_name: str
    middle_name: Optional[str] = None

    status: Optional[str] = None
    is_superuser: bool = False
    is_email_verified: bool = False
    is_phone_verified: bool = False

    is_two_factor_enabled: bool = False
    two_factor_method: Optional[str] = None
    two_factor_email_enabled: bool = False
    two_factor_sms_enabled: bool = False
    two_factor_whatsapp_enabled: bool = False
    two_factor_authenticator_enabled: bool = False

    roles: list[AuthRoleLiteSchema] = Field(default_factory=list)

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SessionInfoSchema(BaseModel):
    """
    Optional schema for session or token metadata.
    """

    jti: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    two_factor_verified: bool = False
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class AuthMeResponseSchema(BaseModel):
    """
    Response schema for the authenticated user profile endpoint.
    """

    success: bool = True
    message: str = "Authenticated user fetched successfully."
    user: AuthenticatedUserProfileSchema
    session: Optional[SessionInfoSchema] = None


# ============================================================
# GENERIC ACTION RESPONSE
# ============================================================

class AuthActionResponseSchema(BaseModel):
    """
    Generic response schema for auth-related actions.
    """

    success: bool = True
    message: str