"""
Cloud-side coordinator for on-premises edge nodes.

A hospital deploys an edge node at the facility — typically a small
Linux server on the LAN running the same FastAPI app pointing at a
local PostgreSQL replica of its tenant database. Three kinds of
exchange happen between the cloud and the edge node:

* **Handshake / heartbeat** — the edge announces itself, registers its
  app/schema version, and updates ``last_seen_at``.
* **PULL** — the edge asks "what changed in the cloud since cursor N?"
  The cloud streams forward-only :class:`SyncJournal` rows.
* **PUSH** — the edge sends "here's everything I authored locally
  since the last push"; the cloud applies the rows and acknowledges
  the new cursor.

Authentication is per-node: each :class:`EdgeNode` row carries a SHA-256
hash of its bearer token. The plaintext is shown to the operator only at
provisioning / rotation time.

Conflict policy:

* Append-only events (vitals, dispense, payment, audit logs) are
  de-duplicated by ``client_uuid`` so replaying a partial batch is safe.
* Mutable records use last-writer-wins keyed on ``occurred_at``. The
  losing payload is preserved in ``conflicted_payload`` for the
  reconciliation dashboard.

This service does **not** apply payloads to business tables — that work
is delegated to handlers registered against the journal entity type, so
the sync layer doesn't need to know every model in the system.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.cryptography import decrypt_string
from app.core.database import get_master_db_context
from app.core.enums import (
    EdgeNodeStatus,
    SyncDirection,
    SyncJournalOp,
    SyncJournalStatus,
)
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.all_models import EdgeNode, SyncBatch, SyncJournal, Tenant
from app.services.sync_journal_service import SyncJournalService


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _generate_token() -> str:
    return "edge_" + secrets.token_urlsafe(40)


# ---------------------------------------------------------------------------
# EdgeNode CRUD (master DB)
# ---------------------------------------------------------------------------


class EdgeNodeService:
    """
    SaaS-admin / tenant-admin facing CRUD for edge nodes.

    Operates against the master database.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_nodes(self, *, tenant_id: Optional[int] = None) -> list[EdgeNode]:
        q = self.db.query(EdgeNode).filter(EdgeNode.is_deleted.is_(False))
        if tenant_id is not None:
            q = q.filter(EdgeNode.tenant_id == tenant_id)
        return q.order_by(EdgeNode.id.desc()).all()

    def get(self, node_id: int) -> EdgeNode:
        node = (
            self.db.query(EdgeNode)
            .filter(EdgeNode.id == node_id, EdgeNode.is_deleted.is_(False))
            .first()
        )
        if not node:
            raise NotFoundError(message="Edge node not found.")
        return node

    def register(
        self,
        *,
        tenant_id: int,
        code: str,
        display_name: str,
        description: Optional[str] = None,
        public_url: Optional[str] = None,
        facility_id: Optional[int] = None,
        heartbeat_interval_seconds: int = 300,
        heartbeat_grace_seconds: int = 900,
    ) -> tuple[EdgeNode, str]:
        """
        Provision a new edge node and return the (record, plain_token).

        The plaintext token is shown to the operator exactly once; it is
        only stored hashed.
        """
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise NotFoundError(message="Tenant not found.")

        if (
            self.db.query(EdgeNode)
            .filter(EdgeNode.code == code.strip().lower(), EdgeNode.is_deleted.is_(False))
            .first()
        ):
            raise BadRequestError(message=f"Edge node code '{code}' is already in use.")

        token = _generate_token()
        node = EdgeNode(
            tenant_id=tenant_id,
            facility_id=facility_id,
            code=code.strip().lower(),
            display_name=display_name.strip(),
            description=description,
            public_url=public_url,
            token_hash=_hash_token(token),
            status=EdgeNodeStatus.PROVISIONED,
            heartbeat_interval_seconds=int(heartbeat_interval_seconds),
            heartbeat_grace_seconds=int(heartbeat_grace_seconds),
        )
        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)
        return node, token

    def rotate_token(self, node_id: int) -> tuple[EdgeNode, str]:
        node = self.get(node_id)
        token = _generate_token()
        node.token_hash = _hash_token(token)
        self.db.commit()
        self.db.refresh(node)
        return node, token

    def decommission(self, node_id: int) -> EdgeNode:
        node = self.get(node_id)
        node.status = EdgeNodeStatus.DECOMMISSIONED
        node.is_active = False
        self.db.commit()
        self.db.refresh(node)
        return node


# ---------------------------------------------------------------------------
# Authentication of the edge node itself
# ---------------------------------------------------------------------------


