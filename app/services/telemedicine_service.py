# app/services/telemedicine_service.py
from __future__ import annotations

"""Telemedicine service — scheduling, virtual-room lifecycle, SOAP notes, chat."""

import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    TelemedicineModality,
    TelemedicineProvider,
    TelemedicineSenderRole,
    TelemedicineStatus,
)
from app.core.exceptions import BadRequestError, ForbiddenError
from app.core.logger import get_logger
from app.models.telemedicine_models import TelemedicineMessage, TelemedicineSession
from app.repositories.telemedicine_repository import TelemedicineRepository

logger = get_logger(__name__)

_JITSI_DOMAIN = "meet.jit.si"
_TERMINAL = {
    TelemedicineStatus.COMPLETED,
    TelemedicineStatus.CANCELLED,
    TelemedicineStatus.NO_SHOW,
}


class TelemedicineService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = TelemedicineRepository(db)

    # -- helpers --
    def _generate_code(self) -> str:
        for _ in range(10):
            code = f"TM-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3).upper()}"
            if not self.repository.code_exists(code):
                return code
        return f"TM-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(5).upper()}"

    @staticmethod
    def _room_name(code: str) -> str:
        # Unguessable, provider-agnostic room slug. For Jitsi the client joins
        # `https://<domain>/<room_name>`; the random suffix keeps the room private.
        return f"carepoint-{code.lower()}-{secrets.token_hex(4)}"

    @staticmethod
    def _room_url(provider: TelemedicineProvider, room_name: str) -> Optional[str]:
        if provider == TelemedicineProvider.JITSI:
            return f"https://{_JITSI_DOMAIN}/{room_name}"
        return None

    def _decorate(self, session: TelemedicineSession) -> TelemedicineSession:
        try:
            p = self.repository.get_patient(session.patient_id)
            session.patient_name = (
                " ".join(x for x in [getattr(p, "first_name", None), getattr(p, "last_name", None)] if x).strip()
                if p else None
            )
        except Exception:
            session.patient_name = None
        try:
            session.clinician_name = self.repository.staff_display_name(session.clinician_staff_id)
        except Exception:
            session.clinician_name = None
        return session

    # -- CRUD / lifecycle --
    def create(self, payload, *, actor_user_id: Optional[int] = None) -> TelemedicineSession:
        self.repository.get_required_patient(payload.patient_id)
        if payload.clinician_staff_id and not self.repository.get_staff(payload.clinician_staff_id):
            raise BadRequestError(
                message="Clinician staff not found.",
                detail={"clinician_staff_id": payload.clinician_staff_id},
            )

        data = payload.model_dump(exclude_unset=True)
        code = self._generate_code()
        provider = data.get("provider", TelemedicineProvider.JITSI)
        room_name = self._room_name(code)
        data["session_code"] = code
        data["room_name"] = room_name
        data["room_url"] = self._room_url(provider, room_name)
        data["status"] = TelemedicineStatus.SCHEDULED
        data["created_by_user_id"] = actor_user_id
        data["created_by_id"] = actor_user_id

        session = self.repository.create(**data)
        self.repository.add_message(
            session_id=session.id,
            sender_role=TelemedicineSenderRole.SYSTEM,
            sender_name="System",
            body=f"Telemedicine session {code} scheduled.",
        )
        self.db.commit()
        self.db.refresh(session)
        self._notify_scheduled(session)
        return self._decorate(session)

    def get(self, session_id: int) -> TelemedicineSession:
        return self._decorate(self.repository.get_required_by_id(session_id))

    def list(self, **kwargs):
        items, total = self.repository.list(**kwargs)
        for s in items:
            self._decorate(s)
        return items, total

    def update(self, session_id: int, payload) -> TelemedicineSession:
        session = self.repository.get_required_by_id(session_id)
        if session.status in _TERMINAL:
            raise BadRequestError(message="Cannot edit a closed telemedicine session.")
        data = payload.model_dump(exclude_unset=True)
        if "clinician_staff_id" in data and data["clinician_staff_id"]:
            if not self.repository.get_staff(data["clinician_staff_id"]):
                raise BadRequestError(
                    message="Clinician staff not found.",
                    detail={"clinician_staff_id": data["clinician_staff_id"]},
                )
        for k, v in data.items():
            setattr(session, k, v)
        self.db.commit()
        self.db.refresh(session)
        return self._decorate(session)

    # -- join --
    def join(self, session_id: int, *, user_id: int, is_clinician: bool, display_name: Optional[str] = None):
        session = self.repository.get_required_by_id(session_id)
        if session.status in _TERMINAL:
            raise BadRequestError(message=f"This session is {str(session.status).lower()} and cannot be joined.")

        now = datetime.now(timezone.utc)
        changed = False
        if is_clinician:
            if session.clinician_joined_at is None:
                session.clinician_joined_at = now
                changed = True
            # Clinician joining moves a scheduled/waiting session into progress.
            if session.status in (TelemedicineStatus.SCHEDULED, TelemedicineStatus.WAITING):
                session.status = TelemedicineStatus.IN_PROGRESS
                if session.started_at is None:
                    session.started_at = now
                changed = True
        else:
            if session.patient_joined_at is None:
                session.patient_joined_at = now
                changed = True
            # Patient arriving before the clinician goes to the waiting room.
            if session.status == TelemedicineStatus.SCHEDULED:
                session.status = TelemedicineStatus.WAITING
                session.waiting_since = now
                changed = True

        if changed:
            role = TelemedicineSenderRole.CLINICIAN if is_clinician else TelemedicineSenderRole.PATIENT
            who = display_name or ("Clinician" if is_clinician else "Patient")
            self.repository.add_message(
                session_id=session.id,
                sender_user_id=user_id,
                sender_role=TelemedicineSenderRole.SYSTEM,
                sender_name="System",
                body=f"{who} joined the session.",
            )
            self.db.commit()
            self.db.refresh(session)

        return self._decorate(session)

    def build_join_info(self, session: TelemedicineSession, *, is_clinician: bool, display_name: Optional[str]):
        return {
            "session_code": session.session_code,
            "provider": str(session.provider),
            "modality": str(session.modality),
            "status": str(session.status),
            "room_name": session.room_name,
            "room_url": session.room_url,
            "domain": _JITSI_DOMAIN,
            "display_name": display_name,
            "is_clinician": is_clinician,
        }

    # -- start / complete / cancel / no-show --
    def start(self, session_id: int, *, actor_user_id: Optional[int] = None) -> TelemedicineSession:
        session = self.repository.get_required_by_id(session_id)
        if session.status in _TERMINAL:
            raise BadRequestError(message="Session is already closed.")
        if session.status == TelemedicineStatus.IN_PROGRESS:
            return self._decorate(session)
        session.status = TelemedicineStatus.IN_PROGRESS
        if session.started_at is None:
            session.started_at = datetime.now(timezone.utc)
        self.repository.add_message(
            session_id=session.id, sender_user_id=actor_user_id,
            sender_role=TelemedicineSenderRole.SYSTEM, sender_name="System",
            body="Consultation started.",
        )
        self.db.commit()
        self.db.refresh(session)
        return self._decorate(session)

    def _apply_notes(self, session: TelemedicineSession, payload) -> None:
        data = payload.model_dump(exclude_unset=True) if payload is not None else {}
        for k in (
            "subjective_note", "objective_note", "assessment_note",
            "plan_note", "summary", "follow_up_required", "follow_up_notes",
        ):
            if k in data and data[k] is not None:
                setattr(session, k, data[k])

    def upsert_notes(self, session_id: int, payload, *, actor_user_id: Optional[int] = None) -> TelemedicineSession:
        session = self.repository.get_required_by_id(session_id)
        if session.status in (TelemedicineStatus.CANCELLED, TelemedicineStatus.NO_SHOW):
            raise BadRequestError(message="Cannot document a cancelled session.")
        self._apply_notes(session, payload)
        self.db.commit()
        self.db.refresh(session)
        return self._decorate(session)

    def complete(self, session_id: int, payload=None, *, actor_user_id: Optional[int] = None) -> TelemedicineSession:
        session = self.repository.get_required_by_id(session_id)
        if session.status in _TERMINAL:
            raise BadRequestError(message="Session is already closed.")
        self._apply_notes(session, payload)
        now = datetime.now(timezone.utc)
        session.status = TelemedicineStatus.COMPLETED
        session.ended_at = now
        if session.started_at is not None:
            delta = now - session.started_at
            session.duration_seconds = max(int(delta.total_seconds()), 0)
        self.repository.add_message(
            session_id=session.id, sender_user_id=actor_user_id,
            sender_role=TelemedicineSenderRole.SYSTEM, sender_name="System",
            body="Consultation completed.",
        )
        self.db.commit()
        self.db.refresh(session)
        return self._decorate(session)

    def cancel(self, session_id: int, payload, *, actor_user_id: Optional[int] = None) -> TelemedicineSession:
        session = self.repository.get_required_by_id(session_id)
        if session.status in _TERMINAL:
            raise BadRequestError(message="Session is already closed.")
        session.status = TelemedicineStatus.CANCELLED
        session.cancellation_reason = getattr(payload, "reason", None)
        self.repository.add_message(
            session_id=session.id, sender_user_id=actor_user_id,
            sender_role=TelemedicineSenderRole.SYSTEM, sender_name="System",
            body="Session cancelled." + (f" Reason: {session.cancellation_reason}" if session.cancellation_reason else ""),
        )
        self.db.commit()
        self.db.refresh(session)
        return self._decorate(session)

    def mark_no_show(self, session_id: int, *, actor_user_id: Optional[int] = None) -> TelemedicineSession:
        session = self.repository.get_required_by_id(session_id)
        if session.status in _TERMINAL:
            raise BadRequestError(message="Session is already closed.")
        session.status = TelemedicineStatus.NO_SHOW
        session.ended_at = datetime.now(timezone.utc)
        self.repository.add_message(
            session_id=session.id, sender_user_id=actor_user_id,
            sender_role=TelemedicineSenderRole.SYSTEM, sender_name="System",
            body="Marked as no-show.",
        )
        self.db.commit()
        self.db.refresh(session)
        return self._decorate(session)

    # -- chat --
    def send_message(
        self, session_id: int, payload, *,
        sender_user_id: Optional[int], sender_role: TelemedicineSenderRole, sender_name: Optional[str],
    ) -> TelemedicineMessage:
        session = self.repository.get_required_by_id(session_id)
        if session.status in (TelemedicineStatus.CANCELLED, TelemedicineStatus.NO_SHOW):
            raise BadRequestError(message="Cannot message a closed session.")
        msg = self.repository.add_message(
            session_id=session.id,
            sender_user_id=sender_user_id,
            sender_role=sender_role,
            sender_name=sender_name,
            body=payload.body,
            attachment_key=payload.attachment_key,
            attachment_name=payload.attachment_name,
        )
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def list_messages(self, session_id: int) -> list[TelemedicineMessage]:
        self.repository.get_required_by_id(session_id)
        return self.repository.list_messages(session_id)

    # -- notifications --
    def _notify_scheduled(self, session: TelemedicineSession) -> None:
        try:
            from app.core.enums import NotificationEvent
            from app.models.all_models import StaffProfile, User
            from app.services.notification_dispatcher import NotificationDispatcher

            if not session.clinician_staff_id:
                return
            user = (
                self.db.query(User)
                .join(StaffProfile, StaffProfile.user_id == User.id)
                .filter(StaffProfile.id == session.clinician_staff_id, User.is_deleted.is_(False))
                .first()
            )
            if not user:
                return
            when = session.scheduled_start_at.isoformat() if session.scheduled_start_at else "soon"
            NotificationDispatcher(self.db).dispatch(
                event=NotificationEvent.SYSTEM_ALERT,
                recipients=[user],
                subject="New telemedicine session scheduled",
                body=f"You have a telemedicine session ({session.session_code}) scheduled for {when}.",
                context={"telemedicine_session_id": session.id, "patient_id": session.patient_id},
            )
        except Exception as exc:
            logger.warning("Telemedicine scheduling notification failed for %s: %s", session.id, exc)
