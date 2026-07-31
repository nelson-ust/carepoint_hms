from __future__ import annotations
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.all_models import (
    AllowanceType,
    DeductionType,
    SalaryGrade,
    SalaryStep,
    StatutoryDeductionConfig,
)
from app.schemas.hr_payroll_schemas import (
    AllowanceTypeCreateSchema,
    DeductionTypeCreateSchema,
    SalaryGradeCreateSchema,
    SalaryStepCreateSchema,
    StatutoryDeductionConfigCreateSchema,
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

    # ── Salary Grades ─────────────────────────────────────────────────

    def create_salary_grade(self, data: SalaryGradeCreateSchema) -> SalaryGrade:
        item = SalaryGrade(**data.model_dump())
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def list_salary_grades(self) -> List[SalaryGrade]:
        return self.db.scalars(
            select(SalaryGrade).where(SalaryGrade.is_deleted == False)
        ).all()

    # ── Salary Steps ──────────────────────────────────────────────────

    def create_salary_step(self, data: SalaryStepCreateSchema) -> SalaryStep:
        item = SalaryStep(**data.model_dump())
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def list_salary_steps(self, grade_id: Optional[int] = None) -> List[SalaryStep]:
        stmt = select(SalaryStep).where(SalaryStep.is_deleted == False)
        if grade_id is not None:
            stmt = stmt.where(SalaryStep.grade_id == grade_id)
        return self.db.scalars(stmt).all()
