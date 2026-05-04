# app/schemas/procedure_schema.py
from __future__ import annotations

"""
Pydantic schemas for the clinical procedure orders module.

Covers:
- ``ProcedureCatalog`` — master list of procedures with default pricing
- ``ProcedureOrder``   — per-visit ordered procedure with execution lifecycle

Lifecycle reflected in these schemas:
    DRAFT -> ORDERED -> IN_PROGRESS -> COMPLETED
                                    \-> CANCELLED
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================
# CATALOG
# ============================================================


class ProcedureCatalogCreateSchema(BaseModel):
    """Add a procedure to the master catalog."""

    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    default_price: Optional[Decimal] = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        # Stable uppercase codes keep audit + integration mappings predictable.
        return v.strip().upper().replace(" ", "_")


class ProcedureCatalogUpdateSchema(BaseModel):
    """Edit catalog metadata. Code is intentionally immutable post-create."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    default_price: Optional[Decimal] = None


class ProcedureCatalogReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: Optional[str] = None
    default_price: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProcedureCatalogListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Procedures fetched successfully."
    items: list[ProcedureCatalogReadSchema]
    count: int
    meta: dict


class ProcedureCatalogActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    procedure: ProcedureCatalogReadSchema


# ============================================================
# ORDER
# ============================================================


class ProcedureOrderCreateSchema(BaseModel):
    """Order a procedure for a visit."""

    visit_id: int
    procedure_catalog_id: int
    consultation_id: Optional[int] = None
    ordered_by_staff_id: Optional[int] = None
    notes: Optional[str] = Field(None, max_length=4000)
    auto_capture_charge: bool = Field(
        default=True,
        description="Capture a billing line for this procedure into the visit's open billing.",
    )


class ProcedureOrderTransitionSchema(BaseModel):
    """Generic transition body for in-progress / complete / cancel."""

    performed_by_staff_id: Optional[int] = None
    findings: Optional[str] = Field(None, max_length=8000)
    note: Optional[str] = Field(None, max_length=2000)


class ProcedureOrderReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    consultation_id: Optional[int] = None
    procedure_catalog_id: int
    ordered_by_staff_id: Optional[int] = None
    performed_by_staff_id: Optional[int] = None
    status: str
    findings: Optional[str] = None
    notes: Optional[str] = None
    ordered_at: datetime
    performed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProcedureOrderListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Procedure orders fetched successfully."
    items: list[ProcedureOrderReadSchema]
    count: int
    meta: dict


class ProcedureOrderActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    order: ProcedureOrderReadSchema
