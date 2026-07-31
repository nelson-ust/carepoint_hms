# app/api/v1/endpoints/integration_routes.py
from __future__ import annotations

"""
Integration partner management + outbound calls (staff/admin, JWT-authed).
Inbound API-key endpoints live in integration_public_routes.py.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.dependencies import AdminUser
from app.core.exceptions import BadRequestError
from app.core.multitenancy import get_current_tenant_id
from app.schemas.integration_schemas import (
    OutboundRequestSchema,
    PartnerCreateSchema,
    PartnerUpdateSchema,
)
from app.services.integration_service import IntegrationService

router = APIRouter(prefix="/integration", tags=["Integrations"])


def _tenant_id() -> int:
    tid = get_current_tenant_id()
    if not tid:
        raise BadRequestError(message="A tenant context is required to manage integrations.")
    return tid


@router.post("/partners", status_code=status.HTTP_201_CREATED, summary="Register a third-party integration partner")
def create_partner(payload: PartnerCreateSchema, actor: AdminUser):
    tenant_id = _tenant_id()
    partner, api_key = IntegrationService().create_partner(
        tenant_id=tenant_id, name=payload.name, description=payload.description,
        scopes=payload.scopes, expiry_days=payload.expiry_days, base_url=payload.base_url,
        auth_header=payload.auth_header, auth_secret=payload.auth_secret,
        created_by_user_id=getattr(actor, "id", None),
    )
    return {"success": True, "message": "Integration partner created. Copy the API key now — it won't be shown again.",
            "partner": partner, "api_key": api_key}


@router.get("/partners", summary="List integration partners")
def list_partners(actor: AdminUser):
    return {"success": True, "items": IntegrationService().list_partners(tenant_id=_tenant_id())}


@router.patch("/partners/{partner_id}", summary="Update an integration partner")
def update_partner(partner_id: int, payload: PartnerUpdateSchema, actor: AdminUser):
    partner = IntegrationService().update_partner(
        partner_id=partner_id, tenant_id=_tenant_id(),
        changes=payload.model_dump(exclude_unset=True),
    )
    return {"success": True, "message": "Partner updated.", "partner": partner}


@router.post("/partners/{partner_id}/rotate-key", summary="Rotate a partner's API key")
def rotate_key(partner_id: int, actor: AdminUser):
    partner, api_key = IntegrationService().rotate_key(partner_id=partner_id, tenant_id=_tenant_id())
    return {"success": True, "message": "API key rotated. The previous key is now invalid.",
            "partner": partner, "api_key": api_key}


@router.delete("/partners/{partner_id}", summary="Revoke (deactivate) an integration partner")
def revoke_partner(partner_id: int, actor: AdminUser):
    partner = IntegrationService().revoke_partner(partner_id=partner_id, tenant_id=_tenant_id())
    return {"success": True, "message": "Partner revoked.", "partner": partner}


@router.post("/partners/{partner_id}/request", summary="Call the partner's endpoint (outbound)")
def outbound_request(partner_id: int, payload: OutboundRequestSchema, actor: AdminUser):
    result = IntegrationService().outbound_request(
        partner_id=partner_id, tenant_id=_tenant_id(), path=payload.path,
        method=payload.method, params=payload.params, payload=payload.payload,
    )
    return {"success": True, "result": result}
