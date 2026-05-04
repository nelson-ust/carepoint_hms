# app/repositories/triage_repository.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import VisitPriority
from app.core.exceptions import NotFoundError
from app.models.all_models import TriageAssessment, Visit


class TriageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_visit(self, visit_id: int) -> Optional[Visit]:
        return (
            self.db.query(Visit)
            .filter(Visit.id == visit_id, Visit.is_deleted.is_(False))
            .first()
        )

    def get_required_visit(self, visit_id: int) -> Visit:
        visit = self.get_visit(visit_id)
        if not visit:
            raise NotFoundError(message="Visit not found.", detail={"visit_id": visit_id})
        return visit

    def get_by_id(self, triage_id: int) -> Optional[TriageAssessment]:
        return (
            self.db.query(TriageAssessment)
            .filter(TriageAssessment.id == triage_id, TriageAssessment.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, triage_id: int) -> TriageAssessment:
        t = self.get_by_id(triage_id)
        if not t:
            raise NotFoundError(message="Triage assessment not found.", detail={"triage_id": triage_id})
        return t

    def create(
        self,
        *,
        visit_id: int,
        chief_complaint: Optional[str],
        triage_note: Optional[str],
        priority: VisitPriority,
        assessed_by_staff_id: Optional[int],
        assessed_at: Optional[datetime] = None,
    ) -> TriageAssessment:
        triage = TriageAssessment(
            visit_id=visit_id,
            chief_complaint=chief_complaint,
            triage_note=triage_note,
            priority=priority,
            assessed_by_staff_id=assessed_by_staff_id,
            assessed_at=assessed_at or datetime.now(timezone.utc),
        )
        self.db.add(triage)
        self.db.flush()
        self.db.refresh(triage)
        return triage

    def save(self, triage: TriageAssessment) -> TriageAssessment:
        self.db.add(triage)
        self.db.flush()
        self.db.refresh(triage)
        return triage

    def list_for_visit(
        self,
        visit_id: int,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[TriageAssessment], int]:
        query = (
            self.db.query(TriageAssessment)
            .filter(
                TriageAssessment.visit_id == visit_id,
                TriageAssessment.is_deleted.is_(False),
            )
        )
        total = query.with_entities(func.count(TriageAssessment.id)).scalar() or 0
        items = (
            query.order_by(TriageAssessment.assessed_at.desc(), TriageAssessment.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def update_visit_priority(self, visit: Visit, priority: VisitPriority) -> Visit:
        visit.priority = priority
        self.db.add(visit)
        self.db.flush()
        self.db.refresh(visit)
        return visit
