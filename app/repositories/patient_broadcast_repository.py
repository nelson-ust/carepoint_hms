# app/repositories/patient_broadcast_repository.py
from __future__ import annotations

"""Persistence helpers for hospital→patient broadcasts and the patient inbox."""

from datetime import datetime, timezone
from typing import List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import PatientBroadcastAudience, PatientBroadcastStatus
from app.models.all_models import (
    Patient,
    PatientBroadcast,
    PatientBroadcastRecipient,
    User,
)


class PatientBroadcastRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Recipient resolution ─────────────────────────────────────────

    def resolve_recipient_patients(
        self,
        audience_type: PatientBroadcastAudience,
        patient_ids: Sequence[int],
    ) -> List[Patient]:
        """Return the live Patient rows a broadcast should reach."""
        stmt = select(Patient).where(Patient.is_deleted.is_(False))
        if audience_type != PatientBroadcastAudience.ALL:
            ids = list(dict.fromkeys(patient_ids or []))
            if not ids:
                return []
            stmt = stmt.where(Patient.id.in_(ids))
        stmt = stmt.order_by(Patient.id.asc())
        return list(self.db.execute(stmt).scalars().all())

    def count_recipient_patients(
        self,
        audience_type: PatientBroadcastAudience,
        patient_ids: Sequence[int],
    ) -> int:
        stmt = select(func.count(Patient.id)).where(Patient.is_deleted.is_(False))
        if audience_type != PatientBroadcastAudience.ALL:
            ids = list(dict.fromkeys(patient_ids or []))
            if not ids:
                return 0
            stmt = stmt.where(Patient.id.in_(ids))
        return int(self.db.execute(stmt).scalar() or 0)

    # ── Writes ───────────────────────────────────────────────────────

    def create_broadcast(
        self,
        *,
        subject: Optional[str],
        body: str,
        audience_type: PatientBroadcastAudience,
        channels: list[str],
        sent_by_user_id: Optional[int],
        recipient_count: int,
        status: PatientBroadcastStatus = PatientBroadcastStatus.SENT,
    ) -> PatientBroadcast:
        broadcast = PatientBroadcast(
            subject=subject,
            body=body,
            audience_type=audience_type,
            channels=channels,
            sent_by_user_id=sent_by_user_id,
            recipient_count=recipient_count,
            status=status,
            sent_at=datetime.now(timezone.utc),
        )
        self.db.add(broadcast)
        self.db.flush()
        self.db.refresh(broadcast)
        return broadcast

    def add_recipients(self, broadcast_id: int, patient_ids: Sequence[int]) -> int:
        rows = [
            PatientBroadcastRecipient(broadcast_id=broadcast_id, patient_id=pid)
            for pid in patient_ids
        ]
        if rows:
            self.db.add_all(rows)
            self.db.flush()
        return len(rows)

    # ── Staff history ────────────────────────────────────────────────

    def list_broadcasts(
        self, *, skip: int = 0, limit: int = 20
    ) -> tuple[list[PatientBroadcast], int]:
        base = select(PatientBroadcast).where(PatientBroadcast.is_deleted.is_(False))
        total = int(
            self.db.execute(
                select(func.count()).select_from(base.subquery())
            ).scalar()
            or 0
        )
        rows = list(
            self.db.execute(
                base.order_by(
                    PatientBroadcast.sent_at.desc(), PatientBroadcast.id.desc()
                )
                .offset(skip)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return rows, total

    def read_counts_for(self, broadcast_ids: Sequence[int]) -> dict[int, int]:
        """Map broadcast_id → number of recipients who have opened it."""
        if not broadcast_ids:
            return {}
        rows = self.db.execute(
            select(
                PatientBroadcastRecipient.broadcast_id,
                func.count(PatientBroadcastRecipient.id),
            )
            .where(
                PatientBroadcastRecipient.broadcast_id.in_(list(broadcast_ids)),
                PatientBroadcastRecipient.is_deleted.is_(False),
                PatientBroadcastRecipient.read_at.is_not(None),
            )
            .group_by(PatientBroadcastRecipient.broadcast_id)
        ).all()
        return {int(bid): int(cnt) for bid, cnt in rows}

    def get_sender_names(self, user_ids: Sequence[int]) -> dict[int, str]:
        ids = [uid for uid in dict.fromkeys(user_ids) if uid]
        if not ids:
            return {}
        rows = self.db.execute(
            select(User).where(User.id.in_(ids))
        ).scalars().all()
        out: dict[int, str] = {}
        for u in rows:
            name = f"{getattr(u, 'first_name', '') or ''} {getattr(u, 'last_name', '') or ''}".strip()
            out[u.id] = name or getattr(u, "username", None) or f"User #{u.id}"
        return out

    # ── Patient inbox ────────────────────────────────────────────────

    def list_inbox(
        self,
        patient_id: int,
        *,
        skip: int = 0,
        limit: int = 20,
        unread_only: bool = False,
    ) -> tuple[list[tuple[PatientBroadcastRecipient, PatientBroadcast]], int]:
        base = (
            select(PatientBroadcastRecipient, PatientBroadcast)
            .join(
                PatientBroadcast,
                PatientBroadcast.id == PatientBroadcastRecipient.broadcast_id,
            )
            .where(
                PatientBroadcastRecipient.patient_id == patient_id,
                PatientBroadcastRecipient.is_deleted.is_(False),
                PatientBroadcast.is_deleted.is_(False),
            )
        )
        if unread_only:
            base = base.where(PatientBroadcastRecipient.read_at.is_(None))

        total = int(
            self.db.execute(
                select(func.count()).select_from(base.subquery())
            ).scalar()
            or 0
        )
        rows = self.db.execute(
            base.order_by(
                PatientBroadcast.sent_at.desc(), PatientBroadcast.id.desc()
            )
            .offset(skip)
            .limit(limit)
        ).all()
        return [(r[0], r[1]) for r in rows], total

    def count_unread(self, patient_id: int) -> int:
        return int(
            self.db.execute(
                select(func.count(PatientBroadcastRecipient.id)).where(
                    PatientBroadcastRecipient.patient_id == patient_id,
                    PatientBroadcastRecipient.is_deleted.is_(False),
                    PatientBroadcastRecipient.read_at.is_(None),
                )
            ).scalar()
            or 0
        )

    def get_recipient(
        self, recipient_id: int, patient_id: int
    ) -> Optional[tuple[PatientBroadcastRecipient, PatientBroadcast]]:
        row = self.db.execute(
            select(PatientBroadcastRecipient, PatientBroadcast)
            .join(
                PatientBroadcast,
                PatientBroadcast.id == PatientBroadcastRecipient.broadcast_id,
            )
            .where(
                PatientBroadcastRecipient.id == recipient_id,
                PatientBroadcastRecipient.patient_id == patient_id,
                PatientBroadcastRecipient.is_deleted.is_(False),
                PatientBroadcast.is_deleted.is_(False),
            )
        ).first()
        if row is None:
            return None
        return row[0], row[1]

    def mark_read(
        self, recipient: PatientBroadcastRecipient
    ) -> PatientBroadcastRecipient:
        if recipient.read_at is None:
            recipient.read_at = datetime.now(timezone.utc)
            self.db.add(recipient)
            self.db.flush()
            self.db.refresh(recipient)
        return recipient

    def mark_all_read(self, patient_id: int) -> int:
        rows = self.db.execute(
            select(PatientBroadcastRecipient).where(
                PatientBroadcastRecipient.patient_id == patient_id,
                PatientBroadcastRecipient.is_deleted.is_(False),
                PatientBroadcastRecipient.read_at.is_(None),
            )
        ).scalars().all()
        now = datetime.now(timezone.utc)
        for r in rows:
            r.read_at = now
            self.db.add(r)
        self.db.flush()
        return len(rows)
