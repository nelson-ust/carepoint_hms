"""
Audit-log read endpoints.

- Tenant admins read their tenant's audit trail at ``/api/v1/audit-logs``.
- SaaS admins read the platform audit trail at ``/api/v1/saas/audit-logs``.

Both are read-only; entries are written by the audit middleware and the auth
services. Results are newest-first and paginated.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db, get_master_db
from app.core.dependencies import CurrentSaaSSuperuser, require_permission
from app.services import audit_service


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AuditLogReadSchema(BaseModel):
    id: int
    action: str
    entity_name: str
    entity_id: Optional[int] = None
    actor_user_id: Optional[int] = None
    actor_label: Optional[str] = None
    actor_type: Optional[str] = None
    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    http_method: Optional[str] = None
    path: Optional[str] = None
    status_code: Optional[int] = None
    before_data: Optional[dict[str, Any]] = None
    after_data: Optional[dict[str, Any]] = None
    extra_metadata: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SaaSAuditLogReadSchema(BaseModel):
    id: int
    action: str
    entity_name: str
    entity_id: Optional[int] = None
    actor_admin_id: Optional[int] = None
    actor_label: Optional[str] = None
    actor_type: Optional[str] = None
    target_tenant_id: Optional[int] = None
    target_tenant_code: Optional[str] = None
    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    http_method: Optional[str] = None
    path: Optional[str] = None
    status_code: Optional[int] = None
    before_data: Optional[dict[str, Any]] = None
    after_data: Optional[dict[str, Any]] = None
    extra_metadata: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    items: list[AuditLogReadSchema]
    total: int
    limit: int
    offset: int


class SaaSAuditLogListResponse(BaseModel):
    items: list[SaaSAuditLogReadSchema]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Tenant audit router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/audit-logs", tags=["Audit Log"])


@router.get("", response_model=AuditLogListResponse, summary="List tenant audit logs")
def list_tenant_audit_logs(
    _: Annotated[Any, Depends(require_permission("AUDIT_READ"))],
    db: Annotated[Session, Depends(get_db)],
    action: Optional[str] = Query(None),
    entity_name: Optional[str] = Query(None),
    actor_user_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None, description="Search action/entity/actor/IP/path"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    rows, total = audit_service.list_tenant_audit_logs(
        db,
        action=action,
        entity_name=entity_name,
        actor_user_id=actor_user_id,
        q=q,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return AuditLogListResponse(items=rows, total=total, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# SaaS / platform audit router
# ---------------------------------------------------------------------------

saas_router = APIRouter(prefix="/saas/audit-logs", tags=["SaaS Admin - Audit Log"])


@saas_router.get("", response_model=SaaSAuditLogListResponse, summary="List platform audit logs")
def list_saas_audit_logs(
    _: CurrentSaaSSuperuser,
    master_db: Annotated[Session, Depends(get_master_db)],
    action: Optional[str] = Query(None),
    entity_name: Optional[str] = Query(None),
    actor_admin_id: Optional[int] = Query(None),
    target_tenant_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    rows, total = audit_service.list_saas_audit_logs(
        master_db,
        action=action,
        entity_name=entity_name,
        actor_admin_id=actor_admin_id,
        target_tenant_code=target_tenant_code,
        q=q,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return SaaSAuditLogListResponse(items=rows, total=total, limit=limit, offset=offset)
