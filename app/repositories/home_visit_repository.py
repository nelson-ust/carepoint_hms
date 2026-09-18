# app/repositories/home_visit_repository.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.all_models import Patient, StaffProfile, User
from app.models.home_health_models import (
    HomeVisit,
    HomeVisitNote,
    HomeVisitStatusEvent,
)


class HomeVisitRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -- lookups on shared entities --
    def get_patient(self, patient_id: int) -> Optional[Patient]:
        return (
            self.db.query(Patient)
            .filter(Patient.id == patient_id, Patient.is_deleted.is_(False))
            .first()
        )

    def get_required_patient(self, patient_id: int) -> Patient:
        p = self.get_patient(patient_id)
        if not p:
            raise NotFoundError(message="Patient not found.", detail={"patient_id": patient_id})
        return p

    def get_staff(self, staff_id: int) -> Optional[StaffProfile]:
        return (
            self.db.query(StaffProfile)
            .filter(StaffProfile.id == staff_id, StaffProfile.is_deleted.is_(False))
            .first()
        )

    def staff_display_name(self, staff_id: Optional[int]) -> Optional[str]:
        if not staff_id:
            return None
        row = (
            self.db.query(User.first_name, User.last_name, StaffProfile.job_title)
            .join(StaffProfile, StaffProfile.user_id == User.id)
            .filter(StaffProfile.id == staff_id)
            .first()
        )
        if not row:
            return None
        name = " ".join(x for x in [row[0], row[1]] if x).strip()
        return name or None

    # -- home visit CRUD --
    def get_by_id(self, visit_id: int) -> Optional[HomeVisit]:
        return (
            self.db.query(HomeVisit)
            .filter(HomeVisit.id == visit_id, HomeVisit.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, visit_id: int) -> HomeVisit:
        v = self.get_by_id(visit_id)
        if not v:
            raise NotFoundError(message="Home visit not found.", detail={"home_visit_id": visit_id})
        return v

    def code_exists(self, code: str) -> bool:
        return (
            self.db.query(HomeVisit.id).filter(HomeVisit.visit_code == code).first() is not None
        )

    def create(self, **kwargs) -> HomeVisit:
        record = HomeVisit(**kwargs)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def list(
        self,
        *,
        status: Optional[str] = None,
        patient_id: Optional[int] = None,
        assigned_staff_id: Optional[int] = None,
        visit_type: Optional[str] = None,
        priority: Optional[str] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[HomeVisit], int]:
        query = self.db.query(HomeVisit).filter(HomeVisit.is_deleted.is_(False))
        if status:
            query = query.filter(HomeVisit.status == status)
        if patient_id:
            query = query.filter(HomeVisit.patient_id == patient_id)
        if assigned_staff_id:
            query = query.filter(HomeVisit.assigned_staff_id == assigned_staff_id)
        if visit_type:
            query = query.filter(HomeVisit.visit_type == visit_type)
        if priority:
            query = query.filter(HomeVisit.priority == priority)
        if from_dt:
            query = query.filter(HomeVisit.scheduled_start_at >= from_dt)
        if to_dt:
            query = query.filter(HomeVisit.scheduled_start_at < to_dt)

        total = query.with_entities(func.count(HomeVisit.id)).scalar() or 0
        items = (
            query.order_by(HomeVisit.scheduled_start_at.desc().nullslast(), HomeVisit.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    # -- status events --
    def add_status_event(self, **kwargs) -> HomeVisitStatusEvent:
        kwargs.setdefault("occurred_at", datetime.now(timezone.utc))
        ev = HomeVisitStatusEvent(**kwargs)
        self.db.add(ev)
        self.db.flush()
        return ev

    def list_events(self, visit_id: int) -> list[HomeVisitStatusEvent]:
        return (
            self.db.query(HomeVisitStatusEvent)
            .filter(
                HomeVisitStatusEvent.home_visit_id == visit_id,
                HomeVisitStatusEvent.is_deleted.is_(False),
            )
            .order_by(HomeVisitStatusEvent.occurred_at.asc(), HomeVisitStatusEvent.id.asc())
            .all()
        )

    # -- documentation note --
    def get_note(self, visit_id: int) -> Optional[HomeVisitNote]:
        return (
            self.db.query(HomeVisitNote)
            .filter(
                HomeVisitNote.home_visit_id == visit_id,
                HomeVisitNote.is_deleted.is_(False),
            )
            .first()
        )

    def create_note(self, **kwargs) -> HomeVisitNote:
        note = HomeVisitNote(**kwargs)
        self.db.add(note)
        self.db.flush()
        self.db.refresh(note)
        return note
