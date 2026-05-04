# app/services/triage_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import VisitPriority, VisitStatus
from app.core.exceptions import BadRequestError
from app.models.all_models import TriageAssessment
from app.repositories.triage_repository import TriageRepository
from app.schemas.triage_schema import TriageCreateSchema, TriageUpdateSchema


_TERMINAL_VISIT_STATES = {VisitStatus.COMPLETED, VisitStatus.CANCELLED}


class TriageService:
    """
    Service layer for triage assessment lifecycle.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = TriageRepository(db)

    def list_for_visit(self, visit_id: int, *, skip: int = 0, limit: int = 20):
        return self.repository.list_for_visit(visit_id, skip=skip, limit=limit)

    def get(self, triage_id: int) -> TriageAssessment:
        return self.repository.get_required_by_id(triage_id)

    def create(self, payload: TriageCreateSchema, *, actor_user_id: Optional[int] = None) -> TriageAssessment:
        visit = self.repository.get_required_visit(payload.visit_id)
        if visit.status in _TERMINAL_VISIT_STATES:
            raise BadRequestError(
                message="Cannot triage a closed visit.",
                detail={"visit_status": str(visit.status)},
            )

        priority = VisitPriority(payload.priority)
        triage = self.repository.create(
            visit_id=visit.id,
            chief_complaint=payload.chief_complaint,
            triage_note=payload.triage_note,
            priority=priority,
            assessed_by_staff_id=payload.assessed_by_staff_id,
            assessed_at=datetime.now(timezone.utc),
        )

        if payload.update_visit_priority:
            self.repository.update_visit_priority(visit, priority)

        self.db.commit()
        return self.repository.get_required_by_id(triage.id)

    def update(
        self,
        triage_id: int,
        payload: TriageUpdateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> TriageAssessment:
        triage = self.repository.get_required_by_id(triage_id)
        if payload.chief_complaint is not None:
            triage.chief_complaint = payload.chief_complaint
        if payload.triage_note is not None:
            triage.triage_note = payload.triage_note
        if payload.priority is not None:
            triage.priority = VisitPriority(payload.priority)

        self.repository.save(triage)

        if payload.update_visit_priority and payload.priority is not None:
            visit = self.repository.get_required_visit(triage.visit_id)
            self.repository.update_visit_priority(visit, VisitPriority(payload.priority))

        self.db.commit()
        return self.repository.get_required_by_id(triage.id)
