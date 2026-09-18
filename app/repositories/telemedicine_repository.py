# app/repositories/telemedicine_repository.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.all_models import Patient, StaffProfile, User
from app.models.telemedicine_models import TelemedicineMessage, TelemedicineSession


class TelemedicineRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -- shared entities --
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
            self.db.query(User.first_name, User.last_name)
            .join(StaffProfile, StaffProfile.user_id == User.id)
            .filter(StaffProfile.id == staff_id)
            .first()
        )
        if not row:
            return None
        name = " ".join(x for x in [row[0], row[1]] if x).strip()
        return name or None

    def staff_id_for_user(self, user_id: int) -> Optional[int]:
        row = (
            self.db.query(StaffProfile.id)
            .filter(StaffProfile.user_id == user_id, StaffProfile.is_deleted.is_(False))
            .first()
        )
        return row[0] if row else None

    # -- session CRUD --
    def get_by_id(self, session_id: int) -> Optional[TelemedicineSession]:
        return (
            self.db.query(TelemedicineSession)
            .filter(TelemedicineSession.id == session_id, TelemedicineSession.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, session_id: int) -> TelemedicineSession:
        s = self.get_by_id(session_id)
        if not s:
            raise NotFoundError(message="Telemedicine session not found.", detail={"session_id": session_id})
        return s

    def get_by_code(self, code: str) -> Optional[TelemedicineSession]:
        return (
            self.db.query(TelemedicineSession)
            .filter(TelemedicineSession.session_code == code, TelemedicineSession.is_deleted.is_(False))
            .first()
        )

    def code_exists(self, code: str) -> bool:
        return (
            self.db.query(TelemedicineSession.id)
            .filter(TelemedicineSession.session_code == code)
            .first()
            is not None
        )

    def create(self, **kwargs) -> TelemedicineSession:
        record = TelemedicineSession(**kwargs)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def list(
        self,
        *,
        status: Optional[str] = None,
        patient_id: Optional[int] = None,
        clinician_staff_id: Optional[int] = None,
        modality: Optional[str] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[TelemedicineSession], int]:
        query = self.db.query(TelemedicineSession).filter(TelemedicineSession.is_deleted.is_(False))
        if status:
            query = query.filter(TelemedicineSession.status == status)
        if patient_id:
            query = query.filter(TelemedicineSession.patient_id == patient_id)
        if clinician_staff_id:
            query = query.filter(TelemedicineSession.clinician_staff_id == clinician_staff_id)
        if modality:
            query = query.filter(TelemedicineSession.modality == modality)
        if from_dt:
            query = query.filter(TelemedicineSession.scheduled_start_at >= from_dt)
        if to_dt:
            query = query.filter(TelemedicineSession.scheduled_start_at < to_dt)

        total = query.with_entities(func.count(TelemedicineSession.id)).scalar() or 0
        items = (
            query.order_by(
                TelemedicineSession.scheduled_start_at.desc().nullslast(),
                TelemedicineSession.id.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    # -- messages --
    def add_message(self, **kwargs) -> TelemedicineMessage:
        kwargs.setdefault("sent_at", datetime.now(timezone.utc))
        msg = TelemedicineMessage(**kwargs)
        self.db.add(msg)
        self.db.flush()
        self.db.refresh(msg)
        return msg

    def list_messages(self, session_id: int) -> list[TelemedicineMessage]:
        return (
            self.db.query(TelemedicineMessage)
            .filter(
                TelemedicineMessage.session_id == session_id,
                TelemedicineMessage.is_deleted.is_(False),
            )
            .order_by(TelemedicineMessage.sent_at.asc(), TelemedicineMessage.id.asc())
            .all()
        )
