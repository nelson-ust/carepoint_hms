# app/repositories/consultation_repository.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import EncounterStatus
from app.core.exceptions import NotFoundError
from app.models.all_models import Consultation, Visit


class ConsultationRepository:
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

    def get_by_id(self, consultation_id: int) -> Optional[Consultation]:
        return (
            self.db.query(Consultation)
            .filter(Consultation.id == consultation_id, Consultation.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, consultation_id: int) -> Consultation:
        c = self.get_by_id(consultation_id)
        if not c:
            raise NotFoundError(message="Consultation not found.", detail={"consultation_id": consultation_id})
        return c

    def list_for_visit(
        self, visit_id: int, *, skip: int = 0, limit: int = 20
    ) -> tuple[list[Consultation], int]:
        query = self.db.query(Consultation).filter(
            Consultation.visit_id == visit_id, Consultation.is_deleted.is_(False)
        )
        total = query.with_entities(func.count(Consultation.id)).scalar() or 0
        items = (
            query.order_by(Consultation.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def get_open_for_visit(self, visit_id: int) -> Optional[Consultation]:
        return (
            self.db.query(Consultation)
            .filter(
                Consultation.visit_id == visit_id,
                Consultation.is_deleted.is_(False),
                Consultation.status == EncounterStatus.OPEN,
            )
            .order_by(Consultation.id.desc())
            .first()
        )

    def create(
        self,
        *,
        visit_id: int,
        clinician_staff_id: Optional[int],
        subjective_note: Optional[str],
        objective_note: Optional[str],
        assessment_note: Optional[str],
        plan_note: Optional[str],
    ) -> Consultation:
        c = Consultation(
            visit_id=visit_id,
            clinician_staff_id=clinician_staff_id,
            subjective_note=subjective_note,
            objective_note=objective_note,
            assessment_note=assessment_note,
            plan_note=plan_note,
            status=EncounterStatus.OPEN,
            consultation_started_at=datetime.now(timezone.utc),
        )
        self.db.add(c)
        self.db.flush()
        self.db.refresh(c)
        return c

    def save(self, c: Consultation) -> Consultation:
        self.db.add(c)
        self.db.flush()
        self.db.refresh(c)
        return c
