# app/services/notification_service.py
from __future__ import annotations

"""
Service layer for the notifications module (Stage 17).

What this service does
----------------------
- Render templates with simple ``{name}`` placeholder substitution.
- Resolve recipient addresses (user.email / user.phone_number / patient.email / etc.)
  in a consent-aware way, falling back gracefully when contact info is missing.
- Hand off to channel adapters (email / SMS / WhatsApp / in-app) which are
  implemented as best-effort stubs that delegate to the corresponding
  ``app.utils`` helpers when available.
- Track every dispatch as a ``Notification`` row so ops can see who got what,
  retry the failed ones, and audit consent.
- Emit security events for high-signal transitions.

Design notes
------------
- Provider failures DO NOT raise out of the service when ``raise_on_failure``
  is False (the default for batched / scheduler-driven dispatch). The
  notification row is marked FAILED with a captured error and the caller is
  expected to retry via the bulk-retry endpoint.
- The retry endpoint is deliberately bounded by ``limit`` so a single call
  can't overwhelm a flaky provider.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.enums import NotificationChannel, NotificationStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import Message, Notification, NotificationTemplate
from app.repositories.notification_repository import (
    MessageRepository,
    NotificationRepository,
    NotificationTemplateRepository,
)
from app.schemas.notification_schema import (
    MessageCreateSchema,
    NotificationAdHocDispatchSchema,
    NotificationDispatchSchema,
    NotificationTemplateCreateSchema,
    NotificationTemplateUpdateSchema,
)
from app.utils.security_event_util import record_security_event


# Optional provider helpers — kept behind try/except so the service still
# works in environments where SMTP/Twilio aren't wired up. The adapters
# below treat missing helpers as a controlled "delivery skipped".
try:
    from app.utils.email_utils import send_email  # type: ignore[import-not-found]
except Exception:
    send_email = None  # type: ignore[assignment]

try:
    from app.utils.sms_util import send_sms, send_whatsapp_message  # type: ignore[import-not-found]
except Exception:
    send_sms = None  # type: ignore[assignment]
    send_whatsapp_message = None  # type: ignore[assignment]


# ============================================================
# TEMPLATE SERVICE
# ============================================================


class NotificationTemplateService:
    """CRUD over reusable notification templates."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = NotificationTemplateRepository(db)

    def list_templates(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        channel: Optional[str] = None,
        search: Optional[str] = None,
    ):
        channel_enum = NotificationChannel(channel.strip().upper()) if channel else None
        return self.repository.list_templates(
            skip=skip, limit=limit, channel=channel_enum, search=search,
        )

    def get(self, template_id: int) -> NotificationTemplate:
        return self.repository.get_required_by_id(template_id)

    def get_by_code(self, code: str) -> Optional[NotificationTemplate]:
        return self.repository.get_by_code(code)

    def create(self, payload: NotificationTemplateCreateSchema) -> NotificationTemplate:
        t = self.repository.create(**payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(t.id)

    def update(self, template_id: int, payload: NotificationTemplateUpdateSchema) -> NotificationTemplate:
        t = self.repository.get_required_by_id(template_id)
        updated = self.repository.update(t, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def soft_delete(self, template_id: int) -> NotificationTemplate:
        t = self.repository.get_required_by_id(template_id)
        t = self.repository.soft_delete(t)
        self.db.commit()
        return t


# ============================================================
# NOTIFICATION SERVICE
# ============================================================


class NotificationService:
    """Dispatch + lifecycle for ``Notification`` rows."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = NotificationRepository(db)
        self.template_repository = NotificationTemplateRepository(db)

    # ------- READS -------

    def list_notifications(self, **kwargs):
        # Translate optional string filters into enums.
        channel = kwargs.pop("channel", None)
        if channel is not None:
            kwargs["channel"] = NotificationChannel(channel.strip().upper())
        status = kwargs.pop("status", None)
        if status is not None:
            kwargs["status"] = NotificationStatus(status.strip().upper())
        return self.repository.list_notifications(**kwargs)

    def get(self, notification_id: int) -> Notification:
        return self.repository.get_required_by_id(notification_id)

    # ------- TEMPLATE RENDERING -------

    @staticmethod
    def _render(template_text: Optional[str], context: dict[str, Any]) -> Optional[str]:
        """
        Apply ``str.format_map`` with a SafeDict so missing placeholders
        render as empty strings instead of raising. This keeps the worker
        resilient when business events emit incomplete contexts.
        """
        if template_text is None:
            return None

        class SafeDict(dict):
            def __missing__(self, key):  # type: ignore[override]
                return ""

        try:
            return template_text.format_map(SafeDict(**context))
        except Exception:
            # Last-resort fallback: return the template as-is. Better to send
            # an unrendered notification than to silently drop it.
            return template_text

    # ------- RECIPIENT RESOLUTION -------

    def _resolve_recipient_address(
        self,
        *,
        channel: NotificationChannel,
        explicit: Optional[str],
        user_id: Optional[int],
        patient_id: Optional[int],
    ) -> Optional[str]:
        """
        Resolve a recipient address when one isn't supplied explicitly.

        - EMAIL → user.email or patient.email
        - SMS / WHATSAPP → user.phone_number or patient.phone_number
        - IN_APP → no address required (returns None)
        """
        if explicit and explicit.strip():
            return explicit.strip()
        if channel == NotificationChannel.IN_APP:
            return None

        target_user = self.repository.get_user(user_id) if user_id else None
        target_patient = self.repository.get_patient(patient_id) if patient_id else None

        if channel == NotificationChannel.EMAIL:
            for src in (target_user, target_patient):
                if src is not None and getattr(src, "email", None):
                    return getattr(src, "email")
        else:  # SMS / WHATSAPP
            for src in (target_user, target_patient):
                if src is not None and getattr(src, "phone_number", None):
                    return getattr(src, "phone_number")
        return None

    # ------- DISPATCH -------

    def dispatch_from_template(
        self,
        payload: NotificationDispatchSchema,
        *,
        actor_user_id: Optional[int] = None,
        raise_on_failure: bool = False,
    ) -> Notification:
        """
        Send a notification using a stored template.

        Resolves the template, renders subject + body, finds a recipient
        address, and hands off to a channel adapter. Persists a ``Notification``
        row regardless of provider success so failures are auditable.
        """
        # Resolve template — code preferred for stable integration keys.
        template: Optional[NotificationTemplate] = None
        if payload.template_id is not None:
            template = self.template_repository.get_required_by_id(payload.template_id)
        elif payload.template_code is not None:
            template = self.template_repository.get_by_code(payload.template_code)
            if template is None:
                raise NotFoundError(
                    message="Notification template not found.",
                    detail={"template_code": payload.template_code},
                )
        if template is None:
            raise BadRequestError(message="Template could not be resolved.")

        # Channel resolution: payload override or template default.
        channel = (
            NotificationChannel(payload.channel_override.strip().upper())
            if payload.channel_override
            else template.channel
        )

        # Render with the supplied context.
        rendered_subject = self._render(template.subject_template, payload.context)
        rendered_body = self._render(template.body_template, payload.context) or ""
        rendered_html = (
            self._render(getattr(template, "body_html", None), payload.context)
            if getattr(template, "body_html", None)
            else None
        ) or getattr(payload, "body_html", None)

        recipient = self._resolve_recipient_address(
            channel=channel,
            explicit=payload.recipient_address,
            user_id=payload.user_id,
            patient_id=payload.patient_id,
        )

        # Persist BEFORE attempting delivery so we have an audit row even if
        # the provider crashes mid-flight.
        notification = self.repository.create(
            channel=channel,
            body=rendered_body,
            body_html=rendered_html,
            subject=rendered_subject,
            recipient_address=recipient,
            user_id=payload.user_id,
            patient_id=payload.patient_id,
            template_id=template.id,
            scheduled_at=payload.scheduled_at,
            payload_metadata={"context": payload.context},
            status=NotificationStatus.PENDING,
        )

        # Scheduled future-dated notifications stay PENDING for the worker.
        if payload.scheduled_at and payload.scheduled_at > datetime.now(timezone.utc):
            self.db.commit()
            return self.repository.get_required_by_id(notification.id)

        self._deliver(
            notification,
            raise_on_failure=raise_on_failure,
            body_html=rendered_html,
        )
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="NOTIFICATION_DISPATCHED",
            severity="INFO",
            event_detail=f"Notification {notification.id} dispatched via {channel}.",
            event_metadata={
                "notification_id": notification.id,
                "channel": str(channel),
                "template_id": template.id,
                "status": str(notification.status),
            },
        )
        self.db.commit()
        return self.repository.get_required_by_id(notification.id)

    def dispatch_ad_hoc(
        self,
        payload: NotificationAdHocDispatchSchema,
        *,
        actor_user_id: Optional[int] = None,
        raise_on_failure: bool = False,
    ) -> Notification:
        """One-off dispatch without a template (operational alerts)."""
        channel = NotificationChannel(payload.channel)
        recipient = self._resolve_recipient_address(
            channel=channel,
            explicit=payload.recipient_address,
            user_id=payload.user_id,
            patient_id=payload.patient_id,
        )

        notification = self.repository.create(
            channel=channel,
            body=payload.body,
            body_html=getattr(payload, "body_html", None),
            subject=payload.subject,
            recipient_address=recipient,
            user_id=payload.user_id,
            patient_id=payload.patient_id,
            scheduled_at=payload.scheduled_at,
            status=NotificationStatus.PENDING,
        )
        if payload.scheduled_at and payload.scheduled_at > datetime.now(timezone.utc):
            self.db.commit()
            return self.repository.get_required_by_id(notification.id)

        self._deliver(
            notification,
            raise_on_failure=raise_on_failure,
            body_html=getattr(payload, "body_html", None),
        )
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="NOTIFICATION_AD_HOC_DISPATCHED",
            severity="INFO",
            event_detail=f"Ad-hoc notification {notification.id} dispatched via {channel}.",
            event_metadata={"notification_id": notification.id, "channel": str(channel)},
        )
        self.db.commit()
        return self.repository.get_required_by_id(notification.id)

    # ------- RETRY -------

    def retry_failed(
        self,
        *,
        limit: int = 50,
        actor_user_id: Optional[int] = None,
    ) -> dict:
        """
        Retry up to ``limit`` previously-failed notifications.

        Returns counts so the operator UI can show "5 retried, 3 sent, 2 still failing".
        """
        failed = self.repository.list_failed(limit=limit)
        sent = 0
        still_failed = 0
        for n in failed:
            n.status = NotificationStatus.PENDING
            self.repository.save(n)
            self._deliver(n, raise_on_failure=False)
            if n.status == NotificationStatus.SENT:
                sent += 1
            else:
                still_failed += 1

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="NOTIFICATION_BULK_RETRY",
            severity="INFO",
            event_detail=f"Bulk retry attempted on {len(failed)} notifications.",
            event_metadata={
                "retried": len(failed),
                "sent": sent,
                "still_failed": still_failed,
            },
        )
        self.db.commit()
        return {
            "retried": len(failed),
            "sent": sent,
            "failed": still_failed,
        }

    def mark_read(
        self,
        notification_id: int,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Notification:
        """Mark an in-app notification as READ. Useful for inbox UIs."""
        n = self.repository.get_required_by_id(notification_id)
        if n.channel != NotificationChannel.IN_APP:
            raise BadRequestError(
                message="Only in-app notifications can be marked READ.",
                detail={"channel": str(n.channel)},
            )
        n.status = NotificationStatus.READ
        self.repository.save(n)
        self.db.commit()
        return self.repository.get_required_by_id(n.id)

    # ------- INTERNAL -------

    def _deliver(self, notification: Notification, *, raise_on_failure: bool, body_html: Optional[str] = None) -> None:
        """
        Hand a notification to its channel adapter.

        On success: status flips to SENT.
        On failure: status flips to FAILED and the error is captured in
        ``payload_metadata['delivery_error']``.

        IN_APP notifications are considered delivered by virtue of being
        persisted (the inbox UI reads from the DB).
        """
        try:
            channel = notification.channel
            # Prefer an explicitly-passed HTML body, else the one persisted on
            # the row (so retries / async delivery keep the styled email).
            body_html = body_html or getattr(notification, "body_html", None)
            if channel == NotificationChannel.IN_APP:
                # In-app delivery is just persistence — the inbox UI polls
                # for unread rows.
                notification.status = NotificationStatus.SENT
            elif channel == NotificationChannel.EMAIL:
                if send_email is None:
                    raise RuntimeError("Email transport not configured.")
                if not notification.recipient_address:
                    raise RuntimeError("No email recipient resolved.")
                send_email(
                    subject=notification.subject or "(no subject)",
                    recipients=[notification.recipient_address],
                    body_text=notification.body,
                    body_html=body_html,
                )
                notification.status = NotificationStatus.SENT
            elif channel == NotificationChannel.SMS:
                if send_sms is None:
                    raise RuntimeError("SMS transport not configured.")
                if not notification.recipient_address:
                    raise RuntimeError("No phone recipient resolved.")
                send_sms(to=notification.recipient_address, body=notification.body)
                notification.status = NotificationStatus.SENT
            elif channel == NotificationChannel.WHATSAPP:
                if send_whatsapp_message is None:
                    raise RuntimeError("WhatsApp transport not configured.")
                if not notification.recipient_address:
                    raise RuntimeError("No phone recipient resolved.")
                send_whatsapp_message(to=notification.recipient_address, body=notification.body)
                notification.status = NotificationStatus.SENT
            else:
                # Future-proof: any channel we don't know about is captured
                # as FAILED rather than silently treated as success.
                raise RuntimeError(f"Unknown notification channel: {channel}")
        except Exception as exc:
            # Capture the error for the retry endpoint.
            notification.status = NotificationStatus.FAILED
            metadata = dict(notification.payload_metadata or {})
            metadata["delivery_error"] = str(exc)
            notification.payload_metadata = metadata
            self.repository.save(notification)
            if raise_on_failure:
                raise
            return

        self.repository.save(notification)


# ============================================================
# DIRECT MESSAGE SERVICE (in-app system messaging)
# ============================================================


class MessageService:
    """Lightweight direct-message between system users."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = MessageRepository(db)

    def list_inbox(self, user_id: int, *, skip: int = 0, limit: int = 50):
        return self.repository.list_for_user(user_id, skip=skip, limit=limit, as_recipient=True)

    def list_sent(self, user_id: int, *, skip: int = 0, limit: int = 50):
        return self.repository.list_for_user(user_id, skip=skip, limit=limit, as_recipient=False)

    def get(self, message_id: int) -> Message:
        return self.repository.get_required_by_id(message_id)

    def send(
        self,
        sender_user_id: int,
        payload: MessageCreateSchema,
    ) -> Message:
        # Self-messaging is allowed; useful for reminders. We don't restrict it.
        m = self.repository.create(
            sender_user_id=sender_user_id,
            recipient_user_id=payload.recipient_user_id,
            subject=payload.subject,
            body=payload.body,
        )
        self.db.commit()
        return self.repository.get_required_by_id(m.id)

    def mark_read(self, message_id: int) -> Message:
        from app.core.enums import MessageStatus
        m = self.repository.get_required_by_id(message_id)
        m.status = MessageStatus.READ
        m.read_at = datetime.now(timezone.utc)
        self.repository.save(m)
        self.db.commit()
        return self.repository.get_required_by_id(m.id)
