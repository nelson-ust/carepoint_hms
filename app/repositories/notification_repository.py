# app/repositories/notification_repository.py
from __future__ import annotations

"""
Repository for the notifications module (Stage 17).

Persists ``NotificationTemplate``, ``Notification``, and the lightweight
``Message`` entity used for in-app system messaging. The retry queue is
implemented at the service layer using these primitives.
"""

from datetime import datetime, timezone
from typing import Optional, List, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.enums import NotificationChannel, NotificationStatus, MessageStatus
from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.all_models import Message, Notification, NotificationTemplate, Patient, User


class NotificationTemplateRepository:
    """Persistence helpers for ``NotificationTemplate``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, template_id: int) -> Optional[NotificationTemplate]:
        stmt = select(NotificationTemplate).filter(
            NotificationTemplate.id == template_id,
            NotificationTemplate.is_deleted.is_(False),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_required_by_id(self, template_id: int) -> NotificationTemplate:
        t = self.get_by_id(template_id)
        if not t:
            raise NotFoundError(message="Notification template not found.", detail={"template_id": template_id})
        return t

    def get_by_code(self, code: str) -> Optional[NotificationTemplate]:
        stmt = select(NotificationTemplate).filter(
            func.upper(NotificationTemplate.code) == code.strip().upper(),
            NotificationTemplate.is_deleted.is_(False),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_templates(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        channel: Optional[NotificationChannel] = None,
        search: Optional[str] = None,
    ) -> tuple[list[NotificationTemplate], int]:
        stmt = select(NotificationTemplate).filter(
            NotificationTemplate.is_deleted.is_(False)
        )
        if channel is not None:
            stmt = stmt.filter(NotificationTemplate.channel == channel)
        if search:
            term = f"%{search.strip().lower()}%"
            stmt = stmt.filter(
                or_(
                    func.lower(NotificationTemplate.name).like(term),
                    func.lower(NotificationTemplate.code).like(term),
                )
            )
        
        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar() or 0

        # Paginate
        stmt = stmt.order_by(NotificationTemplate.code.asc()).offset(skip).limit(limit)
        items = list(self.db.execute(stmt).scalars().all())
        
        return items, int(total)

    def create(self, **kwargs) -> NotificationTemplate:
        if self.get_by_code(kwargs["code"]):
            raise AlreadyExistsError(
                message="A template with this code already exists.",
                detail={"code": kwargs["code"]},
            )
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
        stmt = select(Notification).filter(
            Notification.id == notification_id,
            Notification.is_deleted.is_(False),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_required_by_id(self, notification_id: int) -> Notification:
        n = self.get_by_id(notification_id)
        if not n:
            raise NotFoundError(message="Notification not found.", detail={"notification_id": notification_id})
        return n

    def get_user(self, user_id: int) -> Optional[User]:
        stmt = select(User).filter(User.id == user_id, User.is_deleted.is_(False))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_patient(self, patient_id: int) -> Optional[Patient]:
        stmt = select(Patient).filter(Patient.id == patient_id, Patient.is_deleted.is_(False))
        return self.db.execute(stmt).scalar_one_or_none()

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
        unread_only: bool = False,
    ) -> tuple[list[Notification], int]:
        stmt = select(Notification).filter(Notification.is_deleted.is_(False))
        if user_id is not None:
            stmt = stmt.filter(Notification.user_id == user_id)
        if patient_id is not None:
            stmt = stmt.filter(Notification.patient_id == patient_id)
        if channel is not None:
            stmt = stmt.filter(Notification.channel == channel)
        if status is not None:
            stmt = stmt.filter(Notification.status == status)
        # "Unread" = anything the recipient has not yet acknowledged (READ).
        # Used so read notifications drop out of the inbox feed.
        if unread_only:
            stmt = stmt.filter(Notification.status != NotificationStatus.READ)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar() or 0

        # Paginate
        stmt = stmt.order_by(Notification.id.desc()).offset(skip).limit(limit)
        items = list(self.db.execute(stmt).scalars().all())

        return items, int(total)

    def count_unread(
        self,
        *,
        user_id: Optional[int] = None,
        patient_id: Optional[int] = None,
    ) -> int:
        """Count notifications the recipient has not yet marked READ."""
        stmt = select(func.count()).select_from(Notification).filter(
            Notification.is_deleted.is_(False),
            Notification.status != NotificationStatus.READ,
        )
        if user_id is not None:
            stmt = stmt.filter(Notification.user_id == user_id)
        if patient_id is not None:
            stmt = stmt.filter(Notification.patient_id == patient_id)
        return int(self.db.execute(stmt).scalar() or 0)

    def mark_read(self, notification: Notification) -> Notification:
        """Flip a single notification to READ and stamp ``read_at``."""
        notification.status = NotificationStatus.READ
        if notification.read_at is None:
            notification.read_at = datetime.now(timezone.utc)
        self.db.add(notification)
        self.db.flush()
        self.db.refresh(notification)
        return notification

    def mark_all_read(
        self,
        *,
        user_id: Optional[int] = None,
        patient_id: Optional[int] = None,
    ) -> int:
        """
        Mark every still-unread notification for the given recipient as READ.

        Returns the number of rows updated. At least one of ``user_id`` or
        ``patient_id`` must be supplied so we never touch another recipient's
        feed.
        """
        if user_id is None and patient_id is None:
            raise ValueError("mark_all_read requires user_id or patient_id.")

        stmt = select(Notification).filter(
            Notification.is_deleted.is_(False),
            Notification.status != NotificationStatus.READ,
        )
        if user_id is not None:
            stmt = stmt.filter(Notification.user_id == user_id)
        if patient_id is not None:
            stmt = stmt.filter(Notification.patient_id == patient_id)

        rows = list(self.db.execute(stmt).scalars().all())
        now = datetime.now(timezone.utc)
        for n in rows:
            n.status = NotificationStatus.READ
            if n.read_at is None:
                n.read_at = now
            self.db.add(n)
        self.db.flush()
        return len(rows)

    def list_pending(
        self,
        *,
        limit: int = 100,
        ready_at_or_before: Optional[datetime] = None,
    ) -> list[Notification]:
        cutoff = ready_at_or_before or datetime.now(timezone.utc)
        stmt = (
            select(Notification)
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
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_failed(self, *, limit: int = 100) -> list[Notification]:
        stmt = (
            select(Notification)
            .filter(
                Notification.is_deleted.is_(False),
                Notification.status == NotificationStatus.FAILED,
            )
            .order_by(Notification.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    # ------- WRITE -------

    def create(
        self,
        *,
        channel: NotificationChannel,
        body: str,
        subject: Optional[str] = None,
        body_html: Optional[str] = None,
        recipient_address: Optional[str] = None,
        user_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        template_id: Optional[int] = None,
        scheduled_at: Optional[datetime] = None,
        payload_metadata: Optional[dict] = None,
        status: NotificationStatus = NotificationStatus.PENDING,
        event_code: Optional[str] = None,
        sent_at: Optional[datetime] = None,
    ) -> Notification:
        n = Notification(
            channel=channel,
            status=status,
            body=body,
            body_html=body_html,
            subject=subject,
            recipient_address=recipient_address,
            user_id=user_id,
            patient_id=patient_id,
            template_id=template_id,
            scheduled_at=scheduled_at,
            payload_metadata=payload_metadata,
            event_code=event_code,
            sent_at=sent_at,
        )
        self.db.add(n)
        self.db.flush()
        self.db.refresh(n)
        return n

    def list_by_event(
        self,
        *,
        event_code: str,
        user_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        limit: int = 500,
    ) -> list[Notification]:
        """
        Fetch notifications carrying a specific ``event_code`` (e.g.
        ``appointment.reminder``). Used to de-duplicate event-driven
        notifications before creating a new one.
        """
        stmt = select(Notification).filter(
            Notification.is_deleted.is_(False),
            Notification.event_code == event_code,
        )
        if user_id is not None:
            stmt = stmt.filter(Notification.user_id == user_id)
        if patient_id is not None:
            stmt = stmt.filter(Notification.patient_id == patient_id)
        stmt = stmt.order_by(Notification.id.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

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
        stmt = select(Message).filter(Message.id == message_id, Message.is_deleted.is_(False))
        return self.db.execute(stmt).scalar_one_or_none()

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
        stmt = select(Message).filter(Message.is_deleted.is_(False))
        if as_recipient:
            stmt = stmt.filter(Message.recipient_user_id == user_id)
        else:
            stmt = stmt.filter(Message.sender_user_id == user_id)
        
        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar() or 0

        # Paginate
        stmt = stmt.order_by(Message.id.desc()).offset(skip).limit(limit)
        items = list(self.db.execute(stmt).scalars().all())
        
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
