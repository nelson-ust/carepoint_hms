"""
Tenant email-configuration endpoints.

A tenant administrator points the platform at *their own* email
infrastructure (SMTP relay, SendGrid, Mailgun, Postmark, Resend, or
Amazon SES) so that emails to their patients/users come from a sender
they control. Credentials submitted here are encrypted at rest by
:class:`TenantEmailService`; only the send adapter ever sees them in
plaintext, in memory, at the moment of use.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser
from app.core.enums import EmailProvider
from app.services.tenant_email_service import TenantEmailService


router = APIRouter(
    prefix="/tenant-email-config",
    tags=["Tenant - Email Configuration"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class EmailCredentialsSchema(BaseModel):
    smtp_password: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None


class EmailConfigCreateSchema(BaseModel):
    provider: EmailProvider = EmailProvider.SMTP
    display_name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None
    from_email: EmailStr
    from_name: Optional[str] = None
    reply_to: Optional[EmailStr] = None
    footer_text: Optional[str] = None
    footer_html: Optional[str] = None
    is_active: bool = True
    is_default: bool = True
    sandbox_mode: bool = False
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_security: str = Field("TLS", pattern=r"^(NONE|TLS|SSL)$")
    smtp_username: Optional[str] = None
    api_base_url: Optional[str] = None
    api_region: Optional[str] = None
    api_domain: Optional[str] = None
    credentials: Optional[EmailCredentialsSchema] = None


class EmailConfigUpdateSchema(BaseModel):
    provider: Optional[EmailProvider] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    from_email: Optional[EmailStr] = None
    from_name: Optional[str] = None
    reply_to: Optional[EmailStr] = None
    footer_text: Optional[str] = None
    footer_html: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    sandbox_mode: Optional[bool] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_security: Optional[str] = Field(None, pattern=r"^(NONE|TLS|SSL)$")
    smtp_username: Optional[str] = None
    api_base_url: Optional[str] = None
    api_region: Optional[str] = None
    api_domain: Optional[str] = None
    credentials: Optional[EmailCredentialsSchema] = None


class EmailConfigReadSchema(BaseModel):
    id: int
    provider: EmailProvider
    display_name: str
    description: Optional[str] = None
    from_email: EmailStr
    from_name: Optional[str] = None
    reply_to: Optional[EmailStr] = None
    footer_text: Optional[str] = None
    footer_html: Optional[str] = None
    is_active: bool
    is_default: bool
    sandbox_mode: bool
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_security: str
    smtp_username: Optional[str] = None
    api_base_url: Optional[str] = None
    api_region: Optional[str] = None
    api_domain: Optional[str] = None
    last_used_at: Optional[datetime] = None
    last_test_at: Optional[datetime] = None
    last_test_status: Optional[str] = None
    last_test_error: Optional[str] = None
    sent_count: int = 0

    # Credential presence flags only — never the plaintext.
    has_smtp_password: bool = False
    has_api_key: bool = False
    has_api_secret: bool = False

    model_config = ConfigDict(from_attributes=True)


class SendTestEmailSchema(BaseModel):
    recipient: EmailStr
    subject: str = "CarePoint HMS — test email"
    body_text: str = (
        "If you can read this, your tenant's outbound-email "
        "configuration is working correctly."
    )
    body_html: Optional[str] = None


def _service(db: Annotated[Session, Depends(get_db)]) -> TenantEmailService:
    return TenantEmailService(db)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[EmailConfigReadSchema],
    summary="List the tenant's email configurations",
)
def list_email_configs(
    _: AdminUser,
    service: Annotated[TenantEmailService, Depends(_service)],
    only_active: bool = False,
):
    return service.list_configs(only_active=only_active)


@router.post(
    "",
    response_model=EmailConfigReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Configure a new email provider for the tenant",
)
def create_email_config(
    payload: EmailConfigCreateSchema,
    _: AdminUser,
    service: Annotated[TenantEmailService, Depends(_service)],
):
    creds = payload.credentials.model_dump(exclude_none=True) if payload.credentials else None
    return service.create(
        provider=payload.provider,
        display_name=payload.display_name,
        description=payload.description,
        from_email=payload.from_email,
        from_name=payload.from_name,
        reply_to=payload.reply_to,
        footer_text=payload.footer_text,
        footer_html=payload.footer_html,
        is_active=payload.is_active,
        is_default=payload.is_default,
        sandbox_mode=payload.sandbox_mode,
        smtp_host=payload.smtp_host,
        smtp_port=payload.smtp_port,
        smtp_security=payload.smtp_security,
        smtp_username=payload.smtp_username,
        api_base_url=payload.api_base_url,
        api_region=payload.api_region,
        api_domain=payload.api_domain,
        credentials=creds,
    )


@router.put(
    "/{config_id}",
    response_model=EmailConfigReadSchema,
    summary="Update an email configuration",
)
def update_email_config(
    config_id: int,
    payload: EmailConfigUpdateSchema,
    _: AdminUser,
    service: Annotated[TenantEmailService, Depends(_service)],
):
    creds = payload.credentials.model_dump(exclude_none=True) if payload.credentials else None
    return service.update(
        config_id,
        provider=payload.provider,
        display_name=payload.display_name,
        description=payload.description,
        from_email=payload.from_email,
        from_name=payload.from_name,
        reply_to=payload.reply_to,
        footer_text=payload.footer_text,
        footer_html=payload.footer_html,
        is_active=payload.is_active,
        is_default=payload.is_default,
        sandbox_mode=payload.sandbox_mode,
        smtp_host=payload.smtp_host,
        smtp_port=payload.smtp_port,
        smtp_security=payload.smtp_security,
        smtp_username=payload.smtp_username,
        api_base_url=payload.api_base_url,
        api_region=payload.api_region,
        api_domain=payload.api_domain,
        credentials=creds,
    )


@router.delete(
    "/{config_id}",
    status_code=status.HTTP_200_OK,
    summary="Soft-delete an email configuration",
)
def delete_email_config(
    config_id: int,
    _: AdminUser,
    service: Annotated[TenantEmailService, Depends(_service)],
):
    service.delete(config_id)
    return {"success": True}


@router.post(
    "/{config_id}/test",
    summary="Validate credentials and (for SMTP) attempt a connection",
)
def test_email_config(
    config_id: int,
    _: AdminUser,
    service: Annotated[TenantEmailService, Depends(_service)],
):
    return service.test_config(config_id)


@router.post(
    "/{config_id}/send-test",
    summary="Send a real test email to the requesting admin",
)
def send_test_email(
    config_id: int,
    payload: SendTestEmailSchema,
    actor: AdminUser,
    service: Annotated[TenantEmailService, Depends(_service)],
):
    config = service.get(config_id)
    sent = service.send_email(
        config=config,
        subject=payload.subject,
        recipients=[payload.recipient or actor.email],
        body_text=payload.body_text,
        body_html=payload.body_html,
    )
    return {"sent": sent, "recipient": payload.recipient}
