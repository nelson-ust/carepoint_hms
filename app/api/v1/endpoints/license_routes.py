# app/api/v1/endpoints/license_routes.py
from __future__ import annotations

"""
Licensing routes for offline (edge) hospitals.

* GET  /licenses/status   — current lease posture (for the licence banner).
* POST /licenses/refresh  — pull a fresh lease from the cloud (when online).
* POST /licenses/activate — upload a signed lease by hand (air-gapped sites).
* POST /licenses/issue    — SIGN a lease (cloud licence-authority only).
"""

from typing import Annotated, Optional

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.core.dependencies import AdminUser, CurrentActiveUser, CurrentSaaSAdmin
from app.core.exceptions import BadRequestError
from app.services import entitlement_service

router = APIRouter(prefix="/licenses", tags=["Licensing"])


class ActivateSchema(BaseModel):
    token: str = Field(..., min_length=16, description="Signed licence lease (JWT).")


class IssueSchema(BaseModel):
    tenant: str
    plan: str = "standard"
    modules: list[str] = Field(default_factory=list)
    lease_days: Optional[int] = None
    grace_days: Optional[int] = None
    node_id: Optional[str] = None


@router.get("/status", summary="Current licence posture for this install")
def license_status_route(_: CurrentActiveUser):
    return entitlement_service.status()


@router.post("/refresh", summary="Pull a fresh lease from the cloud (when online)")
def refresh_license(_: AdminUser):
    return entitlement_service.refresh_from_cloud()


@router.post("/activate", summary="Activate a signed lease uploaded by hand (air-gapped sites)")
def activate_license(payload: ActivateSchema, _: AdminUser):
    try:
        entitlement_service.install_token(payload.token)
    except Exception as exc:
        raise BadRequestError(message=f"Licence could not be verified: {exc}")
    return entitlement_service.status()


@router.post("/issue", status_code=status.HTTP_201_CREATED,
             summary="Sign a lease (cloud licence-authority only)")
def issue_license(payload: IssueSchema, _: CurrentSaaSAdmin):
    try:
        token = entitlement_service.sign_lease(
            tenant=payload.tenant, plan=payload.plan, modules=payload.modules,
            lease_days=payload.lease_days, grace_days=payload.grace_days, node_id=payload.node_id,
        )
    except RuntimeError as exc:
        raise BadRequestError(message=str(exc))
    return {"token": token}
