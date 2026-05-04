# app/repositories/vital_sign_repository.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.all_models import VitalSign, Visit


class VitalSignRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_visit(self, visit_id: int) -> Optional[Visit]:
        return (
            self.db.query(Visit)
            .filter(Visit.id == visit_id, Visit.is_deleted.is_(False))
            .first()
        )

    def get_required_visit(self, visit_id: int) -> Visit:
        v = self.get_visit(visit_id)
        if not v:
            raise NotFoundError(message="Visit not found.", detail={"visit_id": visit_id})
        return v

    def get_by_id(self, vital_id: int) -> Optional[VitalSign]:
        return (
            self.db.query(VitalSign)
            .filter(VitalSign.id == vital_id, VitalSign.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, vital_id: int) -> VitalSign:
        v = self.get_by_id(vital_id)
        if not v:
            raise NotFoundError(message="Vital sign record not found.", detail={"vital_id": vital_id})
        return v

    def create(self, **kwargs) -> VitalSign:
        kwargs.setdefault("recorded_at", datetime.now(timezone.utc))
        record = VitalSign(**kwargs)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def list_for_visit(
        self, visit_id: int, *, skip: int = 0, limit: int = 50
    ) -> tuple[list[VitalSign], int]:
        query = self.db.query(VitalSign).filter(
            VitalSign.visit_id == visit_id,
            VitalSign.is_deleted.is_(False),
        )
        total = query.with_entities(func.count(VitalSign.id)).scalar() or 0
        items = (
            query.order_by(VitalSign.recorded_at.desc(), VitalSign.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def latest_for_visit(self, visit_id: int) -> Optional[VitalSign]:
        return (
            self.db.query(VitalSign)
            .filter(VitalSign.visit_id == visit_id, VitalSign.is_deleted.is_(False))
            .order_by(VitalSign.recorded_at.desc(), VitalSign.id.desc())
            .first()
        )
