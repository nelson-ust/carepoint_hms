from __future__ import annotations
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.all_models import AllowanceType, DeductionType, StatutoryDeductionConfig
from app.schemas.hr_payroll_schemas import (
    AllowanceTypeCreateSchema,
    DeductionTypeCreateSchema,
    StatutoryDeductionConfigCreateSchema
)

class HRPayrollRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Allowance Types ───────────────────────────────────────────────

    def create_allowance_type(self, data: AllowanceTypeCreateSchema) -> AllowanceType:
        item = AllowanceType(**data.model_dump())
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def list_allowance_types(self) -> List[AllowanceType]:
        return self.db.scalars(
            select(AllowanceType).where(AllowanceType.is_deleted == False)
        ).all()

    # ── Deduction Types ───────────────────────────────────────────────

    def create_deduction_type(self, data: DeductionTypeCreateSchema) -> DeductionType:
        item = DeductionType(**data.model_dump())
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def list_deduction_types(self) -> List[DeductionType]:
        return self.db.scalars(
            select(DeductionType).where(DeductionType.is_deleted == False)
        ).all()

    # ── Statutory Config ──────────────────────────────────────────────

    def create_statutory_config(self, data: StatutoryDeductionConfigCreateSchema) -> StatutoryDeductionConfig:
        item = StatutoryDeductionConfig(**data.model_dump())
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def list_statutory_configs(self) -> List[StatutoryDeductionConfig]:
        return self.db.scalars(
            select(StatutoryDeductionConfig).where(StatutoryDeductionConfig.is_deleted == False)
        ).all()
