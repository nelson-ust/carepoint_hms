"""
Edge-node management + sync endpoints.

Three audiences:

* **SaaS / tenant administrator** — register, rotate, list, decommission
  edge nodes. Authenticated with the regular Bearer JWT.
* **Edge node itself** — calls /sync/* with its own bearer token
  (issued at registration time, hashed at rest).
* **Frontend / clients on the LAN** — call /connectivity/probe to decide
  whether to talk to the cloud or the local edge node.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Body, Depends, Header, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_master_db
from app.core.dependencies import CurrentSaaSAdmin
from app.core.enums import EdgeNodeStatus, SyncJournalOp
from app.core.exceptions import ForbiddenError
from app.models.all_models import EdgeNode
from app.services.edge_sync_service import (
    EdgeNodeService,
    EdgeSyncService,
    authenticate_edge_node,
    record_heartbeat,
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/edge-nodes", tags=["SaaS - Edge Nodes"])
sync_router = APIRouter(prefix="/sync", tags=["Edge Sync"])
connectivity_router = APIRouter(prefix="/connectivity", tags=["Connectivity"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class EdgeNodeCreateSchema(BaseModel):
    tenant_id: int
    code: str = Field(..., min_length=2, max_length=120)
    display_name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None
    public_url: Optional[str] = None
    facility_id: Optional[int] = None
    heartbeat_interval_seconds: int = Field(300, ge=30, le=3600)
    heartbeat_grace_seconds: int = Field(900, ge=60, le=86400)


class EdgeNodeReadSchema(BaseModel):
    id: int
    tenant_id: int
    code: str
    display_name: str
    description: Optional[str] = None
    public_url: Optional[str] = None
    facility_id: Optional[int] = None
    status: EdgeNodeStatus
    app_version: Optional[str] = None
    schema_version: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    last_pulled_at: Optional[datetime] = None
    last_pushed_at: Optional[datetime] = None
    last_pull_cursor: Optional[int] = None
    last_push_cursor: Optional[int] = None
    last_failure_reason: Optional[str] = None
    heartbeat_interval_seconds: int
    heartbeat_grace_seconds: int

    model_config = ConfigDict(from_attributes=True)


class EdgeNodeWithTokenSchema(BaseModel):
    node: EdgeNodeReadSchema
    token: str


class HandshakeSchema(BaseModel):
    app_version: Optional[str] = None
    schema_version: Optional[str] = None


class PushRowSchema(BaseModel):
    client_uuid: str
    entity_type: str
    entity_id: Optional[int] = None
    op: SyncJournalOp
    payload: Optional[dict[str, Any]] = None
    occurred_at: Optional[datetime] = None


class PushBatchSchema(BaseModel):
    rows: list[PushRowSchema]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _service(db: Annotated[Session, Depends(get_master_db)]) -> EdgeNodeService:
    return EdgeNodeService(db)


def get_current_edge_node(
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> EdgeNode:
    """
    Resolve the edge node from the ``Authorization: Bearer <token>``
    header. Used by the /sync/* endpoints.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ForbiddenError(message="Edge-node bearer token required.")
    token = authorization.split(" ", 1)[1].strip()
    return authenticate_edge_node(token)


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------


@admin_router.get(
    "",
    response_model=list[EdgeNodeReadSchema],
    summary="List edge nodes",
)
def list_edge_nodes(
    _: CurrentSaaSAdmin,
    service: Annotated[EdgeNodeService, Depends(_service)],
    tenant_id: Optional[int] = None,
):
    return service.list_nodes(tenant_id=tenant_id)


@admin_router.post(
    "",
    response_model=EdgeNodeWithTokenSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Provision a new edge node (returns plaintext token ONCE)",
)
def register_edge_node(
    payload: EdgeNodeCreateSchema,
    _: CurrentSaaSAdmin,
    service: Annotated[EdgeNodeService, Depends(_service)],
):
    node, token = service.register(
        tenant_id=payload.tenant_id,
        code=payload.code,
        display_name=payload.display_name,
        description=payload.description,
        public_url=payload.public_url,
        facility_id=payload.facility_id,
        heartbeat_interval_seconds=payload.heartbeat_interval_seconds,
        heartbeat_grace_seconds=payload.heartbeat_grace_seconds,
    )
    return {"node": node, "token": token}


@admin_router.post(
    "/{node_id}/rotate-token",
    response_model=EdgeNodeWithTokenSchema,
    summary="Rotate the edge-node bearer token",
)
def rotate_edge_node_token(
    node_id: int,
    _: CurrentSaaSAdmin,
    service: Annotated[EdgeNodeService, Depends(_service)],
):
    node, token = service.rotate_token(node_id)
    return {"node": node, "token": token}


@admin_router.post(
    "/{node_id}/decommission",
    response_model=EdgeNodeReadSchema,
    summary="Decommission an edge node",
)
def decommission_edge_node(
    node_id: int,
    _: CurrentSaaSAdmin,
    service: Annotated[EdgeNodeService, Depends(_service)],
):
    return service.decommission(node_id)


# ---------------------------------------------------------------------------
# Edge-node sync routes
# ---------------------------------------------------------------------------


@sync_router.post(
    "/handshake",
    response_model=EdgeNodeReadSchema,
    summary="Edge-node heartbeat / version handshake",
)
def edge_handshake(
    payload: HandshakeSchema = Body(default_factory=HandshakeSchema),
    node: EdgeNode = Depends(get_current_edge_node),
):
    return record_heartbeat(
        node,
        app_version=payload.app_version,
        schema_version=payload.schema_version,
    )


@sync_router.get(
    "/pull",
    summary="Pull cloud-authored journal rows since cursor",
)
def edge_pull(
    cursor: int = 0,
    limit: int = 500,
    node: EdgeNode = Depends(get_current_edge_node),
):
    return EdgeSyncService(node).pull(cursor=cursor, limit=limit)


@sync_router.post(
    "/push",
    summary="Push edge-authored journal rows to the cloud",
)
def edge_push(
    payload: PushBatchSchema,
    node: EdgeNode = Depends(get_current_edge_node),
):
    return EdgeSyncService(node).push(
        [r.model_dump() for r in payload.rows]
    )


# ---------------------------------------------------------------------------
# Connectivity probe (public)
# ---------------------------------------------------------------------------


@connectivity_router.get(
    "/probe",
    summary="Lightweight connectivity probe for offline-aware clients",
)
def connectivity_probe():
    """
    Always returns 200 OK with a tiny payload so the frontend can decide
    whether to use the cloud endpoint or its on-LAN edge node. The
    payload also carries the server time so clients can detect clock
    drift before queuing offline writes.
    """
    return {
        "ok": True,
        "server_time": datetime.utcnow().isoformat() + "Z",
        "supports_offline_sync": True,
    }
