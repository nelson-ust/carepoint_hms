# app/api/v1/endpoints/patient_registration_routes.py
from __future__ import annotations

"""
Unified registration + visit-initiation endpoint.

POST /patient-registration/initiate-visit
- existing_patient: looks up by hospital_number / national_identifier / phone / email
- new_patient: registers a new patient inline

Returns the patient + new Visit + first queue ticket so the receptionist UI
can immediately surface the queue number and SDP destination.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.patient_registration_schema import (
    UnifiedVisitInitiationResponseSchema,
    UnifiedVisitInitiationSchema,
)
from app.services.patient_registration_service import PatientRegistrationService

router = APIRouter(prefix="/patient-registration", tags=["Patient Registration"])


def get_registration_service(db: Annotated[Session, Depends(get_db)]) -> PatientRegistrationService:
    return PatientRegistrationService(db)


@router.post(
    "/initiate-visit",
    response_model=UnifiedVisitInitiationResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Register-or-recognize a patient and initiate a visit",
)
def initiate_visit(
    payload: UnifiedVisitInitiationSchema,
    actor: CurrentActiveUser,
    service: Annotated[PatientRegistrationService, Depends(get_registration_service)],
    _: Annotated[User, Depends(require_permission("PATIENT_CREATE", "VISIT_INITIATE"))],
):
    result = service.initiate_visit_with_registration(payload, actor_user_id=actor.id)

    patient = result["patient"]
    visit = result["visit"]
    queue_ticket = result["queue_ticket"]
    admission = result.get("admission")

    # Pick a context-appropriate response message: outpatient vs inpatient.
    if admission is not None:
        message = (
            "Returning patient identified and admitted."
            if result["is_returning_patient"]
            else "New patient registered and admitted."
        )
    else:
        message = (
            "Returning patient identified and visit initiated."
            if result["is_returning_patient"]
            else "New patient registered and visit initiated."
        )

    return {
        "success": True,
        "message": message,
        "is_returning_patient": result["is_returning_patient"],
        "patient_id": patient.id,
        "patient_hospital_number": getattr(patient, "hospital_number", None),
        "visit_id": getattr(visit, "id", None) if visit else 0,
        "visit_code": getattr(visit, "visit_code", None) or "",
        "queue_ticket_id": getattr(queue_ticket, "id", None) if queue_ticket else None,
        "queue_number": getattr(queue_ticket, "queue_number", None) if queue_ticket else None,
        "queue_position": getattr(queue_ticket, "queue_position", None) if queue_ticket else None,
        "first_service_delivery_point_id": (
            getattr(visit, "first_service_delivery_point_id", None) if visit else None
        ),
        "visit_flow_template_id": (
            result["visit_flow_template"].id if result["visit_flow_template"] is not None else None
        ),
        # Admission echo block — populated only in inpatient mode.
        "admission_id": getattr(admission, "id", None) if admission else None,
        "admission_no": getattr(admission, "admission_no", None) if admission else None,
        "admission_status": (
            str(admission.admission_status) if admission else None
        ),
        "ward_id": getattr(admission, "ward_id", None) if admission else None,
        "bed_id": getattr(admission, "bed_id", None) if admission else None,
        "bed_day_charges_captured": int(result.get("bed_day_charges_captured", 0)),
    }
