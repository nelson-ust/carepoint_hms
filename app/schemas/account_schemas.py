# app/schemas/account_schemas.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import AccountType


class AccountCreateSchema(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=150)
    account_type: AccountType = AccountType.REVENUE
    description: Optional[str] = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "-")


class AccountUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=150)
    account_type: Optional[AccountType] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class AccountReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    account_type: AccountType
    description: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AccountListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Accounts fetched successfully."
    items: list[AccountReadSchema]
    count: int
    meta: dict


class AccountActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    account: AccountReadSchema
