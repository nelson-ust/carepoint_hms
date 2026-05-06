from __future__ import annotations
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.portal_repository import PortalRepository
from app.repositories.patient_repository import PatientRepository
from app.schemas.portal_schemas import (
    PortalAccountCreateSchema,
    PortalAppointmentRequestCreateSchema,
    PortalMessageCreateSchema,
    PortalDocumentShareCreateSchema
)
from app.core.security import get_password_hash, validate_password_strength

class PortalService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = PortalRepository(db)
        self.patient_repository = PatientRepository(db)

    def register_portal_account(self, data: PortalAccountCreateSchema):
        # 1. Ensure patient exists
        patient = self.patient_repository.get_by_id(data.patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
            
        # 2. Check if account already exists
        existing = self.repository.get_account_by_username(data.portal_username)
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
            
        # 3. Validate password strength
        validate_password_strength(data.password)
        
        # 4. Hash password and create
        pwd_hash = get_password_hash(data.password)
        account = self.repository.create_account(data, pwd_hash)
        self.db.commit()
        return account

    def request_appointment(self, account_id: int, data: PortalAppointmentRequestCreateSchema):
        request = self.repository.create_appointment_request(account_id, data)
        self.db.commit()
        return request

    def send_message(self, account_id: int, data: PortalMessageCreateSchema):
        message = self.repository.create_message(account_id, data)
        self.db.commit()
        return message

    def share_document(self, account_id: int, data: PortalDocumentShareCreateSchema):
        share = self.repository.create_document_share(account_id, data)
        self.db.commit()
        return share
