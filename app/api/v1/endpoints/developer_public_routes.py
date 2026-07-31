# app/api/v1/endpoints/developer_public_routes.py
from __future__ import annotations

"""
Public, unauthenticated developer self-registration.

A third party registers with an organization + email, verifies the email, and
receives a one-time dashboard token used to manage apps and API keys. No patient
data is reachable here — only account bootstrap.
"""

from fastapi import APIRouter, status

from app.schemas.developer_schemas import (
    DeveloperRegisterSchema,
    DeveloperResendSchema,
    DeveloperVerifySchema,
)
from app.services.developer_service import DEVELOPER_SCOPES, DeveloperService

router = APIRouter(prefix="/developer/public", tags=["Developer Platform (public)"])


@router.get("/scopes", summary="List the available API scopes")
def list_scopes():
    return {"success": True, "scopes": [{"code": k, "description": v} for k, v in DEVELOPER_SCOPES.items()]}


@router.post("/register", status_code=status.HTTP_201_CREATED, summary="Register as a developer")
def register(payload: DeveloperRegisterSchema):
    result = DeveloperService().register(
        organization_name=payload.organization_name,
        contact_name=payload.contact_name,
        email=str(payload.email),
        website=payload.website,
        description=payload.description,
    )
    return {
        "success": True,
        "message": ("Registration received. Verify your email to activate the account. "
                    "In production the verification token is emailed; it is included here "
                    "for environments without outbound email."),
        **result,
    }


@router.post("/verify", summary="Verify email and receive a dashboard token")
def verify(payload: DeveloperVerifySchema):
    result = DeveloperService().verify_email(email=str(payload.email), token=payload.token)
    return {
        "success": True,
        "message": "Email verified. Store your dashboard token now — it is shown only once.",
        "account": result,
    }


@router.post("/resend-verification", summary="Re-issue an email verification token")
def resend(payload: DeveloperResendSchema):
    result = DeveloperService().resend_verification(email=str(payload.email))
    return {"success": True, "message": "A new verification token has been issued.", **result}
