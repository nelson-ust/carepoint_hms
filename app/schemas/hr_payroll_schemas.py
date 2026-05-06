from __future__ import annotations
from typing import List, Optional, Any
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict

# ── Allowance & Deduction Schemas ─────────────────────────────────────

class AllowanceTypeBase(BaseModel):
    code: str
    name: str
    is_taxable: bool = True
    default_amount: Optional[Decimal] = None
    default_percent_of_base: Optional[Decimal] = None
    description: Optional[str] = None
    is_active: bool = True

class AllowanceTypeCreateSchema(AllowanceTypeBase):
    pass

class AllowanceTypeReadSchema(AllowanceTypeBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class DeductionTypeBase(BaseModel):
    code: str
    name: str
    is_statutory: bool = False
    default_amount: Optional[Decimal] = None
    default_percent_of_base: Optional[Decimal] = None
    description: Optional[str] = None
    is_active: bool = True

class DeductionTypeCreateSchema(DeductionTypeBase):
    pass

class DeductionTypeReadSchema(DeductionTypeBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# ── Statutory Config Schemas ──────────────────────────────────────────

class StatutoryDeductionConfigBase(BaseModel):
    code: str
    name: str
    rate_percent: Optional[Decimal] = None
    bands_json: Optional[List[Any]] = None
    employer_rate_percent: Optional[Decimal] = None
    effective_from: date
    effective_to: Optional[date] = None
    note: Optional[str] = None

class StatutoryDeductionConfigCreateSchema(StatutoryDeductionConfigBase):
    pass

class StatutoryDeductionConfigReadSchema(StatutoryDeductionConfigBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
