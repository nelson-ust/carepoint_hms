"""
Endpoints for managing per-tenant module access.

Two role groups can manage modules:

* SaaS administrators (``CurrentSaaSAdmin``) — for any tenant.
* Tenant superusers via the ``/me/...`` endpoints — only for their own tenant.
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.core.database import get_master_db
from app.core.dependencies import CurrentSaaSAdmin
from app.core.exceptions import ForbiddenError
from app.core.multitenancy import get_current_tenant_id
from app.dependencies.auth import get_current_active_user
from app.models.all_models import User
from app.services.tenant_module_service import (
    SUPPORTED_MODULES,
    TenantModuleService,
)


router = APIRouter(prefix="/tenant-modules", tags=["SaaS - Tenant Modules"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ModuleAccessSchema(BaseModel):
    code: str
    label: str
    plan_default: bool
    override: Optional[bool] = None
    effective: bool
    notes: Optional[str] = None


class ModuleSetSchema(BaseModel):
    module_code: str = Field(..., examples=["pharmacy"])
    is_enabled: bool = True
    notes: Optional[str] = None


class BulkModuleSetSchema(BaseModel):
    modules: list[ModuleSetSchema]

    @model_validator(mode="before")
    @classmethod
    def _accept_bare_list(cls, data):
        # Tolerate clients that POST a bare array ([...]) as well as the
        # documented object wrapper ({"modules": [...]}).
        if isinstance(data, list):
            return {"modules": data}
        return data


class FacilityProfileSchema(BaseModel):
    code: str
    label: str
    workspace_name: str
    home: str
    description: str
    modules: list[str] = []
    is_default: bool = False


class CurrentProfileSchema(BaseModel):
    code: str
    label: str
    workspace_name: str
    home: str
    description: str


class ApplyProfileSchema(BaseModel):
    profile: str = Field(..., examples=["DENTAL"])


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


@router.get(
    "/catalog",
    summary="List supported module codes",
)
def list_module_catalog():
    return {
        "modules": [{"code": code, "label": label} for code, label in SUPPORTED_MODULES],
    }


@router.get(
    "/profiles",
    summary="List selectable facility profiles (verticals)",
    response_model=list[FacilityProfileSchema],
)
def list_facility_profiles(
    _current_user: Annotated[User, Depends(get_current_active_user)],
):
    return TenantModuleService.list_profiles()


@router.put(
    "/{tenant_id}/profile",
    summary="Apply a facility profile to a tenant (SaaS admin)",
)
def apply_facility_profile_for_tenant(
    tenant_id: int,
    payload: ApplyProfileSchema,
    _: CurrentSaaSAdmin,
    service: Annotated[TenantModuleService, Depends(_service)],
):
    result = service.apply_profile(tenant_id, payload.profile)
    return {"success": True, **result}


# ---------------------------------------------------------------------------
# SaaS-admin scoped (manage any tenant)
# ---------------------------------------------------------------------------


def _service(db: Session = Depends(get_master_db)) -> TenantModuleService:
    return TenantModuleService(db)


@router.get(
    "/{tenant_id}",
    summary="List effective modules for a tenant",
    response_model=list[ModuleAccessSchema],
)
def list_modules_for_tenant(
    tenant_id: int,
    _: CurrentSaaSAdmin,
    service: Annotated[TenantModuleService, Depends(_service)],
):
    return service.list_modules_for_tenant(tenant_id)


@router.put(
    "/{tenant_id}",
    summary="Set a single module override for a tenant",
    status_code=status.HTTP_200_OK,
)
def set_module_for_tenant(
    tenant_id: int,
    payload: ModuleSetSchema,
    _: CurrentSaaSAdmin,
    service: Annotated[TenantModuleService, Depends(_service)],
):
    record = service.set_module(
        tenant_id,
        payload.module_code,
        is_enabled=payload.is_enabled,
        notes=payload.notes,
    )
    return {
        "success": True,
        "module": record.module_code,
        "is_enabled": record.is_enabled,
    }


@router.put(
    "/{tenant_id}/bulk",
    summary="Bulk update module overrides for a tenant",
)
def bulk_set_modules_for_tenant(
    tenant_id: int,
    payload: BulkModuleSetSchema,
    _: CurrentSaaSAdmin,
    service: Annotated[TenantModuleService, Depends(_service)],
):
    records = service.bulk_set_modules(
        tenant_id,
        [m.model_dump() for m in payload.modules],
    )
    return {
        "success": True,
        "updated": [{"module": r.module_code, "is_enabled": r.is_enabled} for r in records],
    }


@router.delete(
    "/{tenant_id}/{module_code}",
    summary="Reset a module override (fall back to plan default)",
    status_code=status.HTTP_200_OK,
)
def reset_module_for_tenant(
    tenant_id: int,
    module_code: str,
    _: CurrentSaaSAdmin,
    service: Annotated[TenantModuleService, Depends(_service)],
):
    service.reset_module(tenant_id, module_code)
    return {"success": True, "module": module_code}


# ---------------------------------------------------------------------------
# Tenant-self-service (current tenant only)
# ---------------------------------------------------------------------------


@router.get(
    "/me/list",
    summary="List effective modules for the current tenant",
    response_model=list[ModuleAccessSchema],
)
def list_my_tenant_modules(
    current_user: Annotated[User, Depends(get_current_active_user)],
    service: Annotated[TenantModuleService, Depends(_service)],
):
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        return []
    return service.list_modules_for_tenant(tenant_id)


@router.get(
    "/me/profile",
    summary="Current tenant's facility profile",
    response_model=CurrentProfileSchema,
)
def get_my_facility_profile(
    _current_user: Annotated[User, Depends(get_current_active_user)],
    service: Annotated[TenantModuleService, Depends(_service)],
):
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        # No tenant context (e.g. SaaS admin) -> report the default profile.
        return {
            "code": "HOSPITAL",
            "label": "Integrated Hospital",
            "workspace_name": "Hospital Workspace",
            "home": "dashboard",
            "description": "Full multi-department hospital.",
        }
    return service.get_profile_for_tenant(tenant_id)