def authenticate_edge_node(token: str) -> EdgeNode:
    """
    Resolve an edge node from its bearer token.

    Used by FastAPI dependencies on the ``/api/v1/sync/*`` routes.
    """
    if not token:
        raise ForbiddenError(message="Edge node token is required.")
    digest = _hash_token(token)
    with get_master_db_context() as db:
        node = (
            db.query(EdgeNode)
            .filter(
                EdgeNode.token_hash == digest,
                EdgeNode.is_deleted.is_(False),
                EdgeNode.is_active.is_(True),
            )
            .first()
        )
        if not node:
            raise ForbiddenError(message="Unknown or revoked edge-node token.")
        if node.status == EdgeNodeStatus.DECOMMISSIONED:
            raise ForbiddenError(message="Edge node has been decommissioned.")
        # Detach from session so the caller doesn't accidentally write to master
        # via the resolved object.
        db.expunge(node)
        return node


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


def record_heartbeat(
    node: EdgeNode,
    *,
    app_version: Optional[str] = None,
    schema_version: Optional[str] = None,
) -> EdgeNode:
    """Update last_seen_at + version metadata on every node call."""
    with get_master_db_context() as db:
        live = db.query(EdgeNode).filter(EdgeNode.id == node.id).first()
        if not live:
            return node
        live.last_seen_at = datetime.now(timezone.utc)
        if app_version:
            live.app_version = app_version
        if schema_version:
            live.schema_version = schema_version
        if live.status == EdgeNodeStatus.OFFLINE:
            live.status = EdgeNodeStatus.ACTIVE
            live.last_failure_reason = None
        elif live.status == EdgeNodeStatus.PROVISIONED:
            live.status = EdgeNodeStatus.ACTIVE
        db.commit()
        db.refresh(live)
        db.expunge(live)
        return live


def sweep_offline_nodes() -> int:
    """
    Flip nodes that have missed their heartbeat window to OFFLINE.
    Designed to run from the platform scheduler every minute.
    """
    flipped = 0
    now = datetime.now(timezone.utc)
    with get_master_db_context() as db:
        nodes = (
            db.query(EdgeNode)
            .filter(
                EdgeNode.status.in_([EdgeNodeStatus.ACTIVE, EdgeNodeStatus.DEGRADED]),
                EdgeNode.is_deleted.is_(False),
            )
            .all()
        )
        for n in nodes:
            grace = timedelta(seconds=int(n.heartbeat_grace_seconds or 900))
            if n.last_seen_at and (now - n.last_seen_at) > grace:
                n.status = EdgeNodeStatus.OFFLINE
                flipped += 1
        if flipped:
            db.commit()
    return flipped


# ---------------------------------------------------------------------------
# Sync exchange
# ---------------------------------------------------------------------------


def _open_tenant_session(tenant_id: int) -> tuple[Session, Engine]:
    """
    Open a tenant-scoped ``Session`` for ``tenant_id``.

    Returns the session paired with the underlying ``Engine`` so the
    caller can ``engine.dispose()`` after closing the session — this
    matters because each call constructs a fresh per-tenant engine
    rather than reusing a pooled one.
    """
    with get_master_db_context() as db:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant or not tenant.db_connection_string:
            raise NotFoundError(message="Tenant database is not provisioned.")
        url = decrypt_string(tenant.db_connection_string)
    engine = create_engine(url, future=True)
    return Session(engine, expire_on_commit=False), engine


