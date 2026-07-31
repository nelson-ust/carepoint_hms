# app/schemas/developer_schemas.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ---------- Public registration / verification ----------

class DeveloperRegisterSchema(BaseModel):
    organization_name: str = Field(..., min_length=2, max_length=255)
    contact_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    website: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)


class DeveloperVerifySchema(BaseModel):
    email: EmailStr
    token: str = Field(..., min_length=8)


class DeveloperResendSchema(BaseModel):
    email: EmailStr


# ---------- App management (dashboard token) ----------

class AppCreateSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    environment: str = Field("SANDBOX", description="SANDBOX or LIVE.")
    scopes: list[str] = Field(..., min_length=1, description="Subset of the developer scope catalog.")


class AppScopesSchema(BaseModel):
    scopes: list[str] = Field(..., min_length=1)


# ---------- Data grants ----------

class GrantRequestSchema(BaseModel):
    app_id: int
    tenant_code: str = Field(..., min_length=1, max_length=100,
                             description="Public code of the hospital/tenant whose data you need.")
    requested_scopes: Optional[list[str]] = None
    justification: Optional[str] = Field(None, max_length=2000)


class GrantDecisionSchema(BaseModel):
    approve: bool
    approved_scopes: Optional[list[str]] = Field(
        None, description="Subset of the requested scopes to approve. Defaults to all requested.")
    note: Optional[str] = Field(None, max_length=2000)


class GrantRevokeSchema(BaseModel):
    note: Optional[str] = Field(None, max_length=2000)


class AccountStatusSchema(BaseModel):
    active: bool
    reason: Optional[str] = Field(None, max_length=2000)
