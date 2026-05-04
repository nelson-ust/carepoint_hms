"""
Tenant user invitation endpoints.

Three audiences:

* **Tenant admins** (require ``USERS_INVITE`` permission) create, list,
  cancel, or resend invitations.
* **Anonymous invitees** call ``/invitations/accept`` (no auth required —
  the bearer of the token IS the credential).
* **Background sweeps** call ``/invitations/sweep`` to mark expired
  invitations.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser
from app.core.enums import InvitationStatus
from app.services.invitation_service import InvitationService


router = APIRouter(prefix="/invitations", tags=["Tenant - Invitations"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class InvitationCreateSchema(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role_ids: Optional[list[int]] = None
    expiry_days: Optional[int] = Field(None, ge=1, le=30)


class InvitationReadSchema(BaseModel):
    id: int
    email: Optional[str] = None
    phone_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    status: InvitationStatus
    expires_at: datetime
    role_ids: Optional[list[int]] = None
    invited_by_user_id: Optional[int] = None
    accepted_by_user_id: Optional[int] = None
    accepted_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    last_sent_at: Optional[datetime] = None
    resend_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class InvitationCreateResponseSchema(BaseModel):
    invitation: InvitationReadSchema
    token: str
    accept_url: Optional[str] = None


class InvitationAcceptSchema(BaseModel):
    token: str
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None


def _service(db: Annotated[Session, Depends(get_db)]) -> InvitationService:
    return InvitationService(db)


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=InvitationCreateResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create and dispatch a new user invitation",
)
def create_invitation(
    payload: InvitationCreateSchema,
    actor: AdminUser,
    service: Annotated[InvitationService, Depends(_service)],
):
    rec, token = service.create_invitation(
        email=payload.email,
        phone_number=payload.phone_number,
        first_name=payload.first_name,
        last_name=payload.last_name,
        role_ids=payload.role_ids,
        invited_by_user_id=getattr(actor, "id", None),
        expiry_days=payload.expiry_days,
    )
    # Best-effort delivery. The plain token is also returned in the response
    # so the inviter can fall back to copy/paste if the email queue is down.
    try:
        service.send_invitation_email(rec, token)
    except Exception:
        pass

    from app.core.config import settings

    accept_url = None
    base = getattr(settings, "INVITATION_ACCEPT_BASE_URL", None)
    if base:
        accept_url = f"{base.rstrip('/')}/invitations/accept?token={token}"

    return {"invitation": rec, "token": token, "accept_url": accept_url}


@router.get(
    "",
    response_model=list[InvitationReadSchema],
    summary="List invitations",
)
def list_invitations(
    _: AdminUser,
    service: Annotated[InvitationService, Depends(_service)],
    invitation_status: Optional[InvitationStatus] = None,
):
    return service.list_invitations(status=invitation_status)


@router.post(
    "/{invitation_id}/cancel",
    response_model=InvitationReadSchema,
    summary="Cancel a pending invitation",
)
def cancel_invitation(
    invitation_id: int,
    _: AdminUser,
    service: Annotated[InvitationService, Depends(_service)],
):
    return service.cancel_invitation(invitation_id)


@router.post(
    "/{invitation_id}/resend",
    response_model=InvitationCreateResponseSchema,
    summary="Resend an invitation (rotates the token)",
)
def resend_invitation(
    invitation_id: int,
    _: AdminUser,
    service: Annotated[InvitationService, Depends(_service)],
):
    rec, token = service.resend_invitation(invitation_id)
    try:
        service.send_invitation_email(rec, token)
    except Exception:
        pass

    from app.core.config import settings

    accept_url = None
    base = getattr(settings, "INVITATION_ACCEPT_BASE_URL", None)
    if base:
        accept_url = f"{base.rstrip('/')}/invitations/accept?token={token}"

    return {"invitation": rec, "token": token, "accept_url": accept_url}


@router.post(
    "/sweep",
    summary="Expire all overdue invitations",
)
def sweep_expired(
    _: AdminUser,
    service: Annotated[InvitationService, Depends(_service)],
):
    return {"success": True, "expired": service.expire_due_invitations()}


# ---------------------------------------------------------------------------
# Public route — invitee accepts the invitation
# ---------------------------------------------------------------------------


@router.post(
    "/accept",
    summary="Accept an invitation and complete account setup",
    status_code=status.HTTP_201_CREATED,
)
def accept_invitation(
    payload: InvitationAcceptSchema,
    service: Annotated[InvitationService, Depends(_service)],
):
    """
    Public endpoint. The bearer of a valid token may complete account
    setup. No prior authentication is required because the token *is* the
    credential.
    """
    user = service.accept_invitation(
        token=payload.token,
        username=payload.username,
        password=payload.password,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone_number=payload.phone_number,
    )
    return {
        "success": True,
        "message": "Invitation accepted. You can now sign in.",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        },
    }
