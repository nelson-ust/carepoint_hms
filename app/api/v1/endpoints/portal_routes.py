from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.portal_schemas import (
    PortalAccountCreateSchema, PortalAccountReadSchema,
    PortalAppointmentRequestCreateSchema, PortalAppointmentRequestReadSchema,
    PortalClinicianOptionSchema,
    PortalMessageCreateSchema, PortalMessageReadSchema,
    PortalDocumentShareCreateSchema, PortalDocumentShareReadSchema
)
from app.services.portal_service import PortalService
from app.core.multitenancy import get_current_tenant_id
from app.core.exceptions import BadRequestError, NotFoundError
from app.schemas.medical_access_schemas import PortalDecisionSchema
from app.services.medical_access_service import MedicalAccessService

router = APIRouter(prefix="/portal", tags=["Patient Portal"])

def _get_service(db: Session = Depends(get_db)) -> PortalService:
    return PortalService(db)

@router.post("/register", response_model=PortalAccountReadSchema)
def register_account(
    payload: PortalAccountCreateSchema,
    service: PortalService = Depends(_get_service)
):
    return service.register_portal_account(payload)

# Note: In a real app, these would require Portal Account Authentication
# For now, we'll keep the account_id as a parameter or assume it's passed from a dependency

@router.get("/{patient_id}/clinicians", response_model=List[PortalClinicianOptionSchema])
def list_clinicians(
    patient_id: int,
    service: PortalService = Depends(_get_service),
):
    """Doctors the patient can optionally request to see when booking."""
    return service.list_bookable_clinicians()


@router.post("/{patient_id}/appointment-requests", response_model=PortalAppointmentRequestReadSchema)
def request_appointment(
    patient_id: int,
    payload: PortalAppointmentRequestCreateSchema,
    service: PortalService = Depends(_get_service)
):
    # The portal signs patients in via OTP, so the path identifier is the
    # patient id (the frontend sends session.patient_id).
    return service.request_appointment(patient_id, payload)

@router.post("/{account_id}/messages", response_model=PortalMessageReadSchema)
def send_message(
    account_id: int,
    payload: PortalMessageCreateSchema,
    service: PortalService = Depends(_get_service)
):
    return service.send_message(account_id, payload)

@router.post("/{account_id}/document-shares", response_model=PortalDocumentShareReadSchema)
def share_document(
    account_id: int,
    payload: PortalDocumentShareCreateSchema,
    service: PortalService = Depends(_get_service)
):
    return service.share_document(account_id, payload)


# ---------------------------------------------------------------------------
# Medical-record access requests the patient must authorize (in-app).
# ---------------------------------------------------------------------------

def _patient_gpid(db: Session, patient_id: int) -> tuple[int, str]:
    from app.models.all_models import Patient
    tid = get_current_tenant_id()
    if not tid:
        raise BadRequestError(message="A tenant context is required.")
    p = db.query(Patient).filter(Patient.id == patient_id).first()
    if p is None:
        raise NotFoundError(message="Patient not found.")
    return tid, p.global_patient_id


@router.get("/{patient_id}/access-requests", summary="Access requests awaiting the patient's decision")
def list_access_requests(patient_id: int, db: Session = Depends(get_db)):
    tid, gpid = _patient_gpid(db, patient_id)
    items = MedicalAccessService().list_for_patient(holding_tenant_id=tid, patient_global_id=gpid)
    return {"success": True, "items": items}


@router.post("/{patient_id}/access-requests/decision", summary="Patient approves or declines in-app")
def decide_access_request(patient_id: int, payload: PortalDecisionSchema, db: Session = Depends(get_db)):
    tid, gpid = _patient_gpid(db, patient_id)
    result = MedicalAccessService().patient_decision_by_portal(
        holding_tenant_id=tid, patient_global_id=gpid, request_no=payload.request_no,
        approve=payload.approve, reason=payload.reason)
    return {"success": True, "message": "Your response has been recorded.", "request": result}
