# app/api/v1/endpoints/patient_clinical_routes.py
"""
Chronic-care endpoints for clinicians: the patient problem list and the
vitals-trend analytics used to gauge whether a patient is improving.
"""
from typing import Annotated, List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.patient_problem_schemas import (
    ClinicalTrendsResponse,
    PatientProblemCreateSchema,
    PatientProblemReadSchema,
    PatientProblemUpdateSchema,
)
from app.services.patient_clinical_service import PatientClinicalService

router = APIRouter(prefix="/patients", tags=["Patient Chronic Care"])

_VIEW = require_permission("PATIENT_READ", "CONSULTATION_READ", "VISIT_READ")
_WRITE = require_permission("CONSULTATION_WRITE", "PATIENT_UPDATE", "PATIENT_WRITE")


def _service(db: Annotated[Session, Depends(get_db)]) -> PatientClinicalService:
    return PatientClinicalService(db)


@router.get(
    "/{patient_id}/problems",
    response_model=List[PatientProblemReadSchema],
    summary="List a patient's chronic problem list",
)
def list_patient_problems(
    patient_id: int,
    service: Annotated[PatientClinicalService, Depends(_service)],
    _: Annotated[User, Depends(_VIEW)],
    active_only: bool = Query(False, description="Exclude RESOLVED problems."),
):
    return service.list_problems(patient_id, active_only=active_only)


@router.post(
    "/{patient_id}/problems",
    response_model=PatientProblemReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add a chronic condition to a patient's problem list",
)
def create_patient_problem(
    patient_id: int,
    payload: PatientProblemCreateSchema,
    service: Annotated[PatientClinicalService, Depends(_service)],
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(_WRITE)],
):
    return service.create_problem(patient_id, payload, diagnosed_by_user_id=actor.id)


@router.put(
    "/{patient_id}/problems/{problem_id}",
    response_model=PatientProblemReadSchema,
    summary="Update a chronic condition (status, notes, severity, ...)",
)
def update_patient_problem(
    patient_id: int,
    problem_id: int,
    payload: PatientProblemUpdateSchema,
    service: Annotated[PatientClinicalService, Depends(_service)],
    _: Annotated[User, Depends(_WRITE)],
):
    return service.update_problem(patient_id, problem_id, payload)


@router.delete(
    "/{patient_id}/problems/{problem_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove a condition from the problem list",
)
def delete_patient_problem(
    patient_id: int,
    problem_id: int,
    service: Annotated[PatientClinicalService, Depends(_service)],
    _: Annotated[User, Depends(_WRITE)],
):
    service.delete_problem(patient_id, problem_id)
    return {"success": True, "message": "Problem removed."}


@router.get(
    "/{patient_id}/clinical-trends",
    response_model=ClinicalTrendsResponse,
    summary="Vitals trend analytics (improving / stable / worsening)",
)
def get_clinical_trends(
    patient_id: int,
    service: Annotated[PatientClinicalService, Depends(_service)],
    _: Annotated[User, Depends(_VIEW)],
):
    return service.clinical_trends(patient_id)
