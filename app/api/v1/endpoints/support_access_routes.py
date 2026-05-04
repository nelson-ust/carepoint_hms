"""
Endpoints for managing support-access grants between platform admins and
tenants.

Two audiences:

* SaaS admins (``request_grant``, ``list_my_grants``)
* SUPER_ADMIN / SUPPORT_ADMIN (``list_all_grants``, ``approve_grant``,
  ``revoke_grant``)

All actions are persisted in the master DB and timestamped so support
sessions are fully auditable.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_master_db
from app.core.dependencies import CurrentSaaSAdmin
from app.core.enums import SupportAccessStatus
from app.dependencies.auth import (
    require_saas_role,
    require_saas_super_admin,
    require_saas_support_admin,
)
from app.models.all_models import SaaSAdmin
from app.services.support_access_service import SupportAccessService


router = APIRouter(prefix="/support-access", tags=["SaaS - Support Access"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GrantRequestSchema(BaseModel):
    tenant_id: int
    reason: str = Field(..., min_length=10, max_length=500)
    valid_hours: int = Field(4, ge=1, le=24 * 7)
    permissions: list[str] = Field(default_factory=lambda: ["read"])


class GrantApproveSchema(BaseModel):
    approver_user_id: Optional[int] = None


class GrantReadSchema(BaseModel):
    id: int
    saas_admin_id: int
    tenant_id: int
    reason: str
    status: SupportAccessStatus
    valid_from: datetime
    valid_until: datetime
    approved_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    permissions: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


def _service(db: Annotated[Session, Depends(get_master_db)]) -> SupportAccessService:
    return SupportAccessService(db)


# ---------------------------------------------------------------------------
# Routes — admin self-service
# ---------------------------------------------------------------------------


@router.post(
    "/request",
    response_model=GrantReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Request a support-access grant for a tenant",
)
def request_grant(
    payload: GrantRequestSchema,
    current_admin: CurrentSaaSAdmin,
    service: Annotated[SupportAccessService, Depends(_service)],
):
    return service.request_grant(
        admin=current_admin,
        tenant_id=payload.tenant_id,
        reason=payload.reason,
        valid_hours=payload.valid_hours,
        permissions=payload.permissions,
    )


@router.get(
    "/me",
    response_model=list[GrantReadSchema],
    summary="List my support-access grants",
)
def list_my_grants(
    current_admin: CurrentSaaSAdmin,
    service: Annotated[SupportAccessService, Depends(_service)],
    grant_status: Optional[SupportAccessStatus] = None,
):
    return service.list_grants(admin_id=current_admin.id, status=grant_status)


# ---------------------------------------------------------------------------
# Routes — superuser / support admin
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[GrantReadSchema],
    summary="List all support-access grants",
)
def list_all_grants(
    _admin: Annotated[SaaSAdmin, Depends(require_saas_support_admin)],
    service: Annotated[SupportAccessService, Depends(_service)],
    tenant_id: Optional[int] = None,
    admin_id: Optional[int] = None,
    grant_status: Optional[SupportAccessStatus] = None,
):
    return service.list_grants(
        tenant_id=tenant_id,
        admin_id=admin_id,
        status=grant_status,
    )


@router.post(
    "/{grant_id}/approve",
    response_model=GrantReadSchema,
    summary="Approve a pending support-access grant",
)
def approve_grant(
    grant_id: int,
    payload: GrantApproveSchema,
    _admin: Annotated[SaaSAdmin, Depends(require_saas_super_admin)],
    service: Annotated[SupportAccessService, Depends(_service)],
):
    return service.approve_grant(grant_id, approver_user_id=payload.approver_user_id)


@router.post(
    "/{grant_id}/revoke",
    response_model=GrantReadSchema,
    summary="Revoke an active support-access grant",
)
def revoke_grant(
    grant_id: int,
    _admin: Annotated[SaaSAdmin, Depends(require_saas_support_admin)],
    service: Annotated[SupportAccessService, Depends(_service)],
):
    return service.revoke_grant(grant_id)


@router.post(
    "/sweep",
    summary="Expire all due support-access grants",
)
def sweep_expired(
    _admin: Annotated[SaaSAdmin, Depends(require_saas_super_admin)],
    service: Annotated[SupportAccessService, Depends(_service)],
):
    expired = service.expire_due_grants()
    return {"success": True, "expired": expired}
