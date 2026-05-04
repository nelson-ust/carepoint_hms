"""
Tenant-aware, event-driven notification dispatcher.

This module sits on top of the lower-level :class:`NotificationService`
defined in ``app/services/notification_service.py``. Where the latter is
focused on per-channel CRUD and delivery, the dispatcher is the entry point
business code uses to *fire an event*::

    NotificationDispatcher(db).dispatch(
        event=NotificationEvent.INVOICE_CREATED,
        recipients=[user],
        context={"invoice_number": "INV-2026-000123", "amount": 12500},
    )

The dispatcher consults the tenant's :class:`TenantSetting` to decide which
channels to use for each event, persists a :class:`Notification` row per
delivery attempt, and best-effort dispatches to email / SMS / WhatsApp /
push providers. Quiet-hours are respected for SMS, WhatsApp, and push.

It is import-safe: provider helpers are imported lazily so missing optional
dependencies degrade to a logged "delivery skipped" rather than a hard
failure.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Sequence, Union

from sqlalchemy.orm import Session

from app.core.enums import (
    NotificationChannel,
    NotificationEvent,
    NotificationStatus,
)
from app.core.exceptions import BadRequestError
from app.models.all_models import (
    Notification,
    PushDeviceToken,
    User,
)
from app.services.tenant_setting_service import TenantSettingService


logger = logging.getLogger(__name__)


# Channels that should be suppressed during quiet-hours.
QUIET_HOUR_CHANNELS = {"sms", "whatsapp", "push"}


# ---------------------------------------------------------------------------
# Provider helpers (lazy-imported so the module stays import-safe).
# ---------------------------------------------------------------------------

def _send_email_safe(
    db,
    *,
    subject: str,
    recipients,
    body_text: str,
    body_html: Optional[str] = None,
) -> bool:
    """
    Send an email, preferring the tenant's own outbound-email
    configuration (per-tenant SMTP / SendGrid / Mailgun / etc.) and
    falling back to the platform-wide ``send_email`` helper only when
    no tenant config is set up.
    """
    try:
        from app.services.tenant_email_service import send_tenant_email
    except Exception:
        send_tenant_email = None  # type: ignore[assignment]

    if send_tenant_email is not None:
        try:
            return bool(
                send_tenant_email(
                    db,
                    subject=subject,
                    recipients=list(recipients),
                    body_text=body_text,
                    body_html=body_html,
                )
            )
        except Exception as exc:
            logger.warning("send_tenant_email failed; falling back to platform: %s", exc)

    # Fallback: platform-wide SMTP.
    try:
        from app.utils.email_utils import send_email  # type: ignore
    except Exception:
        logger.warning("send_email helper unavailable")
        return False
    try:
        send_email(subject=subject, recipients=list(recipients), body_text=body_text)
        return True
    except Exception as exc:
        logger.exception("send_email failed: %s", exc)
        return False


def _send_sms_safe(to: str, body: str) -> bool:
    try:
        from app.utils.sms_util import send_sms  # type: ignore
    except Exception:
        logger.warning("send_sms helper unavailable")
        return False
    try:
        send_sms(to=to, body=body)
        return True
    except Exception as exc:
        logger.exception("send_sms failed: %s", exc)
        return False


def _send_whatsapp_safe(to: str, body: str) -> bool:
    try:
        from app.utils.sms_util import send_whatsapp_message  # type: ignore
    except Exception:
        logger.warning("send_whatsapp_message helper unavailable")
        return False
    try:
        send_whatsapp_message(to=to, body=body)
        return True
    except Exception as exc:
        logger.exception("send_whatsapp_message failed: %s", exc)
        return False


def _send_push_safe(device_token: str, title: Optional[str], body: str, data: Optional[dict]) -> bool:
    try:
        from app.utils.push_util import send_push  # type: ignore
    except Exception:
        logger.warning("send_push helper unavailable")
        return False
    return bool(send_push(device_token=device_token, title=title, body=body, data=data))


# ---------------------------------------------------------------------------
# Channel code mapping
# ---------------------------------------------------------------------------

_CODE_TO_ENUM = {
    "in_app": NotificationChannel.IN_APP,
    "email": NotificationChannel.EMAIL,
    "sms": NotificationChannel.SMS,
    "whatsapp": NotificationChannel.WHATSAPP,
    "push": NotificationChannel.PUSH,
}


def _coerce_event_code(event: Union[str, NotificationEvent]) -> str:
    if isinstance(event, NotificationEvent):
        return str(event.value)
    return str(event).strip().lower()


def _render_template(template: Optional[str], context: dict[str, Any]) -> str:
    if not template:
        return ""
    try:
        return template.format(**context)
    except Exception:
        return template


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class NotificationDispatcher:
    """
    Fire a tenant-aware notification event across all configured channels.

    Persists one :class:`Notification` row per (recipient, channel) attempt
    and returns the list of created records.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = TenantSettingService(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def dispatch(
        self,
        *,
        event: Union[str, NotificationEvent],
        recipients: Iterable[Union[User, dict, int]],
        subject: Optional[str] = None,
        body: str = "",
        body_template: Optional[str] = None,
        subject_template: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        force_channels: Optional[Sequence[str]] = None,
        suppress_quiet_hours: bool = True,
    ) -> list[Notification]:
        """
        Dispatch a notification event.

        Args
        ----
        event:
            Canonical event code (NotificationEvent or string).
        recipients:
            Iterable of User instances, ``{"user_id": ..., ...}`` dicts, or
            bare user IDs.
        body / body_template:
            Either a pre-rendered ``body`` or a ``body_template`` to render
            against ``context``.
        force_channels:
            If provided, bypass tenant settings and use these channels.
        suppress_quiet_hours:
            When True (default) and the tenant is currently inside its quiet
            hours window, SMS / WhatsApp / push are skipped (in-app + email
            still go out).
        """
        event_code = _coerce_event_code(event)
        ctx = dict(context or {})

        rendered_body = body or _render_template(body_template, ctx)
        rendered_subject = subject or _render_template(subject_template, ctx)
        if not rendered_body:
            raise BadRequestError(message="Notification body must not be empty.")

        if force_channels:
            channels = [c for c in force_channels if c in _CODE_TO_ENUM]
        else:
            channels = self.settings.get_channels_for_event(event_code)

        if suppress_quiet_hours and self.settings.is_in_quiet_hours():
            channels = [c for c in channels if c not in QUIET_HOUR_CHANNELS]

        if not channels:
            logger.info(
                "NotificationDispatcher: no channels resolved for event %s; nothing sent.",
                event_code,
            )
            return []

        created: list[Notification] = []
        for raw in recipients:
            user = self._resolve_user(raw)
            for channel in channels:
                notif = self._create_record(
                    user=user,
                    raw_recipient=raw,
                    event_code=event_code,
                    channel=channel,
                    subject=rendered_subject,
                    body=rendered_body,
                    payload_metadata={"event": event_code, "context": ctx},
                )
                self._deliver(notif, user=user, channel=channel)
                created.append(notif)

        self.db.commit()
        return created

    # ------------------------------------------------------------------
    # Recipient resolution
    # ------------------------------------------------------------------

    def _resolve_user(self, raw: Union[User, dict, int]) -> Optional[User]:
        if isinstance(raw, User):
            return raw
        if isinstance(raw, int):
            return self.db.query(User).filter(User.id == raw, User.is_deleted.is_(False)).first()
        if isinstance(raw, dict):
            uid = raw.get("user_id") or raw.get("id")
            if uid is not None:
                return (
                    self.db.query(User)
                    .filter(User.id == int(uid), User.is_deleted.is_(False))
                    .first()
                )
        return None

    def _resolve_address(self, *, user: Optional[User], raw: Any, channel: str) -> Optional[str]:
        if isinstance(raw, dict):
            override = raw.get(f"{channel}_address") or raw.get("address")
            if override:
                return override
        if user is None:
            return None
        if channel == "email":
            return getattr(user, "email", None)
        if channel in {"sms", "whatsapp"}:
            return getattr(user, "phone_number", None)
        if channel == "in_app":
            return str(user.id)
        if channel == "push":
            # Push uses device tokens, not a single address; signal via empty
            # string so we know to look them up at delivery time.
            return ""
        return None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _create_record(
        self,
        *,
        user: Optional[User],
        raw_recipient: Any,
        event_code: str,
        channel: str,
        subject: Optional[str],
        body: str,
        payload_metadata: dict[str, Any],
    ) -> Notification:
        address = self._resolve_address(user=user, raw=raw_recipient, channel=channel)
        notif = Notification(
            user_id=user.id if user else None,
            event_code=event_code,
            channel=_CODE_TO_ENUM[channel],
            status=NotificationStatus.PENDING,
            recipient_address=address,
            subject=subject,
            body=body,
            payload_metadata=payload_metadata,
        )
        self.db.add(notif)
        self.db.flush()
        return notif

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------

    def _deliver(
        self,
        notif: Notification,
        *,
        user: Optional[User],
        channel: str,
    ) -> None:
        ok = False
        try:
            if channel == "in_app":
                # In-app delivery is satisfied by persisting the row.
                ok = True

            elif channel == "email":
                if not notif.recipient_address:
                    raise RuntimeError("missing email address")
                ok = _send_email_safe(
                    self.db,
                    subject=notif.subject or "Notification",
                    recipients=[notif.recipient_address],
                    body_text=notif.body,
                )

            elif channel == "sms":
                if not notif.recipient_address:
                    raise RuntimeError("missing phone number")
                ok = _send_sms_safe(to=notif.recipient_address, body=notif.body)

            elif channel == "whatsapp":
                if not notif.recipient_address:
                    raise RuntimeError("missing phone number")
                ok = _send_whatsapp_safe(to=notif.recipient_address, body=notif.body)

            elif channel == "push":
                ok = self._deliver_push(notif=notif, user=user)

            else:
                raise RuntimeError(f"unsupported channel '{channel}'")

        except Exception as exc:
            ok = False
            notif.failure_reason = str(exc)[:500]

        now = datetime.now(timezone.utc)
        if ok:
            notif.status = NotificationStatus.SENT
            notif.sent_at = now
        else:
            notif.status = NotificationStatus.FAILED
            notif.retry_count = (notif.retry_count or 0) + 1
            if not notif.failure_reason:
                notif.failure_reason = "delivery skipped"

    def _deliver_push(self, *, notif: Notification, user: Optional[User]) -> bool:
        if user is None:
            notif.failure_reason = "push requires a user"
            return False

        tokens = (
            self.db.query(PushDeviceToken)
            .filter(
                PushDeviceToken.user_id == user.id,
                PushDeviceToken.is_active.is_(True),
                PushDeviceToken.is_deleted.is_(False),
            )
            .all()
        )
        if not tokens:
            notif.failure_reason = "no registered push devices"
            return False

        any_ok = False
        for tok in tokens:
            ok = _send_push_safe(
                device_token=tok.device_token,
                title=notif.subject,
                body=notif.body,
                data=(notif.payload_metadata or {}).get("context"),
            )
            if ok:
                tok.last_used_at = datetime.now(timezone.utc)
                any_ok = True
            else:
                # Soft-disable obviously broken tokens.
                tok.is_active = False
        return any_ok
