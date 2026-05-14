# app/repositories/consultation_repository.py
from __future__ import annotations

"""
app.repositories.consultation_repository

Repository layer for Clinical Consultations.

Purpose
-------
This module handles persistence for clinical encounter notes (consultations).
It ensures that consultations are linked to active visits and facilitates
retrieval with optimized eager loading for demographics and clinician context.

Optimizations
-------------
- Eager loads Visit and Patient demographics to avoid N+1 queries.
- Eager loads Clinician Staff and User profiles for immediate UI display.
- Implements decoupled count queries for performant pagination.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.enums import EncounterStatus
from app.core.exceptions import NotFoundError
from app.models.all_models import Consultation, Visit, StaffProfile, User


class ConsultationRepository:
    """
    Repository for Consultation persistence and lookups.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_visit(self, visit_id: int) -> Optional[Visit]:
        """
        Retrieve a visit by ID, checking for soft-deletion.
        """
        return (
            self.db.query(Visit)
            .filter(Visit.id == visit_id, Visit.is_deleted.is_(False))
            .first()
        )

    def get_required_visit(self, visit_id: int) -> Visit:
        """
        Retrieve a visit or raise NotFoundError if missing.
        """
        v = self.get_visit(visit_id)
        if not v:
            raise NotFoundError(message="Visit not found.", detail={"visit_id": visit_id})
        return v

    def get_by_id(self, consultation_id: int) -> Optional[Consultation]:
        """
        Retrieve a consultation by ID with optimized eager loading.
        
        Loads:
        - Visit and Patient (for header info)
        - Clinician Staff and User (for attribution info)
        """
        return (
            self.db.query(Consultation)
            .options(
                joinedload(Consultation.visit).joinedload(Visit.patient),
                joinedload(Consultation.clinician_staff).joinedload(StaffProfile.user),
            )
            .filter(Consultation.id == consultation_id, Consultation.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, consultation_id: int) -> Consultation:
        """
        Retrieve a consultation or raise NotFoundError if missing.
        """
        c = self.get_by_id(consultation_id)
        if not c:
            raise NotFoundError(message="Consultation not found.", detail={"consultation_id": consultation_id})
        return c

    def list_for_visit(
        self, visit_id: int, *, skip: int = 0, limit: int = 20
    ) -> tuple[list[Consultation], int]:
        """
        Return a paginated list of consultations for a specific visit.
        """
        # Base query to reuse for count and data
        query = self.db.query(Consultation).filter(
            Consultation.visit_id == visit_id, Consultation.is_deleted.is_(False)
        )
        
        # 1. Performance-optimized count
        total = query.with_entities(func.count(Consultation.id)).scalar() or 0
        
        if total == 0:
            return [], 0

        # 2. Optimized data retrieval with eager loads
        items = (
            query.options(
                joinedload(Consultation.clinician_staff).joinedload(StaffProfile.user),
            )
            .order_by(Consultation.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)


    def get_open_for_visit(self, visit_id: int) -> Optional[Consultation]:
        """
        Find the most recent OPEN consultation for a visit.
        
        Useful for preventing duplicate concurrent encounters.
        """
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
        visit_flow_step_id: Optional[int],
        subjective_note: Optional[str],
        objective_note: Optional[str],
        assessment_note: Optional[str],
        plan_note: Optional[str],
    ) -> Consultation:
        """
        Initialize a new clinical consultation record.
        """
        c = Consultation(
            visit_id=visit_id,
            visit_flow_step_id=visit_flow_step_id,
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
        """
        Persist changes to an existing consultation.
        """
        self.db.add(c)
        self.db.flush()
        self.db.refresh(c)
        return c
