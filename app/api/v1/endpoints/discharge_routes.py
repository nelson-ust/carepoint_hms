# app/api/v1/endpoints/discharge_routes.py
from __future__ import annotations

"""
FastAPI routes for the inpatient discharge close-out.

Endpoints
---------
- ``POST /discharges``                                   submit a discharge
- ``GET  /discharges/{discharge_id}``                    read one discharge
- ``GET  /discharges/admissions/{admission_id}``         find by admission

Each discharge:
1. Captures any uncaptured bed-day charges up to the discharge date.
2. Frees the bed.
3. Marks the admission DISCHARGED.
4. Optionally closes the visit when the admission was the last open event.
5. Emits a ``PATIENT_DISCHARGED`` security audit row.

Permission codes used
---------------------
- ``ADMISSION_DISCHARGE`` — submit a discharge
- ``BILLING_READ``        — read discharge details
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.discharge_schema import (
    DischargeActionResponseSchema,
    DischargeCreateSchema,
    DischargeReadSchema,
)
from app.services.discharge_service import DischargeService

router = APIRouter(
    prefix="/discharges", 
    tags=["Discharges"],
    dependencies=[Depends(require_plan_feature("inpatient"))]
)


def get_discharge_service(db: Annotated[Session, Depends(get_db)]) -> DischargeService:
    """FastAPI dependency that constructs a DischargeService per-request."""
    return DischargeService(db)


@router.post(
    "/",
    response_model=DischargeActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Discharge an admitted patient",
)
def discharge(
    payload: DischargeCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[DischargeService, Depends(get_discharge_service)],
    _: Annotated[User, Depends(require_permission("ADMISSION_DISCHARGE"))],
):
    """
    Close out an inpatient admission.
    """
    result = service.discharge(payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Patient discharged.",
        "discharge": result["discharge"],
        "admission_id": result["admission_id"],
        "bed_day_charges_captured": result["bed_day_charges_captured"],
        "visit_completed": result["visit_completed"],
    }


@router.get(
    "/admissions/{admission_id}/readiness",
    summary="Check whether an admission is ready for discharge",
)
def check_discharge_readiness(
    admission_id: int,
    _: Annotated[User, Depends(require_permission("ADMISSION_DISCHARGE", "BILLING_READ", "VISIT_READ"))],
    service: Annotated[DischargeService, Depends(get_discharge_service)],
):
    return service.readiness_for_admission(admission_id)


@router.get(
    "/{discharge_id}",
    response_model=DischargeReadSchema,
    summary="Get a discharge record",
)
def get_discharge(
    discharge_id: int,
    _: Annotated[User, Depends(require_permission("BILLING_READ", "ADMISSION_DISCHARGE", "VISIT_READ"))],
    service: Annotated[DischargeService, Depends(get_discharge_service)],
):
    """Read a single discharge record."""
    return service.get(discharge_id)


@router.get(
    "/admissions/{admission_id}",
    response_model=DischargeReadSchema,
    summary="Get the discharge tied to an admission",
)
def get_discharge_for_admission(
    admission_id: int,
    _: Annotated[User, Depends(require_permission("BILLING_READ", "ADMISSION_DISCHARGE", "VISIT_READ"))],
    service: Annotated[DischargeService, Depends(get_discharge_service)],
):
    """
    Locate the discharge record for a given admission.
    """
    discharge = service.get_for_admission(admission_id)
    if discharge is None:
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "message": "Admission has not been discharged yet.",
                "admission_id": admission_id,
            },
        )
    return discharge
