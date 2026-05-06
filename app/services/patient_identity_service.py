from __future__ import annotations
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.patient_identity_repository import PatientIdentityRepository
from app.schemas.patient_identity_schemas import (
    PatientIdentifierCreateSchema,
    PatientAttachmentCreateSchema,
    PatientConsentCreateSchema,
    InsuranceProviderCreateSchema,
    PatientInsuranceCreateSchema
)

class PatientIdentityService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = PatientIdentityRepository(db)

    # ── Identifiers ───────────────────────────────────────────────────

    def add_identifier(self, patient_id: int, data: PatientIdentifierCreateSchema):
        # Logic to ensure only one is primary if requested
        if data.is_primary:
            identifiers = self.repository.list_identifiers(patient_id)
            for ident in identifiers:
                if ident.is_primary:
                    ident.is_primary = False
                    self.db.add(ident)
        
        identifier = self.repository.create_identifier(patient_id, data)
        self.db.commit()
        return identifier

    # ── Attachments ───────────────────────────────────────────────────

    def add_attachment(self, patient_id: int, uploaded_by_id: int, data: PatientAttachmentCreateSchema):
        attachment = self.repository.create_attachment(patient_id, uploaded_by_id, data)
        self.db.commit()
        return attachment

    # ── Consents ──────────────────────────────────────────────────────

    def record_consent(self, patient_id: int, recorded_by_id: int, data: PatientConsentCreateSchema):
        consent = self.repository.create_consent(patient_id, recorded_by_id, data)
        self.db.commit()
        return consent

    # ── Insurance ─────────────────────────────────────────────────────

    def create_insurance_provider(self, data: InsuranceProviderCreateSchema):
        provider = self.repository.create_provider(data)
        self.db.commit()
        return provider

    def link_patient_insurance(self, patient_id: int, data: PatientInsuranceCreateSchema):
        provider = self.repository.get_provider(data.insurance_provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Insurance provider not found")
            
        record = self.repository.create_patient_insurance(patient_id, data)
        self.db.commit()
        return record