class EdgeSyncService:
    """
    Handles the actual cursor-based exchange of journal rows between the
    cloud and an authenticated edge node.
    """

    def __init__(self, node: EdgeNode) -> None:
        self.node = node

    # ------------------------------------------------------------------
    # PULL — cloud sends, edge consumes
    # ------------------------------------------------------------------

    def pull(
        self,
        *,
        cursor: int = 0,
        limit: int = 500,
    ) -> dict[str, Any]:
        """
        Return up to ``limit`` cloud-authored journal rows newer than
        ``cursor``. Rows authored by the requesting node are skipped so
        we don't echo a node's own pushes back at it.
        """
        session, engine = _open_tenant_session(self.node.tenant_id)
        try:
            svc = SyncJournalService(session)
            rows = svc.fetch_since(
                cursor=cursor,
                limit=limit,
                skip_origin=f"edge:{self.node.code}",
            )

            payload = [self._serialize_row(r) for r in rows]
            highest = rows[-1].seq if rows else cursor

            batch = SyncBatch(
                direction=SyncDirection.PULL,
                edge_node_code=self.node.code,
                cursor_from=int(cursor or 0),
                cursor_to=int(highest or cursor or 0),
                record_count=len(rows),
                applied_count=0,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                note=f"pull by edge node {self.node.code}",
            )
            session.add(batch)
            session.commit()
        finally:
            session.close()
            engine.dispose()

        # Update master-side cursor + heartbeat.
        with get_master_db_context() as master_db:
            n = master_db.query(EdgeNode).filter(EdgeNode.id == self.node.id).first()
            if n:
                n.last_pulled_at = datetime.now(timezone.utc)
                n.last_pull_cursor = int(highest or cursor or 0)
                n.last_seen_at = datetime.now(timezone.utc)
                master_db.commit()

        return {
            "node": self.node.code,
            "cursor": int(highest or cursor or 0),
            "count": len(payload),
            "rows": payload,
            "has_more": len(payload) == limit,
        }

    # ------------------------------------------------------------------
    # PUSH — edge sends, cloud applies
    # ------------------------------------------------------------------

    def push(self, rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
        """
        Apply edge-authored rows to the cloud tenant DB.

        Each incoming row must include ``client_uuid``, ``entity_type``,
        ``op``, ``payload`` (optional), and ``occurred_at``. Duplicates
        (already-seen ``client_uuid``) are counted but not applied.
        """
        session, engine = _open_tenant_session(self.node.tenant_id)
        applied = 0
        duplicates = 0
        rejected = 0
        rejected_details: list[dict] = []
        try:
            svc = SyncJournalService(
                session,
                origin=f"edge:{self.node.code}",
                origin_node_id=self.node.id,
            )

            for raw in rows:
                try:
                    op = SyncJournalOp(str(raw.get("op", "")).upper())
                except ValueError:
                    rejected += 1
                    rejected_details.append({"client_uuid": raw.get("client_uuid"), "reason": "invalid op"})
                    continue

                cuid = raw.get("client_uuid")
                if not cuid:
                    rejected += 1
                    rejected_details.append({"reason": "missing client_uuid"})
                    continue

                # Idempotency: skip if we already have this client_uuid.
                exists = (
                    session.query(SyncJournal)
                    .filter(SyncJournal.client_uuid == cuid)
                    .first()
                )
                if exists is not None:
                    duplicates += 1
                    continue

                rec = svc.record_change(
                    entity_type=str(raw.get("entity_type") or "unknown"),
                    op=op,
                    entity_id=raw.get("entity_id"),
                    payload=raw.get("payload"),
                    client_uuid=cuid,
                    occurred_at=_parse_dt(raw.get("occurred_at")),
                    status=SyncJournalStatus.APPLIED,
                )
                if rec is not None:
                    rec.applied_at = datetime.now(timezone.utc)
                    applied += 1
                else:
                    duplicates += 1

            batch = SyncBatch(
                direction=SyncDirection.PUSH,
                edge_node_code=self.node.code,
                record_count=applied + duplicates + rejected,
                applied_count=applied,
                duplicate_count=duplicates,
                rejected_count=rejected,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                note=f"push from edge node {self.node.code}",
            )
            session.add(batch)
            session.commit()
        finally:
            session.close()
            engine.dispose()

        # Update master-side bookkeeping.
        with get_master_db_context() as master_db:
            n = master_db.query(EdgeNode).filter(EdgeNode.id == self.node.id).first()
            if n:
                n.last_pushed_at = datetime.now(timezone.utc)
                n.last_seen_at = datetime.now(timezone.utc)
                if rejected:
                    n.status = EdgeNodeStatus.DEGRADED
                    n.last_failure_reason = f"{rejected} rejected rows on last push"
                else:
                    n.status = EdgeNodeStatus.ACTIVE
                    n.last_failure_reason = None
                master_db.commit()

        return {
            "node": self.node.code,
            "applied": applied,
            "duplicates": duplicates,
            "rejected": rejected,
            "rejected_details": rejected_details[:50],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_row(rec: SyncJournal) -> dict[str, Any]:
        return {
            "seq": int(rec.seq),
            "client_uuid": rec.client_uuid,
            "entity_type": rec.entity_type,
            "entity_id": rec.entity_id,
            "op": getattr(rec.op, "value", rec.op),
            "payload": rec.payload,
            "occurred_at": rec.occurred_at.isoformat() if rec.occurred_at else None,
            "origin": rec.origin,
        }


# ---------------------------------------------------------------------------
# Misc utility
# ---------------------------------------------------------------------------


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            # Handle the common "2026-05-02T13:46:01+00:00" / "Z" forms.
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
