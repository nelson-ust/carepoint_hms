"""
Schemas for platform-admin management.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class SaaSAdminCreateSchema(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone_number: Optional[str] = None
    password: str
    is_superuser: bool = False
    platform_role: str = Field(
        "SUPPORT_ADMIN",
        description="One of SUPER_ADMIN, SUPPORT_ADMIN, BILLING_ADMIN, SYSTEM_AUDITOR.",
    )


class SaaSAdminUpdateStatusSchema(BaseModel):
    status: str


class SaaSAdminUpdateSchema(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    is_superuser: Optional[bool] = None
    platform_role: Optional[str] = None


class SaaSAdminReadSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: EmailStr
    phone_number: Optional[str] = None
    status: str
    is_superuser: bool
    platform_role: str

    model_config = ConfigDict(from_attributes=True)
