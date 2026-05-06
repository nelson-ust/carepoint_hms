from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException

from app.services.onboarding_service import OnboardingService
from app.schemas.onboarding_schemas import OnboardingInvitationCreateSchema, OnboardingCompletionSchema
from app.core.enums import OnboardingInvitationStatus, OnboardingDocumentType
from app.models.all_models import StaffOnboardingInvitation, StaffProfile, User


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def service(db):
    return OnboardingService(db)


class TestOnboardingService:
    
    def test_create_draft_invitation_success(self, service, db):
        payload = OnboardingInvitationCreateSchema(
            staff_profile_id=1,
            candidate_email="candidate@example.com",
            candidate_phone="1234567890",
            notes="New nurse",
            expiry_days=7
        )
        
        service.repo = MagicMock()
        service.repo.get_invitation_by_staff_profile.return_value = None
        service.repo.create_invitation.side_effect = lambda x: x
        
        invitation = service.create_draft_invitation(payload, creator_id=10)
        
        assert invitation.staff_profile_id == 1
        assert invitation.candidate_email == "candidate@example.com"
        assert invitation.status == OnboardingInvitationStatus.DRAFT
        service.repo.create_invitation.assert_called_once()

    def test_create_draft_invitation_already_exists(self, service):
        payload = OnboardingInvitationCreateSchema(
            staff_profile_id=1,
            candidate_email="candidate@example.com"
        )
        service.repo = MagicMock()
        service.repo.get_invitation_by_staff_profile.return_value = MagicMock()
        
        with pytest.raises(HTTPException) as exc:
            service.create_draft_invitation(payload, creator_id=10)
        assert exc.value.status_code == 400

    def test_send_invitation_success(self, service):
        invitation = StaffOnboardingInvitation(id=1, status=OnboardingInvitationStatus.DRAFT, expiry_days=7)
        service.repo = MagicMock()
        service.repo.get_invitation_by_id.return_value = invitation
        
        token = service.send_invitation(1)
        
        assert token is not None
        assert invitation.status == OnboardingInvitationStatus.PENDING
        assert invitation.token_hash is not None
        assert invitation.expires_at is not None
        service.repo.update_invitation.assert_called_once_with(invitation)

    def test_validate_token_expired(self, service):
        invitation = StaffOnboardingInvitation(
            id=1, 
            status=OnboardingInvitationStatus.PENDING,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        raw_token = "valid_token"
        token_hash = service._hash_token(raw_token)
        invitation.token_hash = token_hash
        
        service.repo = MagicMock()
        service.repo.get_invitation_by_token_hash.return_value = invitation
        
        with pytest.raises(HTTPException) as exc:
            service.validate_token(raw_token)
        assert exc.value.status_code == 403
        assert invitation.status == OnboardingInvitationStatus.EXPIRED

    def test_complete_onboarding_success(self, service, db):
        user = User(id=1, first_name="Old", last_name="Name")
        staff_profile = StaffProfile(id=1, user=user)
        invitation = StaffOnboardingInvitation(
            id=1, 
            status=OnboardingInvitationStatus.PENDING,
            staff_profile=staff_profile,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        raw_token = "complete_token"
        invitation.token_hash = service._hash_token(raw_token)
        
        service.repo = MagicMock()
        service.repo.get_invitation_by_token_hash.return_value = invitation
        db.scalars.return_value.all.return_value = []
        
        payload = OnboardingCompletionSchema(
            first_name="New",
            last_name="Name",
            date_of_birth="1990-01-01",
            gender="MALE",
            marital_status="SINGLE",
            nationality="Nigerian",
            address_line_1="123 Street",
            city="Lagos",
            state_region="Lagos",
            country="Nigeria",
            emergency_contact_name="Contact",
            emergency_contact_phone="09012345678",
            emergency_contacts=[],
            licenses=[]
        )
        
        service.complete_onboarding(raw_token, payload)
        
        assert user.first_name == "New"
        assert staff_profile.onboarding_completed is True
        assert invitation.status == OnboardingInvitationStatus.COMPLETED
        db.commit.assert_called()

    def test_get_onboarding_progress(self, service, db):
        staff_profile = StaffProfile(id=1, onboarding_completed=False)
        invitation = StaffOnboardingInvitation(
            id=1, 
            status=OnboardingInvitationStatus.IN_PROGRESS,
            staff_profile=staff_profile,
            documents=[],
            expires_at=datetime.now(timezone.utc) + timedelta(days=2)
        )
        raw_token = "progress_token"
        invitation.token_hash = service._hash_token(raw_token)
        
        service.repo = MagicMock()
        service.repo.get_invitation_by_token_hash.return_value = invitation
        db.scalars.return_value.all.return_value = []
        
        progress = service.get_onboarding_progress(raw_token)
        
        assert progress["completion_percentage"] == 0.0  # 0/4 points (0 demographics, 0/3 docs)
        assert progress["is_demographics_complete"] is False
        assert len(progress["missing_document_types"]) == 3
        assert progress["days_remaining"] >= 1

    @patch("app.services.onboarding_service.OnboardingService.upload_document")
    @patch("app.services.onboarding_service.OnboardingService.complete_onboarding")
    def test_bulk_complete_onboarding(self, mock_complete, mock_upload, service):
        raw_token = "bulk_token"
        token_hash = service._hash_token(raw_token)
        invitation = StaffOnboardingInvitation(
            id=1, 
            token_hash=token_hash,
            status=OnboardingInvitationStatus.PENDING
        )
        
        service.repo = MagicMock()
        service.repo.get_invitation_by_token_hash.return_value = invitation
        
        payload = MagicMock(spec=OnboardingCompletionSchema)
        files = [(OnboardingDocumentType.CV, MagicMock())]
        
        service.bulk_complete_onboarding(raw_token, payload, files)
        
        mock_upload.assert_called_once()
        mock_complete.assert_called_once_with(raw_token, payload)
