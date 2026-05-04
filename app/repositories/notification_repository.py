# app/repositories/notification_repository.py
from __future__ import annotations

"""
Repository for the notifications module (Stage 17).

Persists ``NotificationTemplate``, ``Notification``, and the lightweight
``Message`` entity used for in-app system messaging. The retry queue is
implemented at the service layer using these primitives.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.enums import NotificationChannel, NotificationStatus, MessageStatus
from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.all_models import Message, Notification, NotificationTemplate, Patient, User


class NotificationTemplateRepository:
    """Persistence helpers for ``NotificationTemplate``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, template_id: int) -> Optional[NotificationTemplate]:
        return (
            self.db.query(NotificationTemplate)
            .filter(
                NotificationTemplate.id == template_id,
                NotificationTemplate.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, template_id: int) -> NotificationTemplate:
        t = self.get_by_id(template_id)
        if not t:
            raise NotFoundError(message="Notification template not found.", detail={"template_id": template_id})
        return t

    def get_by_code(self, code: str) -> Optional[NotificationTemplate]:
        # Codes are stored uppercase by the schema validator; we still uppercase
        # defensively in case callers pass in raw lower-case values.
        return (
            self.db.query(NotificationTemplate)
            .filter(
                func.upper(NotificationTemplate.code) == code.strip().upper(),
                NotificationTemplate.is_deleted.is_(False),
            )
            .first()
        )

    def list_templates(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        channel: Optional[NotificationChannel] = None,
        search: Optional[str] = None,
    ) -> tuple[list[NotificationTemplate], int]:
        query = self.db.query(NotificationTemplate).filter(
            NotificationTemplate.is_deleted.is_(False)
        )
        if channel is not None:
            query = query.filter(NotificationTemplate.channel == channel)
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(NotificationTemplate.name).like(term),
                    func.lower(NotificationTemplate.code).like(term),
                )
            )
        total = query.with_entities(func.count(NotificationTemplate.id)).scalar() or 0
        items = (
            query.order_by(NotificationTemplate.code.asc()).offset(skip).limit(limit).all()
        )
        return items, int(total)

    def create(self, **kwargs) -> NotificationTemplate:
        if self.get_by_code(kwargs["code"]):
            raise AlreadyExistsError(
                message="A template with this code already exists.",
                detail={"code": kwargs["code"]},
            )
        # SQLAlchemy expects the enum class itself, so coerce string channels
        # into the NotificationChannel enum here.
        if isinstance(kwargs.get("channel"), str):
            kwargs["channel"] = NotificationChannel(kwargs["channel"])
        t = NotificationTemplate(**kwargs)
        self.db.add(t)
        self.db.flush()
        self.db.refresh(t)
        return t

    def update(self, t: NotificationTemplate, **kwargs) -> NotificationTemplate:
        for field, value in kwargs.items():
            if value is not None:
                setattr(t, field, value)
        self.db.add(t)
        self.db.flush()
        self.db.refresh(t)
        return t

    def soft_delete(self, t: NotificationTemplate) -> NotificationTemplate:
        t.is_deleted = True
        self.db.add(t)
        self.db.flush()
        return t


