"""
Append-only change ledger used by cloud↔edge replication.

Business code calls :func:`record_change` once per write that must
survive an internet outage; the row goes into ``sync_journal`` and is
later replicated to the other side by :class:`EdgeSyncService`.

The helper is intentionally lightweight — most callers just hand it the
new row and a verb. Duplicates (replays after a crash) are silently
dropped via the ``client_uuid`` unique constraint.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import SyncJournalOp, SyncJournalStatus
from app.models.all_models import SyncJournal


logger = logging.getLogger(__name__)


class SyncJournalService:
    """Tenant-DB scoped helper around :class:`SyncJournal`."""

    def __init__(self, db: Session, *, origin: str = "cloud", origin_node_id: Optional[int] = None) -> None:
        self.db = db
        self.origin = origin
        self.origin_node_id = origin_node_id

    # ------------------------------------------------------------------
    # Append
    # ------------------------------------------------------------------

    def record_change(
        self,
        *,
        entity_type: str,
        op: SyncJournalOp,
        entity_id: Optional[int] = None,
        payload: Optional[dict[str, Any]] = None,
        client_uuid: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
        status: SyncJournalStatus = SyncJournalStatus.PENDING,
    ) -> Optional[SyncJournal]:
        rec = SyncJournal(
            entity_type=entity_type,
            entity_id=entity_id,
            client_uuid=client_uuid or str(uuid.uuid4()),
            op=op,
            payload=payload,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            origin=self.origin,
            origin_node_id=self.origin_node_id,
            status=status,
        )
        self.db.add(rec)
        try:
            self.db.flush()
        except IntegrityError:
            # Duplicate client_uuid — replay or echo from the other side.
            self.db.rollback()
            logger.debug("SyncJournal duplicate skipped: %s", rec.client_uuid)
            return None
        return rec

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def fetch_since(
        self,
        *,
        cursor: int = 0,
        limit: int = 500,
        skip_origin: Optional[str] = None,
    ) -> list[SyncJournal]:
        """
        Return up to ``limit`` rows with ``seq > cursor``.

        ``skip_origin`` lets a subscriber filter out their own echoes
        (an edge node should not pull rows it itself authored).
        """
        q = (
            self.db.query(SyncJournal)
            .filter(SyncJournal.seq > int(cursor or 0))
            .order_by(SyncJournal.seq.asc())
        )
        if skip_origin:
            q = q.filter(SyncJournal.origin != skip_origin)
        return q.limit(int(limit)).all()

    def latest_seq(self) -> int:
        from sqlalchemy import func

        row = self.db.query(func.coalesce(func.max(SyncJournal.seq), 0)).scalar()
        return int(row or 0)
