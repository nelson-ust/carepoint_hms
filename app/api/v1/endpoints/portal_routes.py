from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.portal_schemas import (
    PortalAccountCreateSchema, PortalAccountReadSchema,
    PortalAppointmentRequestCreateSchema, PortalAppointmentRequestReadSchema,
    PortalMessageCreateSchema, PortalMessageReadSchema,
    PortalDocumentShareCreateSchema, PortalDocumentShareReadSchema
)
from app.services.portal_service import PortalService

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

@router.post("/{account_id}/appointment-requests", response_model=PortalAppointmentRequestReadSchema)
def request_appointment(
    account_id: int,
    payload: PortalAppointmentRequestCreateSchema,
    service: PortalService = Depends(_get_service)
):
    return service.request_appointment(account_id, payload)

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
