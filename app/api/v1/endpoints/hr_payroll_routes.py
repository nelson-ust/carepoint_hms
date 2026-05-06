from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.hr_payroll_schemas import (
    AllowanceTypeCreateSchema, AllowanceTypeReadSchema,
    DeductionTypeCreateSchema, DeductionTypeReadSchema,
    StatutoryDeductionConfigCreateSchema, StatutoryDeductionConfigReadSchema
)
from app.services.hr_payroll_service import HRPayrollService

router = APIRouter(prefix="/hr/payroll-config", tags=["HR - Payroll Configuration"])

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
