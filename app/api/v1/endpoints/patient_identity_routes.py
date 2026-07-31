from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_plan_feature
from app.models.all_models import User
from app.schemas.patient_identity_schemas import (
    PatientIdentifierCreateSchema, PatientIdentifierReadSchema,
    PatientAttachmentCreateSchema, PatientAttachmentReadSchema,
    PatientConsentCreateSchema, PatientConsentReadSchema,
    InsuranceProviderCreateSchema, InsuranceProviderReadSchema,
    PatientInsuranceCreateSchema, PatientInsuranceReadSchema
)
from app.services.patient_identity_service import PatientIdentityService

router = APIRouter(
    prefix="/patient-master", 
    tags=["Patient - Identity & Insurance"],
    dependencies=[Depends(require_plan_feature("clinical"))]
)

def _get_service(db: Session = Depends(get_db)) -> PatientIdentityService:
    return PatientIdentityService(db)

# ── Identifiers ───────────────────────────────────────────────────

@router.post("/{patient_id}/identifiers", response_model=PatientIdentifierReadSchema)
def add_identifier(
    patient_id: int,
    payload: PatientIdentifierCreateSchema,
    service: PatientIdentityService = Depends(_get_service)
):
    return service.add_identifier(patient_id, payload)

@router.get("/{patient_id}/identifiers", response_model=List[PatientIdentifierReadSchema])
def list_identifiers(
    patient_id: int,
    service: PatientIdentityService = Depends(_get_service)
):
    return service.repository.list_identifiers(patient_id)

# ── Attachments ───────────────────────────────────────────────────

@router.post("/{patient_id}/attachments", response_model=PatientAttachmentReadSchema)
def add_attachment(
    patient_id: int,
    payload: PatientAttachmentCreateSchema,
    current_user: User = Depends(get_current_user),
    service: PatientIdentityService = Depends(_get_service)
):
    return service.add_attachment(patient_id, current_user.id, payload)

# ── Consents ──────────────────────────────────────────────────────

@router.post("/{patient_id}/consents", response_model=PatientConsentReadSchema)
def record_consent(
    patient_id: int,
    payload: PatientConsentCreateSchema,
    current_user: User = Depends(get_current_user),
    service: PatientIdentityService = Depends(_get_service)
):
    return service.record_consent(patient_id, current_user.id, payload)

# ── Insurance Providers ───────────────────────────────────────────

@router.post("/insurance-providers", response_model=InsuranceProviderReadSchema)
def create_provider(
    payload: InsuranceProviderCreateSchema,
    service: PatientIdentityService = Depends(_get_service)
):
    return service.create_insurance_provider(payload)

@router.get("/insurance-providers", response_model=List[InsuranceProviderReadSchema])
def list_providers(
    skip: int = 0, limit: int = 100,
    service: PatientIdentityService = Depends(_get_service)
):
    return service.repository.list_providers(skip, limit)

# ── Patient Insurance ─────────────────────────────────────────────

@router.post("/{patient_id}/insurance", response_model=PatientInsuranceReadSchema)
def link_insurance(
    patient_id: int,
    payload: PatientInsuranceCreateSchema,
    service: PatientIdentityService = Depends(_get_service)
):
    return service.link_patient_insurance(patient_id, payload)

@router.get("/{patient_id}/insurance", response_model=List[PatientInsuranceReadSchema])
def list_patient_insurance(
    patient_id: int,
    service: PatientIdentityService = Depends(_get_service)
):
    """List a patient's insurance policies (used to map claims to a policy)."""
    return service.list_patient_insurance(patient_id)
