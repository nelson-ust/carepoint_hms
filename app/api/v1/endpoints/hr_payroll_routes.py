from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.hr_payroll_schemas import (
    AllowanceTypeCreateSchema, AllowanceTypeReadSchema,
    DeductionTypeCreateSchema, DeductionTypeReadSchema,
    StatutoryDeductionConfigCreateSchema, StatutoryDeductionConfigReadSchema,
    SalaryGradeCreateSchema, SalaryGradeReadSchema,
    SalaryStepCreateSchema, SalaryStepReadSchema,
)
from app.services.hr_payroll_service import HRPayrollService

from app.core.dependencies import require_plan_feature

router = APIRouter(
    prefix="/hr/payroll-config", 
    tags=["HR - Payroll Configuration"],
    dependencies=[Depends(require_plan_feature("hr"))]
)

def _get_service(db: Session = Depends(get_db)) -> HRPayrollService:
    return HRPayrollService(db)

@router.post("/allowance-types", response_model=AllowanceTypeReadSchema)
def create_allowance_type(
    payload: AllowanceTypeCreateSchema,
    service: HRPayrollService = Depends(_get_service)
):
    return service.create_allowance_type(payload)

@router.get("/allowance-types", response_model=List[AllowanceTypeReadSchema])
def list_allowance_types(
    service: HRPayrollService = Depends(_get_service)
):
    return service.repository.list_allowance_types()

@router.post("/deduction-types", response_model=DeductionTypeReadSchema)
def create_deduction_type(
    payload: DeductionTypeCreateSchema,
    service: HRPayrollService = Depends(_get_service)
):
    return service.create_deduction_type(payload)

@router.get("/deduction-types", response_model=List[DeductionTypeReadSchema])
def list_deduction_types(
    service: HRPayrollService = Depends(_get_service)
):
    return service.repository.list_deduction_types()

@router.post("/statutory-configs", response_model=StatutoryDeductionConfigReadSchema)
def create_statutory_config(
    payload: StatutoryDeductionConfigCreateSchema,
    service: HRPayrollService = Depends(_get_service)
):
    return service.create_statutory_config(payload)

@router.get("/statutory-configs", response_model=List[StatutoryDeductionConfigReadSchema])
def list_statutory_configs(
    service: HRPayrollService = Depends(_get_service)
):
    return service.repository.list_statutory_configs()


# ── Salary Grades ─────────────────────────────────────────────────────

@router.post("/salary-grades", response_model=SalaryGradeReadSchema)
def create_salary_grade(
    payload: SalaryGradeCreateSchema,
    service: HRPayrollService = Depends(_get_service)
):
    return service.create_salary_grade(payload)

@router.get("/salary-grades", response_model=List[SalaryGradeReadSchema])
def list_salary_grades(
    service: HRPayrollService = Depends(_get_service)
):
    return service.repository.list_salary_grades()

# ── Salary Steps ──────────────────────────────────────────────────────

@router.post("/salary-steps", response_model=SalaryStepReadSchema)
def create_salary_step(
    payload: SalaryStepCreateSchema,
    service: HRPayrollService = Depends(_get_service)
):
    return service.create_salary_step(payload)

@router.get("/salary-steps", response_model=List[SalaryStepReadSchema])
def list_salary_steps(
    grade_id: Optional[int] = None,
    service: HRPayrollService = Depends(_get_service)
):
    return service.repository.list_salary_steps(grade_id)
