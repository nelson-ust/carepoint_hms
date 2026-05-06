from __future__ import annotations

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.all_models import User
from app.schemas.onboarding_schemas import (
    OnboardingInvitationCreateSchema,
    OnboardingInvitationReadSchema,
    OnboardingCompletionSchema,
    OnboardingDocumentReadSchema,
    OnboardingProgressSchema
)
from app.services.onboarding_service import OnboardingService
from app.core.enums import OnboardingDocumentType
import json
from pydantic import ValidationError


router = APIRouter(prefix="/onboarding", tags=["HR - Staff Onboarding"])


def _get_service(db: Session = Depends(get_db)) -> OnboardingService:
    return OnboardingService(db)


# ── HR Administrative Endpoints ──────────────────────────────────────

@router.post("/invitations", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_onboarding_invitation(
    payload: OnboardingInvitationCreateSchema,
    current_user: User = Depends(get_current_user),
    service: OnboardingService = Depends(_get_service)
):
    """
    HR creates a draft onboarding invitation for a candidate.
    """
    invitation = service.create_draft_invitation(payload, creator_id=current_user.id)
    return {
        "success": True,
        "message": "Onboarding invitation drafted successfully.",
        "invitation": OnboardingInvitationReadSchema.model_validate(invitation).model_dump()
    }


@router.post("/invitations/{invitation_id}/send", response_model=dict)
def send_onboarding_link(
    invitation_id: int,
    current_user: User = Depends(get_current_user),
    service: OnboardingService = Depends(_get_service)
):
    """
    Generate the unique token and "send" the email.
    In this demo, we return the token/link so you can see it.
    """
    token = service.send_invitation(invitation_id)
    # Build a sample link (In prod this would be your frontend URL)
    onboarding_link = f"/onboarding/start?token={token}"
    
    return {
        "success": True,
        "message": "Onboarding invitation sent successfully.",
        "token": token,
        "link": onboarding_link
    }


@router.get("/invitations", response_model=dict)
def list_onboarding_invitations(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    service: OnboardingService = Depends(_get_service)
):
    """
    List all onboarding invitations.
    """
    items, total = service.repo.list_invitations(skip=skip, limit=limit)
    return {
        "success": True,
        "items": [OnboardingInvitationReadSchema.model_validate(i).model_dump() for i in items],
        "total": total
    }


# ── Candidate/Public Endpoints (Token-based) ─────────────────────────

@router.get("/session", response_model=dict)
def get_onboarding_session(
    token: str,
    service: OnboardingService = Depends(_get_service)
):
    """
    Public endpoint for the candidate to fetch their onboarding context
    using the token provided in their email.
    """
    invitation = service.get_invitation_by_token(token)
    return {
        "success": True,
        "invitation": OnboardingInvitationReadSchema.model_validate(invitation).model_dump()
    }


@router.post("/upload", response_model=dict)
def upload_onboarding_document(
    token: str = Form(...),
    document_type: OnboardingDocumentType = Form(...),
    file: UploadFile = File(...),
    service: OnboardingService = Depends(_get_service)
):
    """
    Candidate uploads a required document.
    """
    doc = service.upload_document(token, document_type, file)
    return {
        "success": True,
        "message": f"Document '{doc.title}' uploaded successfully.",
        "document": OnboardingDocumentReadSchema.model_validate(doc).model_dump()
    }


@router.post("/complete", response_model=dict)
def complete_onboarding(
    token: str,
    payload: OnboardingCompletionSchema,
    service: OnboardingService = Depends(_get_service)
):
    """
    Candidate submits their final demographic data to complete onboarding.
    """
    staff_profile = service.complete_onboarding(token, payload)
    return {
        "success": True,
        "message": "Onboarding completed successfully. Welcome to the team!",
        "staff_profile_id": staff_profile.id
    }


@router.get("/progress", response_model=dict)
def get_onboarding_progress(
    token: str,
    service: OnboardingService = Depends(_get_service)
):
    """
    Check the current progress of the onboarding journey.
    """
    progress = service.get_onboarding_progress(token)
    return {
        "success": True,
        "progress": OnboardingProgressSchema.model_validate(progress).model_dump()
    }


@router.post("/bulk-complete", response_model=dict)
def bulk_complete_onboarding(
    token: str = Form(...),
    payload_json: str = Form(...),
    cv_file: Optional[UploadFile] = File(None),
    id_file: Optional[UploadFile] = File(None),
    cert_file: Optional[UploadFile] = File(None),
    service: OnboardingService = Depends(_get_service)
):
    """
    Unified endpoint to submit all demographic data and documents at once.
    `payload_json` should be a JSON string representing `OnboardingCompletionSchema`.
    """
    try:
        data = json.loads(payload_json)
        payload = OnboardingCompletionSchema(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid completion data: {str(e)}"
        )

    files_data = []
    if cv_file:
        files_data.append((OnboardingDocumentType.CV, cv_file))
    if id_file:
        files_data.append((OnboardingDocumentType.GOVERNMENT_ID, id_file))
    if cert_file:
        files_data.append((OnboardingDocumentType.ACADEMIC_CERTIFICATE, cert_file))
        
    staff_profile = service.bulk_complete_onboarding(token, payload, files_data)
    return {
        "success": True,
        "message": "Full onboarding completed in one step!",
        "staff_profile_id": staff_profile.id
    }
