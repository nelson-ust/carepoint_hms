# app/api/v1/endpoints/patient_portal_routes.py
from __future__ import annotations

from typing import List, Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_plan_feature

from app.models.all_models import User
from app.services.patient_portal_service import PatientPortalService
from app.services.patient_portal_auth_service import PatientPortalAuthService
from app.services.paystack_service import PaystackService
from app.services.membership_card_service import MembershipCardService
from app.services.auth_service import AuthService
from app.schemas.patient_portal_schemas import (
    PatientPortalDashboard,
    PatientPortalProfile,
    PatientFundCardRequest,
    PatientPortalOTPRequest,
    PatientPortalOTPVerify
)
from app.schemas.patient_portal_schema import (
    PatientPortalRequestOtpSchema,
    PatientPortalResendOtpSchema,
    PatientPortalRequestOtpResponseSchema,
    PatientPortalLoginResponseSchema,
    PatientPortalVerifyOtpSchema,
)
from app.schemas.paystack_schemas import PaystackTransactionRead
from app.schemas.notification_schema import NotificationReadSchema
from app.schemas.auth_schemas import LoginSuccessSchema, OTPActionResponseSchema, OTPVerificationSuccessSchema


router = APIRouter(
    prefix="/portal", 
    tags=["Patient Portal"],
    dependencies=[Depends(require_plan_feature("patient_portal"))]
)



def get_portal_service(db: Annotated[Session, Depends(get_db)]) -> PatientPortalService:
    return PatientPortalService(db)

def get_paystack_service(db: Annotated[Session, Depends(get_db)]) -> PaystackService:
    return PaystackService(db)

def get_card_service(db: Annotated[Session, Depends(get_db)]) -> MembershipCardService:
    return MembershipCardService(db)

def get_auth_service(db: Annotated[Session, Depends(get_db)]) -> AuthService:
    return AuthService(db)


def get_portal_auth_service(
    db: Annotated[Session, Depends(get_db)],
) -> PatientPortalAuthService:
    """
    Auth service for the patient portal.

    Distinct from :class:`AuthService` (which assumes a pre-existing
    :class:`User`). The portal flow can authenticate a patient who has
    never logged in before — it auto-creates the User row on first
    successful OTP verification.
    """
    return PatientPortalAuthService(db)


@router.post(
    "/auth/request-otp",
    response_model=PatientPortalRequestOtpResponseSchema,
    summary="Request a 5-digit OTP for patient portal login",
)
async def request_otp(
    payload: PatientPortalRequestOtpSchema,
    request: Request,
    service: Annotated[PatientPortalAuthService, Depends(get_portal_auth_service)],
):
    """
    Generate and dispatch a 5-digit OTP to the patient via email or SMS.

    The patient is identified by email, phone, or hospital number. The OTP
    is short-lived (10 minutes) and is hashed at rest — only the patient
    receives the plaintext via the chosen channel.
    """
    result = service.request_otp(
        identifier=payload.identifier,
        channel=payload.channel,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {
        "success": True,
        "message": "OTP dispatched. Check your email or SMS for the code.",
        **result,
    }


@router.post(
    "/auth/verify-otp",
    response_model=PatientPortalLoginResponseSchema,
    summary="Verify the OTP and exchange it for a JWT pair",
)
async def verify_otp(
    payload: PatientPortalVerifyOtpSchema,
    request: Request,
    service: Annotated[PatientPortalAuthService, Depends(get_portal_auth_service)],
):
    """
    Verify the OTP and (on success) issue access + refresh tokens for the
    patient portal. If the patient has no linked :class:`User` yet, one
    is auto-created and assigned the ``PATIENT`` role.
    """
    result = service.verify_otp(
        otp_id=payload.otp_id,
        otp_code=payload.otp_code,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {
        "success": True,
        "message": "Patient portal access granted.",
        **result,
    }


@router.post(
    "/auth/resend-otp",
    response_model=PatientPortalRequestOtpResponseSchema,
    summary="Resend the active OTP",
)
async def resend_otp(
    payload: PatientPortalResendOtpSchema,
    request: Request,
    service: Annotated[PatientPortalAuthService, Depends(get_portal_auth_service)],
):
    """
    Re-dispatch the active OTP. A fresh code is generated and the
    expiry window is reset; previous codes are invalidated.
    """
    result = service.resend_otp(
        otp_id=payload.otp_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {
        "success": True,
        "message": "OTP resent. Please use the most recent code.",
        **result,
    }


@router.get("/dashboard", response_model=PatientPortalDashboard)
async def get_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PatientPortalService, Depends(get_portal_service)],
):
    """Get summarized dashboard data for the logged-in patient."""
    return service.get_dashboard(current_user.id)


@router.get("/profile", response_model=PatientPortalProfile)
async def get_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PatientPortalService, Depends(get_portal_service)],
):
    """Get detailed profile info for the logged-in patient."""
    return service.get_profile(current_user.id)


@router.get("/notifications", response_model=List[NotificationReadSchema])
async def get_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PatientPortalService, Depends(get_portal_service)],
    skip: int = 0,
    limit: int = 20,
):
    """Get notifications for the logged-in patient."""
    return service.list_notifications(current_user.id, skip=skip, limit=limit)


@router.post("/fund-card", response_model=PaystackTransactionRead)
async def initialize_card_funding(
    payload: PatientFundCardRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    portal_service: Annotated[PatientPortalService, Depends(get_portal_service)],
    paystack_service: Annotated[PaystackService, Depends(get_paystack_service)],
    card_service: Annotated[MembershipCardService, Depends(get_card_service)],
):
    """Initiate a Paystack transaction to fund the patient's membership card."""
    patient = portal_service.get_patient_by_user_id(current_user.id)
    cards = card_service.list_patient_cards(patient.id)
    if not cards:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No membership card found for this patient."
        )
    
    card = cards[0] # Funding the primary/first card
    tx = await paystack_service.initialize_transaction(patient, card, payload.amount)
    return tx
