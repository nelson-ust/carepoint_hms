# app/api/v1/endpoints/medical_history_routes.py
from __future__ import annotations

"""
Read-only patient medical history endpoints.

The clinician-facing UI typically calls one of these on visit-open so
the doctor lands on a page that already has the patient's prior visits,
diagnoses, lab + radiology results, prescriptions, surgeries, and
admissions in front of them.

Two routes are exposed for ergonomics:
- ``GET /patients/{patient_id}/medical-history`` — keyed on patient id
- ``GET /visits/{visit_id}/medical-history``     — keyed on visit id;
  resolves to the patient automatically.

Permissions: ``PATIENT_READ`` ∪ ``CONSULTATION_READ`` ∪ ``VISIT_READ``.
Any of these is enough — most clinical roles already carry one of them
out of the canonical seed.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.medical_history_schema import PatientMedicalHistoryResponseSchema
from app.services.medical_history_service import PatientMedicalHistoryService

router = APIRouter(
    tags=["Medical History"],
    dependencies=[Depends(require_plan_feature("clinical"))]
)


def _get_service(db: Annotated[Session, Depends(get_db)]) -> PatientMedicalHistoryService:
    return PatientMedicalHistoryService(db)


@router.get(
    "/patients/{patient_id}/medical-history",
    response_model=PatientMedicalHistoryResponseSchema,
    summary="Aggregated medical history for a patient",
)
def get_patient_medical_history(
    patient_id: int,
    _: Annotated[
        User,
        Depends(require_permission("PATIENT_READ", "CONSULTATION_READ", "VISIT_READ")),
    ],
    service: Annotated[PatientMedicalHistoryService, Depends(_get_service)],
    include_vital_signs: bool = Query(
        True,
        description="Drop the vital-sign timeline when set to false (compact view).",
    ),
    max_visits: Optional[int] = Query(
        None,
        ge=1,
        description=(
            "Restrict aggregation to the most recent N visits. Useful for very "
            "long-running patients where only the latest visits are relevant."
        ),
    ),
):
    """Return the full clinical history for a patient."""
    history = service.get_patient_history(
        patient_id,
        include_vital_signs=include_vital_signs,
        max_visits=max_visits,
    )
    return {
        "success": True,
        "message": "Patient medical history fetched successfully.",
        "history": history,
    }


@router.get(
    "/visits/{visit_id}/medical-history",
    response_model=PatientMedicalHistoryResponseSchema,
    summary="Medical history for the patient of a given visit",
)
def get_history_for_visit(
    visit_id: int,
    _: Annotated[
        User,
        Depends(require_permission("PATIENT_READ", "CONSULTATION_READ", "VISIT_READ")),
    ],
    service: Annotated[PatientMedicalHistoryService, Depends(_get_service)],
    include_vital_signs: bool = Query(True),
    max_visits: Optional[int] = Query(None, ge=1),
):
    """Convenience endpoint — resolve the patient through the visit."""
    history = service.get_history_by_visit(
        visit_id,
        include_vital_signs=include_vital_signs,
        max_visits=max_visits,
    )
    return {
        "success": True,
        "message": "Patient medical history fetched successfully.",
        "history": history,
    }
