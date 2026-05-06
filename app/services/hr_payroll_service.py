from __future__ import annotations
from sqlalchemy.orm import Session
from app.repositories.hr_payroll_repository import HRPayrollRepository
from app.schemas.hr_payroll_schemas import (
    AllowanceTypeCreateSchema,
    DeductionTypeCreateSchema,
    StatutoryDeductionConfigCreateSchema
)

class HRPayrollService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = HRPayrollRepository(db)

    def create_allowance_type(self, data: AllowanceTypeCreateSchema):
        item = self.repository.create_allowance_type(data)
        self.db.commit()
        return item

    def create_deduction_type(self, data: DeductionTypeCreateSchema):
        item = self.repository.create_deduction_type(data)
        self.db.commit()
        return item

    def create_statutory_config(self, data: StatutoryDeductionConfigCreateSchema):
        item = self.repository.create_statutory_config(data)
        self.db.commit()
        return item
