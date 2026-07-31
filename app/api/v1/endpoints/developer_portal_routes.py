# app/api/v1/endpoints/developer_portal_routes.py
from __future__ import annotations

"""
Developer self-service portal (authenticated by the dashboard token).

The developer manages apps + API keys and requests data-access grants from
hospitals. No patient data flows through here.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies.developer_auth import require_developer_dashboard
from app.schemas.developer_schemas import (
    AppCreateSchema,
    AppScopesSchema,
    GrantRequestSchema,
)
from app.services.developer_service import DEVELOPER_SCOPES, DeveloperService

router = APIRouter(prefix="/developer/portal", tags=["Developer Platform (portal)"])

DevAccount = Annotated[dict, Depends(require_developer_dashboard)]


@router.get("/me", summary="Current developer account + apps")
def me(account: DevAccount):
    return {"success": True, "account": DeveloperService().me(account_id=account["id"])}


@router.get("/scopes", summary="Scope catalog")
def scopes(account: DevAccount):
    return {"success": True, "scopes": [{"code": k, "description": v} for k, v in DEVELOPER_SCOPES.items()]}


@router.get("/apps", summary="List apps / API keys")
def list_apps(account: DevAccount):
    return {"success": True, "items": DeveloperService().list_apps(account_id=account["id"])}


@router.post("/apps", status_code=status.HTTP_201_CREATED, summary="Create an app + API key")
def create_app(payload: AppCreateSchema, account: DevAccount):
    app = DeveloperService().create_app(
        account_id=account["id"], name=payload.name,
        environment=payload.environment, scopes=payload.scopes,
    )
    return {"success": True,
            "message": "App created. Copy the API key now — it is shown only once.",
            "app": app}


@router.patch("/apps/{app_id}/scopes", summary="Update an app's requested scopes")
def update_scopes(app_id: int, payload: AppScopesSchema, account: DevAccount):
    app = DeveloperService().update_app_scopes(
        app_id=app_id, account_id=account["id"], scopes=payload.scopes)
    return {"success": True, "app": app}


@router.post("/apps/{app_id}/rotate-key", summary="Rotate an app's API key")
def rotate_key(app_id: int, account: DevAccount):
    app = DeveloperService().rotate_key(app_id=app_id, account_id=account["id"])
    return {"success": True,
            "message": "Key rotated. Copy the new API key now — the old one no longer works.",
            "app": app}


@router.post("/apps/{app_id}/revoke", summary="Revoke an app's API key")
def revoke_app(app_id: int, account: DevAccount):
    app = DeveloperService().revoke_app(app_id=app_id, account_id=account["id"])
    return {"success": True, "message": "App revoked.", "app": app}


@router.get("/grants", summary="List this developer's data grants")
def list_grants(account: DevAccount):
    return {"success": True, "items": DeveloperService().list_grants(account_id=account["id"])}


@router.post("/grants", status_code=status.HTTP_201_CREATED, summary="Request data access from a hospital")
def request_grant(payload: GrantRequestSchema, account: DevAccount):
    grant = DeveloperService().request_grant(
        account_id=account["id"], app_id=payload.app_id,
        tenant_code=payload.tenant_code, requested_scopes=payload.requested_scopes,
        justification=payload.justification,
    )
    return {"success": True,
            "message": "Access requested. The hospital must approve before data is available.",
            "grant": grant}
