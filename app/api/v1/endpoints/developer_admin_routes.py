# app/api/v1/endpoints/developer_admin_routes.py
from __future__ import annotations

"""
Tenant-admin governance of the developer platform (JWT-authed).

A hospital administrator reviews which developers requested access to *their*
data and approves / revokes those grants. Platform-wide developer-account
oversight (suspend / reactivate) is also here, gated by the same permission.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import require_permission
from app.core.exceptions import BadRequestError
from app.core.multitenancy import get_current_tenant_id
from app.models.all_models import User
from app.schemas.developer_schemas import (
    AccountStatusSchema,
    GrantDecisionSchema,
    GrantRevokeSchema,
)
from app.services.developer_service import DeveloperService

router = APIRouter(prefix="/admin/developer", tags=["Developer Platform (admin)"])

DevAdmin = Annotated[User, Depends(require_permission("DEVELOPER_ACCESS_MANAGE"))]


def _tenant_id() -> int:
    tid = get_current_tenant_id()
    if not tid:
        raise BadRequestError(message="A tenant context is required.")
    return tid


@router.get("/grants", summary="Developer data grants awaiting or affecting this hospital")
def list_grants(actor: DevAdmin, status: Optional[str] = Query(None, description="PENDING/APPROVED/DENIED/REVOKED")):
    return {"success": True, "items": DeveloperService().list_grants_for_tenant(
        tenant_id=_tenant_id(), status=status)}


@router.post("/grants/{grant_id}/decision", summary="Approve or deny a developer data grant")
def decide_grant(grant_id: int, payload: GrantDecisionSchema, actor: DevAdmin):
    grant = DeveloperService().decide_grant(
        grant_id=grant_id, tenant_id=_tenant_id(), approve=payload.approve,
        approved_scopes=payload.approved_scopes, note=payload.note,
        user_id=getattr(actor, "id", None),
    )
    return {"success": True, "message": "Decision recorded.", "grant": grant}


@router.post("/grants/{grant_id}/revoke", summary="Revoke a previously approved grant")
def revoke_grant(grant_id: int, payload: GrantRevokeSchema, actor: DevAdmin):
    grant = DeveloperService().revoke_grant(
        grant_id=grant_id, tenant_id=_tenant_id(),
        user_id=getattr(actor, "id", None), note=payload.note,
    )
    return {"success": True, "message": "Grant revoked.", "grant": grant}


@router.get("/accounts", summary="List registered developer accounts")
def list_accounts(actor: DevAdmin, status: Optional[str] = Query(None)):
    return {"success": True, "items": DeveloperService().list_accounts(status=status)}


@router.post("/accounts/{account_id}/status", summary="Suspend or reactivate a developer account")
def set_status(account_id: int, payload: AccountStatusSchema, actor: DevAdmin):
    acct = DeveloperService().set_account_status(
        account_id=account_id, active=payload.active, reason=payload.reason,
        user_id=getattr(actor, "id", None),
    )
    return {"success": True, "message": "Account updated.", "account": acct}
