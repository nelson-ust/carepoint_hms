from __future__ import annotations

import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple

from fastapi import HTTPException, status, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import StaffOnboardingInvitation, StaffOnboardingDocument, StaffProfile, User
from app.repositories.onboarding_repository import OnboardingRepository
from app.core.enums import OnboardingInvitationStatus, OnboardingDocumentType, NotificationEvent
from app.schemas.onboarding_schemas import (
    OnboardingInvitationCreateSchema,
    OnboardingInvitationUpdateSchema,
    OnboardingCompletionSchema,
    StaffLicenseOnboardingSchema,
    StaffEmergencyContactOnboardingSchema
)
from app.models.all_models import (
    StaffOnboardingInvitation, 
    StaffOnboardingDocument, 
    StaffProfile, 
    User,
    StaffLicense,
    StaffEmergencyContact,
    StaffSalary,
    StaffOnboardingChecklistItem,
    SalaryGrade,
    SalaryStep
)
from app.services.aws_s3_service import S3Service
from app.core.config import settings


class OnboardingService:
    """
    Business logic for the Staff Onboarding process.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = OnboardingRepository(db)
        self.s3_service = S3Service()

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_draft_invitation(self, payload: OnboardingInvitationCreateSchema, creator_id: int) -> StaffOnboardingInvitation:
        """
        HR creates a draft onboarding invitation.
        """
        # Check if an invitation already exists for this staff profile
        existing = self.repo.get_invitation_by_staff_profile(payload.staff_profile_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An onboarding invitation already exists for this staff member."
            )

        invitation = StaffOnboardingInvitation(
            staff_profile_id=payload.staff_profile_id,
            candidate_email=str(payload.candidate_email),
            candidate_phone=payload.candidate_phone,
            notes=payload.notes,
            expiry_days=payload.expiry_days,
            created_by_user_id=creator_id,
            status=OnboardingInvitationStatus.DRAFT,
            salary_grade_id=payload.salary_grade_id,
            salary_step_id=payload.salary_step_id
        )
        invitation = self.repo.create_invitation(invitation)
        
        # Initialize the onboarding checklist for the new hire
        self._initialize_checklist(invitation.staff_profile_id)
        
        return invitation

    def _initialize_checklist(self, staff_profile_id: int):
        """
        Populates the default onboarding checklist for a new staff member.
        """
        defaults = [
            ("Personal Info Update", "Candidate completes their demographic data.", 10),
            ("Document Uploads", "Candidate uploads CV, ID, and certifications.", 20),
            ("Professional License", "Candidate provides valid license details.", 30),
            ("Emergency Contacts", "Candidate provides at least one emergency contact.", 40),
            ("Internal Review", "HR reviews and approves the submitted records.", 100),
        ]
        
        for title, desc, order in defaults:
            item = StaffOnboardingChecklistItem(
                staff_profile_id=staff_profile_id,
                title=title,
                description=desc,
                sort_order=order,
                is_required=True,
                is_completed=False
            )
            self.db.add(item)
        self.db.commit()

    def send_invitation(self, invitation_id: int) -> str:
        """
        Generates a unique token, sets expiry, and marks as PENDING.
        Returns the raw token to be sent in the email.
        """
        invitation = self.repo.get_invitation_by_id(invitation_id)
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")

        if invitation.status not in (OnboardingInvitationStatus.DRAFT, OnboardingInvitationStatus.EXPIRED, OnboardingInvitationStatus.RESENT):
             if invitation.status != OnboardingInvitationStatus.PENDING:
                raise HTTPException(status_code=400, detail=f"Cannot send invitation in {invitation.status} status")

        raw_token = secrets.token_urlsafe(32)
        invitation.token_hash = self._hash_token(raw_token)
        invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=invitation.expiry_days)
        invitation.status = OnboardingInvitationStatus.PENDING
        invitation.sent_at = datetime.now(timezone.utc)
        
        if invitation.status == OnboardingInvitationStatus.PENDING and invitation.sent_at:
            invitation.resend_count = (invitation.resend_count or 0) + 1

        self.repo.update_invitation(invitation)
        
        # In a real app, you would trigger the email dispatch here.
        # self._dispatch_onboarding_email(invitation, raw_token)
        
        return raw_token

    def validate_token(self, raw_token: str) -> StaffOnboardingInvitation:
        """
        Validates the token hash and checks for expiry.
        """
        token_hash = self._hash_token(raw_token)
        invitation = self.repo.get_invitation_by_token_hash(token_hash)
        
        if not invitation:
            raise HTTPException(status_code=403, detail="Invalid onboarding token.")

        if invitation.status != OnboardingInvitationStatus.PENDING and invitation.status != OnboardingInvitationStatus.IN_PROGRESS:
            raise HTTPException(status_code=403, detail=f"Invitation is no longer active (Status: {invitation.status})")

        if invitation.expires_at and datetime.now(timezone.utc) > invitation.expires_at:
            invitation.status = OnboardingInvitationStatus.EXPIRED
            self.repo.update_invitation(invitation)
            raise HTTPException(status_code=403, detail="Onboarding link has expired.")

        return invitation

    def upload_document(self, raw_token: str, doc_type: OnboardingDocumentType, file: UploadFile) -> StaffOnboardingDocument:
        """
        Candidate uploads a document via the onboarding link.
        Stored in AWS S3.
        """
        invitation = self.validate_token(raw_token)
        
        # Mark as in progress if it was just pending
        if invitation.status == OnboardingInvitationStatus.PENDING:
            invitation.status = OnboardingInvitationStatus.IN_PROGRESS
            self.repo.update_invitation(invitation)

        # Generate S3 key: onboarding/{invitation_id}/{timestamp}_{filename}
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        s3_key = f"onboarding/{invitation.id}/{timestamp}_{file.filename}"
        
        # Upload to S3
        # Prioritize tenant-specific bucket from context
        from app.utils.s3_utils import get_bucket_name
        try:
            bucket_name = get_bucket_name()  # tenant bucket only — no shared fallback
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Tenant document storage is not available: {exc}",
            )

        file_url = self.s3_service.upload_file(bucket_name, file, s3_key)
        
        if not file_url:
            raise HTTPException(status_code=500, detail="Failed to upload document to S3.")

        doc = StaffOnboardingDocument(
            invitation_id=invitation.id,
            document_type=doc_type,
            title=file.filename or "Uploaded Document",
            s3_key=s3_key,
            file_url=file_url,
            mime_type=file.content_type,
            size_bytes=file.size
        )
        return self.repo.add_document(doc)


    def complete_onboarding(self, raw_token: str, payload: OnboardingCompletionSchema) -> StaffProfile:
        """
        Final step: Candidate submits their data and completes the self-service flow.
        
        This refactored method now handles:
        1. Demographic updates on StaffProfile and User.
        2. Creation of StaffEmergencyContact records.
        3. Creation of StaffLicense records.
        4. Setup of the StaffSalary record based on HR presets.
        5. Updating the Onboarding Checklist items.
        """
        invitation = self.validate_token(raw_token)
        
        # Fetch related staff profile and user
        staff_profile = invitation.staff_profile
        user = staff_profile.user
        
        # 1. Update User & Basic StaffProfile data
        user.first_name = payload.first_name
        user.last_name = payload.last_name
        user.middle_name = payload.middle_name
        
        staff_profile.date_of_birth = payload.date_of_birth
        staff_profile.gender = payload.gender
        staff_profile.marital_status = payload.marital_status
        staff_profile.nationality = payload.nationality
        staff_profile.address_line_1 = payload.address_line_1
        staff_profile.city = payload.city
        staff_profile.state_region = payload.state_region
        staff_profile.country = payload.country
        
        # Legacy fields for quick access
        staff_profile.emergency_contact_name = payload.emergency_contact_name
        staff_profile.emergency_contact_phone = payload.emergency_contact_phone
        
        # Bank details
        staff_profile.bank_name = payload.bank_name
        staff_profile.bank_account_no = payload.bank_account_no
        staff_profile.bank_account_name = payload.bank_account_name
        
        # 2. Process Detailed Emergency Contacts
        for ec in payload.emergency_contacts:
            contact = StaffEmergencyContact(
                staff_profile_id=staff_profile.id,
                full_name=ec.full_name,
                relationship=ec.relationship,
                phone_number=ec.phone_number,
                email=str(ec.email) if ec.email else None,
                address=ec.address,
                is_primary=ec.is_primary
            )
            self.db.add(contact)
            
        # 3. Process Professional Licenses
        for lic in payload.licenses:
            license_rec = StaffLicense(
                staff_profile_id=staff_profile.id,
                license_type=lic.license_type,
                license_number=lic.license_number,
                issuing_body=lic.issuing_body,
                issue_date=lic.issue_date,
                expiry_date=lic.expiry_date,
                notes=lic.notes
            )
            self.db.add(license_rec)
            
        # 4. Initialize Staff Salary (if HR provided presets)
        if invitation.salary_grade_id:
            # Check if a salary record already exists to avoid duplicates
            salary_stmt = select(StaffSalary).where(StaffSalary.staff_profile_id == staff_profile.id)
            salary_rec = self.db.scalars(salary_stmt).first()
            
            if not salary_rec:
                salary_rec = StaffSalary(
                    staff_profile_id=staff_profile.id,
                    grade_id=invitation.salary_grade_id,
                    step_id=invitation.salary_step_id,
                    effective_from=datetime.now(timezone.utc).date(),
                    is_active=True
                )
                self.db.add(salary_rec)
            else:
                salary_rec.grade_id = invitation.salary_grade_id
                salary_rec.step_id = invitation.salary_step_id

        # 5. Update Checklist Items
        checklist_items = self.db.scalars(
            select(StaffOnboardingChecklistItem).where(StaffOnboardingChecklistItem.staff_profile_id == staff_profile.id)
        ).all()
        
        for item in checklist_items:
            # Automatically mark certain candidate-driven items as complete
            if item.title in ["Personal Info Update", "Professional License", "Emergency Contacts", "Document Uploads"]:
                item.is_completed = True
                item.completed_at = datetime.now(timezone.utc)
        
        # Mark onboarding lifecycle as complete
        staff_profile.onboarding_completed = True
        staff_profile.onboarded_at = datetime.now(timezone.utc)
        
        invitation.status = OnboardingInvitationStatus.COMPLETED
        invitation.completed_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(staff_profile)
        
        return staff_profile

    def get_invitation_by_token(self, raw_token: str) -> StaffOnboardingInvitation:
        """
        Public lookup for the onboarding form initialization.
        """
        return self.validate_token(raw_token)

    def bulk_complete_onboarding(
        self, 
        raw_token: str, 
        payload: OnboardingCompletionSchema,
        files_data: List[Tuple[OnboardingDocumentType, UploadFile]]
    ) -> StaffProfile:
        """
        Enables a candidate to submit their profile data and multiple documents
        in a single request.
        """
        # Validate token first to fail fast
        self.validate_token(raw_token)

        # 1. Process all file uploads
        for doc_type, file in files_data:
            if file and file.filename:
                self.upload_document(raw_token, doc_type, file)

        # 2. Update demographics and mark as complete
        return self.complete_onboarding(raw_token, payload)

    def get_onboarding_progress(self, raw_token: str) -> dict:
        """
        Computes the current progress of the onboarding journey.
        Now factors in the StaffOnboardingChecklistItem records.
        """
        invitation = self.validate_token(raw_token)
        staff_profile = invitation.staff_profile
        
        # Fetch actual checklist items from the database
        items = self.db.scalars(
            select(StaffOnboardingChecklistItem)
            .where(StaffOnboardingChecklistItem.staff_profile_id == staff_profile.id)
            .order_by(StaffOnboardingChecklistItem.sort_order)
        ).all()
        
        if not items or len(items) == 0:
            # Fallback to legacy calculation if no checklist items found
            required_docs = [
                OnboardingDocumentType.CV,
                OnboardingDocumentType.GOVERNMENT_ID,
                OnboardingDocumentType.ACADEMIC_CERTIFICATE
            ]
            uploaded_types = [doc.document_type for doc in invitation.documents]
            total_points = 1 + len(required_docs)
            earned_points = (1 if staff_profile.onboarding_completed else 0)
            earned_points += sum(1 for t in required_docs if t in uploaded_types)
            percentage = (earned_points / total_points) * 100
            
            return {
                "status": invitation.status,
                "completion_percentage": round(percentage, 2),
                "is_demographics_complete": staff_profile.onboarding_completed,
                "uploaded_document_types": uploaded_types,
                "missing_document_types": [t for t in required_docs if t not in uploaded_types],
                "expires_at": invitation.expires_at,
                "days_remaining": self._calc_days_remaining(invitation.expires_at)
            }

        # Calculate based on checklist
        completed_items = [i for i in items if i.is_completed]
        percentage = (len(completed_items) / len(items)) * 100
        
        uploaded_types = [doc.document_type for doc in invitation.documents]

        return {
            "status": invitation.status,
            "completion_percentage": round(percentage, 2),
            "is_demographics_complete": any(i.title == "Personal Info Update" and i.is_completed for i in items),
            "uploaded_document_types": uploaded_types,
            "checklist": [
                {"title": i.title, "is_completed": i.is_completed, "is_required": i.is_required} 
                for i in items
            ],
            "expires_at": invitation.expires_at,
            "days_remaining": self._calc_days_remaining(invitation.expires_at)
        }

    def _calc_days_remaining(self, expires_at: Optional[datetime]) -> Optional[int]:
        if not expires_at:
            return None
        delta = expires_at - datetime.now(timezone.utc)
        return max(0, delta.days)