class NotificationRepository:
    """Persistence helpers for ``Notification`` and the retry queue."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------- LOOKUPS -------

    def get_by_id(self, notification_id: int) -> Optional[Notification]:
        return (
            self.db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, notification_id: int) -> Notification:
        n = self.get_by_id(notification_id)
        if not n:
            raise NotFoundError(message="Notification not found.", detail={"notification_id": notification_id})
        return n

    def get_user(self, user_id: int) -> Optional[User]:
        return (
            self.db.query(User)
            .filter(User.id == user_id, User.is_deleted.is_(False))
            .first()
        )

    def get_patient(self, patient_id: int) -> Optional[Patient]:
        return (
            self.db.query(Patient)
            .filter(Patient.id == patient_id, Patient.is_deleted.is_(False))
            .first()
        )

    # ------- LISTING -------

    def list_notifications(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        user_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        channel: Optional[NotificationChannel] = None,
        status: Optional[NotificationStatus] = None,
    ) -> tuple[list[Notification], int]:
        query = self.db.query(Notification).filter(Notification.is_deleted.is_(False))
        if user_id is not None:
            query = query.filter(Notification.user_id == user_id)
        if patient_id is not None:
            query = query.filter(Notification.patient_id == patient_id)
        if channel is not None:
            query = query.filter(Notification.channel == channel)
        if status is not None:
            query = query.filter(Notification.status == status)

        total = query.with_entities(func.count(Notification.id)).scalar() or 0
        items = (
            query.order_by(Notification.id.desc()).offset(skip).limit(limit).all()
        )
        return items, int(total)

    def list_pending(
        self,
        *,
        limit: int = 100,
        ready_at_or_before: Optional[datetime] = None,
    ) -> list[Notification]:
        """
        Pull notifications that are waiting to be sent.

        A notification is "ready" when its status is PENDING and either:
        - scheduled_at is null (send asap), or
        - scheduled_at <= ready_at_or_before (defaults to now).
        """
        cutoff = ready_at_or_before or datetime.now(timezone.utc)
        return (
            self.db.query(Notification)
            .filter(
                Notification.is_deleted.is_(False),
                Notification.status == NotificationStatus.PENDING,
                or_(
                    Notification.scheduled_at.is_(None),
                    Notification.scheduled_at <= cutoff,
                ),
            )
            .order_by(Notification.scheduled_at.asc().nullsfirst(), Notification.id.asc())
            .limit(limit)
            .all()
        )

    def list_failed(self, *, limit: int = 100) -> list[Notification]:
        """Notifications previously marked FAILED — used by the retry endpoint."""
        return (
            self.db.query(Notification)
            .filter(
                Notification.is_deleted.is_(False),
                Notification.status == NotificationStatus.FAILED,
            )
            .order_by(Notification.id.desc())
            .limit(limit)
            .all()
        )

    # ------- WRITE -------

    def create(
        self,
        *,
        channel: NotificationChannel,
        body: str,
        subject: Optional[str] = None,
        recipient_address: Optional[str] = None,
        user_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        template_id: Optional[int] = None,
        scheduled_at: Optional[datetime] = None,
        payload_metadata: Optional[dict] = None,
        status: NotificationStatus = NotificationStatus.PENDING,
    ) -> Notification:
        n = Notification(
            channel=channel,
            status=status,
            body=body,
            subject=subject,
            recipient_address=recipient_address,
            user_id=user_id,
            patient_id=patient_id,
            template_id=template_id,
            scheduled_at=scheduled_at,
            payload_metadata=payload_metadata,
        )
        self.db.add(n)
        self.db.flush()
        self.db.refresh(n)
        return n

    def save(self, n: Notification) -> Notification:
        self.db.add(n)
        self.db.flush()
        self.db.refresh(n)
        return n


class MessageRepository:
    """Lightweight persistence helpers for direct in-app messages."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, message_id: int) -> Optional[Message]:
        return (
            self.db.query(Message)
            .filter(Message.id == message_id, Message.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, message_id: int) -> Message:
        m = self.get_by_id(message_id)
        if not m:
            raise NotFoundError(message="Message not found.", detail={"message_id": message_id})
        return m

    def list_for_user(
        self,
        user_id: int,
        *,
        skip: int = 0,
        limit: int = 50,
        as_recipient: bool = True,
    ) -> tuple[list[Message], int]:
        query = self.db.query(Message).filter(Message.is_deleted.is_(False))
        if as_recipient:
            query = query.filter(Message.recipient_user_id == user_id)
        else:
            query = query.filter(Message.sender_user_id == user_id)
        total = query.with_entities(func.count(Message.id)).scalar() or 0
        items = query.order_by(Message.id.desc()).offset(skip).limit(limit).all()
        return items, int(total)

    def create(
        self,
        *,
        sender_user_id: Optional[int],
        recipient_user_id: int,
        subject: Optional[str],
        body: str,
    ) -> Message:
        m = Message(
            sender_user_id=sender_user_id,
            recipient_user_id=recipient_user_id,
            subject=subject,
            body=body,
            status=MessageStatus.SENT,
            sent_at=datetime.now(timezone.utc),
        )
        self.db.add(m)
        self.db.flush()
        self.db.refresh(m)
        return m

    def save(self, m: Message) -> Message:
        self.db.add(m)
        self.db.flush()
        self.db.refresh(m)
        return m
