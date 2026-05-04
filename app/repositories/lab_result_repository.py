# app/repositories/lab_result_repository.py
from __future__ import annotations

"""
Repository for LabResult.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import NotFoundError
from app.models.all_models import LabOrderItem, LabResult


class LabResultRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, result_id: int) -> Optional[LabResult]:
        return (
            self.db.query(LabResult)
            .filter(LabResult.id == result_id, LabResult.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, result_id: int) -> LabResult:
        r = self.get_by_id(result_id)
        if not r:
            raise NotFoundError(message="Lab result not found.", detail={"result_id": result_id})
        return r

    def get_by_order_item(self, item_id: int) -> Optional[LabResult]:
        return (
            self.db.query(LabResult)
            .filter(LabResult.lab_order_item_id == item_id, LabResult.is_deleted.is_(False))
            .first()
        )

    def list_for_visit(self, visit_id: int) -> list[LabResult]:
        return (
            self.db.query(LabResult)
            .options(joinedload(LabResult.lab_order_item).joinedload(LabOrderItem.lab_order))
            .join(LabOrderItem, LabResult.lab_order_item_id == LabOrderItem.id)
            .filter(LabResult.is_deleted.is_(False))
            .filter(LabOrderItem.is_deleted.is_(False))
            .all()
        )

    def create(self, **kwargs) -> LabResult:
        kwargs.setdefault("entered_at", datetime.now(timezone.utc))
        result = LabResult(**kwargs)
        self.db.add(result)
        self.db.flush()
        self.db.refresh(result)
        return result

    def save(self, result: LabResult) -> LabResult:
        self.db.add(result)
        self.db.flush()
        self.db.refresh(result)
        return result
