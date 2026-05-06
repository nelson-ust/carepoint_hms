from __future__ import annotations
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.models.all_models import (
    PatientIdentifier, 
    PatientAttachment, 
    PatientConsent, 
    InsuranceProvider, 
    PatientInsurance
)
from app.schemas.patient_identity_schemas import (
    PatientIdentifierCreateSchema,
    PatientAttachmentCreateSchema,
    PatientConsentCreateSchema,
    InsuranceProviderCreateSchema,
    PatientInsuranceCreateSchema
)

class PatientIdentityRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Identifiers ───────────────────────────────────────────────────

    def create_identifier(self, patient_id: int, data: PatientIdentifierCreateSchema) -> PatientIdentifier:
        identifier = PatientIdentifier(patient_id=patient_id, **data.model_dump())
        self.db.add(identifier)
        self.db.flush()
        self.db.refresh(identifier)
        return identifier

    def list_identifiers(self, patient_id: int) -> List[PatientIdentifier]:
        return self.db.scalars(
            select(PatientIdentifier)
            .where(PatientIdentifier.patient_id == patient_id, PatientIdentifier.is_deleted == False)
        ).all()

    # ── Attachments ───────────────────────────────────────────────────

    def create_attachment(self, patient_id: int, uploaded_by_id: int, data: PatientAttachmentCreateSchema) -> PatientAttachment:
        attachment = PatientAttachment(
            patient_id=patient_id, 
            uploaded_by_id=uploaded_by_id, 
            **data.model_dump()
        )
        self.db.add(attachment)
        self.db.flush()
        self.db.refresh(attachment)
        return attachment

    def list_attachments(self, patient_id: int) -> List[PatientAttachment]:
        return self.db.scalars(
            select(PatientAttachment)
            .where(PatientAttachment.patient_id == patient_id, PatientAttachment.is_deleted == False)
        ).all()

    # ── Consents ──────────────────────────────────────────────────────

    def create_consent(self, patient_id: int, recorded_by_id: int, data: PatientConsentCreateSchema) -> PatientConsent:
        consent = PatientConsent(
            patient_id=patient_id, 
            recorded_by_id=recorded_by_id, 
            **data.model_dump()
        )
        self.db.add(consent)
        self.db.flush()
        self.db.refresh(consent)
        return consent

    def list_consents(self, patient_id: int) -> List[PatientConsent]:
        return self.db.scalars(
            select(PatientConsent)
            .where(PatientConsent.patient_id == patient_id, PatientConsent.is_deleted == False)
        ).all()

    # ── Insurance Providers ───────────────────────────────────────────

    def create_provider(self, data: InsuranceProviderCreateSchema) -> InsuranceProvider:
        provider = InsuranceProvider(**data.model_dump())
        self.db.add(provider)
        self.db.flush()
        self.db.refresh(provider)
        return provider

    def get_provider(self, provider_id: int) -> Optional[InsuranceProvider]:
        return self.db.get(InsuranceProvider, provider_id)

    def list_providers(self, skip: int = 0, limit: int = 100) -> List[InsuranceProvider]:
        return self.db.scalars(
            select(InsuranceProvider)
            .where(InsuranceProvider.is_deleted == False)
            .offset(skip).limit(limit)
        ).all()

    # ── Patient Insurance ─────────────────────────────────────────────

    def create_patient_insurance(self, patient_id: int, data: PatientInsuranceCreateSchema) -> PatientInsurance:
        record = PatientInsurance(patient_id=patient_id, **data.model_dump())
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def list_patient_insurance(self, patient_id: int) -> List[PatientInsurance]:
        return self.db.scalars(
            select(PatientInsurance)
            .where(PatientInsurance.patient_id == patient_id, PatientInsurance.is_deleted == False)
        ).all()
