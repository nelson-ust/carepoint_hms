# app/repositories/diagnosis_repository.py
from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.all_models import Diagnosis, Visit


class DiagnosisRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, diagnosis_id: int) -> Optional[Diagnosis]:
        return (
            self.db.query(Diagnosis)
            .filter(Diagnosis.id == diagnosis_id, Diagnosis.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, diagnosis_id: int) -> Diagnosis:
        d = self.get_by_id(diagnosis_id)
        if not d:
            raise NotFoundError(message="Diagnosis not found.", detail={"diagnosis_id": diagnosis_id})
        return d

    def get_visit(self, visit_id: int) -> Optional[Visit]:
        return (
            self.db.query(Visit)
            .filter(Visit.id == visit_id, Visit.is_deleted.is_(False))
            .first()
        )

    def list_for_visit(
        self, visit_id: int, *, skip: int = 0, limit: int = 50
    ) -> tuple[list[Diagnosis], int]:
        query = self.db.query(Diagnosis).filter(
            Diagnosis.visit_id == visit_id, Diagnosis.is_deleted.is_(False)
        )
        total = query.with_entities(func.count(Diagnosis.id)).scalar() or 0
        items = (
            query.order_by(Diagnosis.id.desc()).offset(skip).limit(limit).all()
        )
        return items, int(total)

    def create(self, **kwargs) -> Diagnosis:
        d = Diagnosis(**kwargs)
        self.db.add(d)
        self.db.flush()
        self.db.refresh(d)
        return d

    def save(self, d: Diagnosis) -> Diagnosis:
        self.db.add(d)
        self.db.flush()
        self.db.refresh(d)
        return d
