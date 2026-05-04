"""
Endpoints for managing tenant custom domains and SSL/verification status.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_master_db
from app.core.dependencies import CurrentSaaSAdmin
from app.services.tenant_domain_service import TenantDomainService


router = APIRouter(prefix="/tenant-domains", tags=["SaaS - Tenant Domains"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DomainReadSchema(BaseModel):
    id: int
    tenant_id: int
    domain_name: str
    is_primary: bool
    is_verified: bool
    verified_at: Optional[datetime] = None
    ssl_status: str
    ssl_provider: Optional[str] = None
    ssl_issued_at: Optional[datetime] = None
    ssl_expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DomainAddSchema(BaseModel):
    domain_name: str = Field(..., examples=["portal.acmeclinic.com"])
    is_primary: bool = False


class SSLStatusUpdateSchema(BaseModel):
    ssl_status: str
    ssl_provider: Optional[str] = None
    ssl_issued_at: Optional[datetime] = None
    ssl_expires_at: Optional[datetime] = None


def _service(db: Session = Depends(get_master_db)) -> TenantDomainService:
    return TenantDomainService(db)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "/{tenant_id}",
    summary="List all domains for a tenant",
    response_model=list[DomainReadSchema],
)
def list_domains(
    tenant_id: int,
    _: CurrentSaaSAdmin,
    service: Annotated[TenantDomainService, Depends(_service)],
):
    return service.list_domains(tenant_id)


@router.post(
    "/{tenant_id}",
    summary="Register a new custom domain for a tenant",
    response_model=DomainReadSchema,
    status_code=status.HTTP_201_CREATED,
)
def add_domain(
    tenant_id: int,
    payload: DomainAddSchema,
    _: CurrentSaaSAdmin,
    service: Annotated[TenantDomainService, Depends(_service)],
):
    return service.add_domain(
        tenant_id,
        payload.domain_name,
        is_primary=payload.is_primary,
    )


@router.get(
    "/{tenant_id}/{domain_id}/verification",
    summary="Get DNS verification instructions for a domain",
)
def get_verification_instructions(
    tenant_id: int,
    domain_id: int,
    _: CurrentSaaSAdmin,
    service: Annotated[TenantDomainService, Depends(_service)],
):
    return service.get_verification_instructions(tenant_id, domain_id)


@router.post(
    "/{tenant_id}/{domain_id}/verify",
    summary="Run domain verification",
    response_model=DomainReadSchema,
)
def verify_domain(
    tenant_id: int,
    domain_id: int,
    _: CurrentSaaSAdmin,
    service: Annotated[TenantDomainService, Depends(_service)],
):
    return service.verify_domain(tenant_id, domain_id)


@router.post(
    "/{tenant_id}/{domain_id}/make-primary",
    summary="Mark a verified domain as primary",
    response_model=DomainReadSchema,
)
def make_primary(
    tenant_id: int,
    domain_id: int,
    _: CurrentSaaSAdmin,
    service: Annotated[TenantDomainService, Depends(_service)],
):
    return service.make_primary(tenant_id, domain_id)


@router.delete(
    "/{tenant_id}/{domain_id}",
    summary="Remove a non-primary domain",
    status_code=status.HTTP_200_OK,
)
def remove_domain(
    tenant_id: int,
    domain_id: int,
    _: CurrentSaaSAdmin,
    service: Annotated[TenantDomainService, Depends(_service)],
):
    service.remove_domain(tenant_id, domain_id)
    return {"success": True}


@router.put(
    "/{tenant_id}/{domain_id}/ssl",
    summary="Update SSL status for a domain (used by ACME automation)",
    response_model=DomainReadSchema,
)
def update_ssl_status(
    tenant_id: int,
    domain_id: int,
    payload: SSLStatusUpdateSchema,
    _: CurrentSaaSAdmin,
    service: Annotated[TenantDomainService, Depends(_service)],
):
    return service.update_ssl_status(
        tenant_id,
        domain_id,
        ssl_status=payload.ssl_status,
        ssl_provider=payload.ssl_provider,
        ssl_issued_at=payload.ssl_issued_at,
        ssl_expires_at=payload.ssl_expires_at,
    )
