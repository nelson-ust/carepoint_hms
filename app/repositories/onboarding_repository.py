from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
import hashlib

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models.all_models import (
    StaffOnboardingInvitation, 
    StaffOnboardingDocument, 
    StaffProfile,
    StaffLicense,
    StaffEmergencyContact,
    StaffSalary,
    StaffOnboardingChecklistItem,
    SalaryGrade,
    SalaryStep
)
from app.core.enums import OnboardingInvitationStatus


class OnboardingRepository:
    """
    Handles database operations for Staff Onboarding invitations and documents.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_invitation_by_id(self, invitation_id: int) -> Optional[StaffOnboardingInvitation]:
        return self.db.scalars(
            select(StaffOnboardingInvitation).where(StaffOnboardingInvitation.id == invitation_id)
        ).first()

    def get_invitation_by_token_hash(self, token_hash: str) -> Optional[StaffOnboardingInvitation]:
        return self.db.scalars(
            select(StaffOnboardingInvitation).where(StaffOnboardingInvitation.token_hash == token_hash)
        ).first()

    def get_invitation_by_staff_profile(self, staff_profile_id: int) -> Optional[StaffOnboardingInvitation]:
        return self.db.scalars(
            select(StaffOnboardingInvitation).where(StaffOnboardingInvitation.staff_profile_id == staff_profile_id)
        ).first()

    def list_invitations(
        self,
        status: Optional[OnboardingInvitationStatus] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[StaffOnboardingInvitation], int]:
        stmt = select(StaffOnboardingInvitation)
        if status:
            stmt = stmt.where(StaffOnboardingInvitation.status == status)
        
        stmt = stmt.order_by(StaffOnboardingInvitation.id.desc())
        
        total = len(self.db.scalars(stmt).all())
        items = list(self.db.scalars(stmt.offset(skip).limit(limit)).all())
        return items, total

    def create_invitation(self, invitation: StaffOnboardingInvitation) -> StaffOnboardingInvitation:
        self.db.add(invitation)
        self.db.commit()
        self.db.refresh(invitation)
        return invitation

    def update_invitation(self, invitation: StaffOnboardingInvitation) -> StaffOnboardingInvitation:
        self.db.commit()
        self.db.refresh(invitation)
        return invitation

    def add_document(self, document: StaffOnboardingDocument) -> StaffOnboardingDocument:
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get_document(self, document_id: int) -> Optional[StaffOnboardingDocument]:
        return self.db.scalars(
            select(StaffOnboardingDocument).where(StaffOnboardingDocument.id == document_id)
        ).first()

    def delete_document(self, document: StaffOnboardingDocument) -> None:
        self.db.delete(document)
        self.db.commit()
