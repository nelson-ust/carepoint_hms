# app/services/whatsapp_service.py
"""Meta WhatsApp Business Platform (Cloud API) integration.

This module powers three things:

* **Webhook verification** — the GET ``hub.challenge`` handshake and the
  POST ``X-Hub-Signature-256`` HMAC check.
* **Webhook processing** — routing each delivery to the right tenant (by
  ``phone_number_id``), logging the raw payload for audit + idempotency,
  parsing inbound messages into per-tenant conversations/messages, applying
  outbound delivery-status updates, linking the sender to a patient, and
  notifying staff.
* **Outbound messaging** — sending text/template messages via the Cloud API
  and persisting them so their delivery status can be tracked.

Meta delivers every webhook to one app-level URL, so the receiver itself runs
without tenant context: it resolves the tenant from the payload and opens that
tenant's database explicitly.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


# ============================================================
# Pure parsing helpers (no DB) — unit-testable in isolation
# ============================================================

def normalize_phone(value: Optional[str]) -> str:
    """Reduce a phone/wa_id to digits only for tolerant matching."""
    if not value:
        return ""
    return "".join(ch for ch in str(value) if ch.isdigit())


def phone_suffix(value: Optional[str], length: int = 10) -> str:
    digits = normalize_phone(value)
    return digits[-length:] if digits else ""


def epoch_to_dt(value: Any) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


_TYPE_MAP = {
    "text": "TEXT", "image": "IMAGE", "audio": "AUDIO", "video": "VIDEO",
    "document": "DOCUMENT", "sticker": "STICKER", "location": "LOCATION",
    "contacts": "CONTACTS", "interactive": "INTERACTIVE", "button": "BUTTON",
    "reaction": "REACTION", "order": "ORDER", "system": "SYSTEM",
    "unsupported": "UNSUPPORTED",
}

_MEDIA_TYPES = {"image", "audio", "video", "document", "sticker"}

_STATUS_MAP = {
    "sent": "SENT", "delivered": "DELIVERED", "read": "READ",
    "failed": "FAILED", "deleted": "DELETED", "accepted": "ACCEPTED",
}


def extract_message_content(message: dict) -> dict:
    """Normalise a single inbound message object into a flat dict, tolerating
    every message type Meta may send (text, media, location, interactive, …)."""
    raw_type = (message.get("type") or "unknown").lower()
    message_type = _TYPE_MAP.get(raw_type, "UNKNOWN")
    body: Optional[str] = None
    caption: Optional[str] = None
    media_id: Optional[str] = None
    media_mime: Optional[str] = None
    media_filename: Optional[str] = None

    if raw_type == "text":
        body = (message.get("text") or {}).get("body")
    elif raw_type in _MEDIA_TYPES:
        media = message.get(raw_type) or {}
        media_id = media.get("id")
        media_mime = media.get("mime_type")
        media_filename = media.get("filename")
        caption = media.get("caption")
        body = caption
    elif raw_type == "location":
        loc = message.get("location") or {}
        parts = [str(loc.get("latitude", "")), str(loc.get("longitude", ""))]
        body = loc.get("name") or ", ".join(p for p in parts if p)
    elif raw_type == "button":
        body = (message.get("button") or {}).get("text")
    elif raw_type == "interactive":
        inter = message.get("interactive") or {}
        reply = inter.get("button_reply") or inter.get("list_reply") or {}
        body = reply.get("title") or reply.get("description")
    elif raw_type == "reaction":
        reaction = message.get("reaction") or {}
        body = reaction.get("emoji")
    elif raw_type == "order":
        body = "[order]"
    else:
        # Unknown / unsupported — keep a hint for the operator.
        errors = message.get("errors") or []
        if errors:
            body = errors[0].get("title") or "[unsupported message]"
        else:
            body = f"[{raw_type}]"

    return {
        "wa_message_id": message.get("id"),
        "from_number": message.get("from"),
        "message_type": message_type,
        "body": body,
        "caption": caption,
        "media_id": media_id,
        "media_mime_type": media_mime,
        "media_filename": media_filename,
        "wa_timestamp": epoch_to_dt(message.get("timestamp")),
        "raw": message,
    }


def parse_change_value(value: dict) -> dict:
    """Normalise a webhook ``entry.changes[].value`` object into contacts,
    inbound messages, and outbound statuses."""
    metadata = value.get("metadata") or {}
    contacts = {}
    for contact in value.get("contacts") or []:
        wa_id = contact.get("wa_id")
        if wa_id:
            contacts[wa_id] = (contact.get("profile") or {}).get("name")

    messages = [extract_message_content(m) for m in (value.get("messages") or [])]

    statuses = []
    for st in value.get("statuses") or []:
        errors = st.get("errors") or []
        err0 = errors[0] if errors else {}
        statuses.append({
            "wa_message_id": st.get("id"),
            "status": _STATUS_MAP.get((st.get("status") or "").lower(), "UNKNOWN"),
            "recipient_id": st.get("recipient_id"),
            "timestamp": epoch_to_dt(st.get("timestamp")),
            "error_code": str(err0.get("code")) if err0.get("code") is not None else None,
            "error_title": err0.get("title") or err0.get("message"),
            "raw": st,
        })

    return {
        "phone_number_id": metadata.get("phone_number_id"),
        "display_phone_number": metadata.get("display_phone_number"),
        "contacts": contacts,
        "messages": messages,
        "statuses": statuses,
    }


def verify_subscription(mode: Optional[str], token: Optional[str],
                        challenge: Optional[str], expected_tokens) -> Optional[str]:
    """Return the challenge string when the GET verification handshake is valid,
    else None. ``expected_tokens`` is any iterable of acceptable verify tokens."""
    valid = {t for t in (expected_tokens or []) if t}
    if mode == "subscribe" and token and token in valid:
        return challenge
    return None


def verify_signature(raw_body: bytes, signature_header: Optional[str],
                     app_secret: Optional[str]) -> bool:
    """Validate Meta's ``X-Hub-Signature-256: sha256=<hex>`` header against the
    raw request body using the app secret (constant-time compare)."""
    if not app_secret or not signature_header:
        return False
    header = signature_header.strip()
    if header.startswith("sha256="):
        header = header[len("sha256="):]
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, header)


# ============================================================
# Config service (master DB) — number -> tenant mapping
# ============================================================

class WhatsAppConfigService:
    def __init__(self, master_db: Session) -> None:
        self.db = master_db

    def resolve(self, phone_number_id: str):
        from app.models.all_models import WhatsAppAccountConfig
        if not phone_number_id:
            return None
        return (
            self.db.query(WhatsAppAccountConfig)
            .filter(WhatsAppAccountConfig.phone_number_id == str(phone_number_id),
                    WhatsAppAccountConfig.is_deleted.is_(False))
            .first()
        )

    def resolve_for_tenant(self, tenant_id: int):
        from app.models.all_models import WhatsAppAccountConfig
        return (
            self.db.query(WhatsAppAccountConfig)
            .filter(WhatsAppAccountConfig.tenant_id == tenant_id,
                    WhatsAppAccountConfig.is_active.is_(True),
                    WhatsAppAccountConfig.is_deleted.is_(False))
            .order_by(WhatsAppAccountConfig.id.asc())
            .first()
        )

    def list_for_tenant(self, tenant_id: int):
        from app.models.all_models import WhatsAppAccountConfig
        return (
            self.db.query(WhatsAppAccountConfig)
            .filter(WhatsAppAccountConfig.tenant_id == tenant_id,
                    WhatsAppAccountConfig.is_deleted.is_(False))
            .order_by(WhatsAppAccountConfig.id.asc())
            .all()
        )

    @staticmethod
    def _encrypt(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        from app.core.cryptography import encrypt_string
        return encrypt_string(value)

    @staticmethod
    def decrypt(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        from app.core.cryptography import decrypt_string
        try:
            return decrypt_string(value)
        except Exception:
            return None

    def upsert(self, tenant_id: int, data: dict):
        """Create or update the mapping for ``data['phone_number_id']``."""
        from app.models.all_models import WhatsAppAccountConfig
        from app.core.exceptions import BadRequestError

        pnid = (data.get("phone_number_id") or "").strip()
        if not pnid:
            raise BadRequestError(message="phone_number_id is required.")

        cfg = self.resolve(pnid)
        if cfg is not None and cfg.tenant_id != tenant_id:
            raise BadRequestError(
                message="This WhatsApp phone number is already mapped to another tenant.")
        if cfg is None:
            cfg = WhatsAppAccountConfig(tenant_id=tenant_id, phone_number_id=pnid)
            self.db.add(cfg)

        for field in ("waba_id", "display_phone_number", "business_name"):
            if field in data and data[field] is not None:
                setattr(cfg, field, str(data[field]).strip() or None)
        if "notify_role_codes" in data:
            cfg.notify_role_codes = data.get("notify_role_codes") or None
        if data.get("access_token"):
            cfg.access_token_encrypted = self._encrypt(data["access_token"])
        if data.get("verify_token"):
            cfg.verify_token_encrypted = self._encrypt(data["verify_token"])
        if data.get("app_secret"):
            cfg.app_secret_encrypted = self._encrypt(data["app_secret"])
        if "is_active" in data and data["is_active"] is not None:
            cfg.is_active = bool(data["is_active"])

        self.db.commit()
        self.db.refresh(cfg)
        return cfg

    def to_dict(self, cfg) -> dict:
        return {
            "id": cfg.id,
            "tenant_id": cfg.tenant_id,
            "phone_number_id": cfg.phone_number_id,
            "waba_id": cfg.waba_id,
            "display_phone_number": cfg.display_phone_number,
            "business_name": cfg.business_name,
            "notify_role_codes": cfg.notify_role_codes or [],
            "is_active": cfg.is_active,
            "has_access_token": bool(cfg.access_token_encrypted),
            "has_app_secret": bool(cfg.app_secret_encrypted),
            "has_verify_token": bool(cfg.verify_token_encrypted),
            "created_at": getattr(cfg, "created_at", None),
        }


# ============================================================
# Cloud API client (outbound)
# ============================================================

class WhatsAppCloudClient:
    """Thin Cloud API HTTP client. Raises for HTTP errors so callers can record
    a FAILED message."""

    def __init__(self, access_token: str, phone_number_id: str,
                 *, base_url: Optional[str] = None, api_version: Optional[str] = None,
                 timeout: float = 15.0) -> None:
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.base_url = (base_url or settings.WHATSAPP_API_BASE_URL).rstrip("/")
        self.api_version = api_version or settings.WHATSAPP_API_VERSION
        self.timeout = timeout

    @property
    def _url(self) -> str:
        return f"{self.base_url}/{self.api_version}/{self.phone_number_id}/messages"

    def send(self, payload: dict) -> dict:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self._url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()


# ============================================================
# Webhook processing service (master + per-tenant routing)
# ============================================================

class WhatsAppWebhookService:
    def __init__(self, master_db: Session) -> None:
        self.master_db = master_db
        self.config_service = WhatsAppConfigService(master_db)

    # -- verification helpers exposed for the route ---------------------------
    def acceptable_verify_tokens(self) -> list:
        tokens = []
        if settings.WHATSAPP_VERIFY_TOKEN:
            tokens.append(settings.WHATSAPP_VERIFY_TOKEN.get_secret_value())
        # per-number verify tokens (webhook overrides)
        try:
            from app.models.all_models import WhatsAppAccountConfig
            rows = (self.master_db.query(WhatsAppAccountConfig)
                    .filter(WhatsAppAccountConfig.verify_token_encrypted.isnot(None),
                            WhatsAppAccountConfig.is_deleted.is_(False)).all())
            for r in rows:
                dec = WhatsAppConfigService.decrypt(r.verify_token_encrypted)
                if dec:
                    tokens.append(dec)
        except Exception:
            logger.exception("Failed loading per-number WhatsApp verify tokens")
        return tokens

    def app_secret(self) -> Optional[str]:
        if settings.WHATSAPP_APP_SECRET:
            return settings.WHATSAPP_APP_SECRET.get_secret_value()
        return None

    # -- main entry point -----------------------------------------------------
    def handle_event(self, raw_body: bytes, payload: dict) -> dict:
        """Log + route a webhook delivery. Never raises for per-item problems;
        the caller should always return HTTP 200 so Meta does not retry for 7
        days on a transient processing hiccup."""
        payload_hash = hashlib.sha256(raw_body or b"").hexdigest()
        event = self._record_raw_event(payload_hash, payload)
        if event is None:
            # Duplicate delivery (same body hash) — idempotent no-op.
            return {"status": "duplicate"}

        routed = 0
        processed = 0
        errors = []
        object_type = payload.get("object")
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                field = change.get("field")
                value = change.get("value") or {}
                parsed = parse_change_value(value)
                pnid = parsed.get("phone_number_id")
                if event.field is None:
                    event.field = field
                if event.phone_number_id is None:
                    event.phone_number_id = pnid
                if event.waba_id is None:
                    event.waba_id = entry.get("id")
                if event.object_type is None:
                    event.object_type = object_type

                if field != "messages":
                    # Non-message webhooks (template/account/quality updates,
                    # etc.) are logged for audit; deeper handling can be layered
                    # on later. Nothing tenant-specific to persist here.
                    continue

                config = self.config_service.resolve(pnid) if pnid else None
                if config is None:
                    errors.append(f"unrouted phone_number_id={pnid}")
                    continue

                event.tenant_id = config.tenant_id
                routed += 1
                try:
                    self._route_to_tenant(config, parsed)
                    processed += 1
                except Exception as exc:  # never fail the whole delivery
                    logger.exception("WhatsApp change processing failed")
                    errors.append(str(exc))

        event.routed = routed > 0
        event.processed = not errors
        event.processing_error = "; ".join(errors)[:2000] if errors else None
        self.master_db.commit()
        return {"status": "processed", "routed": routed, "processed": processed,
                "errors": errors}

    # -- internals ------------------------------------------------------------
    def _record_raw_event(self, payload_hash: str, payload: dict):
        from app.models.all_models import WhatsAppWebhookEvent
        existing = (self.master_db.query(WhatsAppWebhookEvent)
                    .filter(WhatsAppWebhookEvent.payload_hash == payload_hash)
                    .first())
        if existing is not None:
            return None
        event = WhatsAppWebhookEvent(
            payload_hash=payload_hash,
            payload_json=payload,
            object_type=payload.get("object"),
        )
        self.master_db.add(event)
        self.master_db.flush()
        return event

    def _route_to_tenant(self, config, parsed: dict) -> None:
        from app.core.database import get_tenant_db_context
        with get_tenant_db_context(config.tenant_id) as tenant_db:
            processor = _TenantMessageProcessor(tenant_db, config)
            processor.apply(parsed)
            tenant_db.commit()


class _TenantMessageProcessor:
    """Applies a parsed change to one tenant DB: upserts the conversation,
    inserts inbound messages, updates outbound statuses, links the patient, and
    notifies staff."""

    def __init__(self, tenant_db: Session, config) -> None:
        self.db = tenant_db
        self.config = config
        self.phone_number_id = config.phone_number_id

    def apply(self, parsed: dict) -> None:
        for msg in parsed.get("messages") or []:
            self._ingest_inbound(msg, parsed.get("contacts") or {})
        for status in parsed.get("statuses") or []:
            self._apply_status(status)

    # -- inbound --------------------------------------------------------------
    def _ingest_inbound(self, msg: dict, contacts: dict) -> None:
        from app.models.all_models import WhatsAppMessage
        wamid = msg.get("wa_message_id")
        if wamid:
            existing = (self.db.query(WhatsAppMessage)
                        .filter(WhatsAppMessage.wa_message_id == wamid).first())
            if existing is not None:
                return  # idempotent — retried delivery

        wa_id = msg.get("from_number")
        contact_name = contacts.get(wa_id)
        conversation = self._get_or_create_conversation(wa_id, contact_name)

        record = WhatsAppMessage(
            conversation_id=conversation.id,
            wa_message_id=wamid,
            direction="INBOUND",
            from_number=wa_id,
            to_number=self.config.display_phone_number,
            phone_number_id=self.phone_number_id,
            message_type=msg.get("message_type") or "UNKNOWN",
            body=msg.get("body"),
            caption=msg.get("caption"),
            media_id=msg.get("media_id"),
            media_mime_type=msg.get("media_mime_type"),
            media_filename=msg.get("media_filename"),
            patient_id=conversation.patient_id,
            wa_timestamp=msg.get("wa_timestamp"),
            raw_json=msg.get("raw"),
        )
        self.db.add(record)

        ts = msg.get("wa_timestamp")
        conversation.last_message_at = ts
        conversation.last_inbound_at = ts
        conversation.unread_count = (conversation.unread_count or 0) + 1
        self.db.add(conversation)
        self.db.flush()

        self._notify_staff(conversation, record)

    def _get_or_create_conversation(self, wa_id: str, contact_name: Optional[str]):
        from app.models.all_models import WhatsAppConversation
        conversation = (self.db.query(WhatsAppConversation)
                        .filter(WhatsAppConversation.phone_number_id == self.phone_number_id,
                                WhatsAppConversation.wa_id == wa_id).first())
        if conversation is None:
            conversation = WhatsAppConversation(
                phone_number_id=self.phone_number_id,
                wa_id=wa_id,
                contact_name=contact_name,
                status="OPEN",
                unread_count=0,
                patient_id=self._match_patient_id(wa_id),
            )
            self.db.add(conversation)
            self.db.flush()
        else:
            if contact_name and not conversation.contact_name:
                conversation.contact_name = contact_name
            if conversation.patient_id is None:
                conversation.patient_id = self._match_patient_id(wa_id)
        return conversation

    def _match_patient_id(self, wa_id: str) -> Optional[int]:
        from app.models.all_models import Patient
        suffix = phone_suffix(wa_id, 10)
        if not suffix:
            return None
        try:
            patient = (self.db.query(Patient)
                       .filter(Patient.is_deleted.is_(False))
                       .filter((Patient.phone_number.like(f"%{suffix}"))
                               | (Patient.alternate_phone_number.like(f"%{suffix}")))
                       .first())
            return patient.id if patient else None
        except Exception:
            logger.exception("WhatsApp patient match failed")
            return None

    def _notify_staff(self, conversation, record) -> None:
        try:
            recipients = self._recipient_ids()
            if not recipients:
                return
            from app.services.notification_dispatcher import NotificationDispatcher
            from app.core.enums import NotificationEvent
            who = conversation.contact_name or conversation.wa_id
            preview = (record.body or f"[{record.message_type.lower()}]")[:160]
            NotificationDispatcher(self.db).dispatch(
                event=NotificationEvent.WHATSAPP_MESSAGE_RECEIVED,
                recipients=recipients,
                subject=f"New WhatsApp message from {who}",
                body=preview,
                context={"wa_id": conversation.wa_id,
                         "conversation_id": conversation.id,
                         "patient_id": conversation.patient_id},
            )
        except Exception:
            logger.exception("WhatsApp inbound notification failed")

    def _recipient_ids(self) -> list:
        from app.models.all_models import User, Role, UserRoleAssociation
        ids = set()
        try:
            supers = (self.db.query(User.id)
                      .filter(User.is_superuser.is_(True),
                              User.is_active.is_(True),
                              User.is_deleted.is_(False)).all())
            ids.update(uid for (uid,) in supers)
            role_codes = self.config.notify_role_codes or []
            if role_codes:
                rows = (self.db.query(User.id)
                        .join(UserRoleAssociation, UserRoleAssociation.user_id == User.id)
                        .join(Role, Role.id == UserRoleAssociation.role_id)
                        .filter(Role.code.in_(role_codes),
                                User.is_active.is_(True),
                                User.is_deleted.is_(False)).all())
                ids.update(uid for (uid,) in rows)
        except Exception:
            logger.exception("WhatsApp recipient resolution failed")
        return list(ids)

    # -- outbound status ------------------------------------------------------
    def _apply_status(self, status: dict) -> None:
        from app.models.all_models import WhatsAppMessage
        wamid = status.get("wa_message_id")
        if not wamid:
            return
        message = (self.db.query(WhatsAppMessage)
                   .filter(WhatsAppMessage.wa_message_id == wamid).first())
        if message is None:
            return  # status for a message we didn't send/record
        new_status = status.get("status")
        if new_status and new_status != "UNKNOWN" and not _status_is_regression(message.status, new_status):
            message.status = new_status
        message.status_updated_at = status.get("timestamp")
        if status.get("error_code"):
            message.error_code = status.get("error_code")
            message.error_title = status.get("error_title")
        self.db.add(message)


_STATUS_ORDER = {"ACCEPTED": 0, "SENT": 1, "DELIVERED": 2, "READ": 3}


def _status_is_regression(current: Optional[str], incoming: str) -> bool:
    """Prevent an out-of-order status (e.g. a late 'sent' after 'read') from
    moving the message backwards. FAILED/DELETED always apply."""
    if incoming in ("FAILED", "DELETED"):
        return False
    if current not in _STATUS_ORDER or incoming not in _STATUS_ORDER:
        return False
    return _STATUS_ORDER[incoming] < _STATUS_ORDER[current]


# ============================================================
# Outbound send service (tenant context)
# ============================================================

class WhatsAppOutboundService:
    """Sends outbound messages for the *current* tenant and persists them so
    delivery status can be tracked via the statuses webhook. Constructed with
    the tenant request session; resolves the number's credentials from master."""

    def __init__(self, tenant_db: Session, master_db: Session, tenant_id: int) -> None:
        self.db = tenant_db
        self.master_db = master_db
        self.tenant_id = tenant_id
        self.config_service = WhatsAppConfigService(master_db)

    def _resolve_credentials(self):
        from app.core.exceptions import BadRequestError
        cfg = self.config_service.resolve_for_tenant(self.tenant_id)
        phone_number_id = None
        access_token = None
        display_number = None
        notify = None
        if cfg is not None:
            phone_number_id = cfg.phone_number_id
            access_token = WhatsAppConfigService.decrypt(cfg.access_token_encrypted)
            display_number = cfg.display_phone_number
        # Global fallbacks
        if not phone_number_id:
            phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        if not access_token and settings.WHATSAPP_ACCESS_TOKEN:
            access_token = settings.WHATSAPP_ACCESS_TOKEN.get_secret_value()
        if not phone_number_id or not access_token:
            raise BadRequestError(
                message="WhatsApp is not configured for this tenant "
                        "(missing phone_number_id or access token).")
        return phone_number_id, access_token, display_number

    def send_text(self, to: str, body: str, *, sender_user_id: Optional[int] = None,
                  preview_url: bool = False) -> "object":
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": normalize_phone(to),
            "type": "text",
            "text": {"preview_url": preview_url, "body": body},
        }
        return self._send(payload, to=to, body=body, message_type="TEXT",
                          sender_user_id=sender_user_id)

    def send_template(self, to: str, template_name: str, language_code: str = "en_US",
                      components: Optional[list] = None, *,
                      sender_user_id: Optional[int] = None) -> "object":
        template: dict = {"name": template_name, "language": {"code": language_code}}
        if components:
            template["components"] = components
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": normalize_phone(to),
            "type": "template",
            "template": template,
        }
        return self._send(payload, to=to, body=f"[template:{template_name}]",
                          message_type="TEMPLATE", sender_user_id=sender_user_id)

    def _send(self, payload: dict, *, to: str, body: Optional[str],
              message_type: str, sender_user_id: Optional[int]):
        from app.models.all_models import WhatsAppMessage, WhatsAppConversation
        from app.core.exceptions import BadRequestError

        if not settings.WHATSAPP_ENABLED:
            raise BadRequestError(message="WhatsApp sending is disabled.")

        phone_number_id, access_token, display_number = self._resolve_credentials()
        wa_id = normalize_phone(to)

        conversation = (self.db.query(WhatsAppConversation)
                        .filter(WhatsAppConversation.phone_number_id == phone_number_id,
                                WhatsAppConversation.wa_id == wa_id).first())
        if conversation is None:
            conversation = WhatsAppConversation(
                phone_number_id=phone_number_id, wa_id=wa_id, status="OPEN", unread_count=0)
            self.db.add(conversation)
            self.db.flush()

        record = WhatsAppMessage(
            conversation_id=conversation.id,
            direction="OUTBOUND",
            from_number=display_number,
            to_number=wa_id,
            phone_number_id=phone_number_id,
            message_type=message_type,
            body=body,
            status="ACCEPTED",
            patient_id=conversation.patient_id,
            sent_by_user_id=sender_user_id,
            raw_json=payload,
        )
        self.db.add(record)

        client = WhatsAppCloudClient(access_token, phone_number_id)
        try:
            response = client.send(payload)
            wamid = None
            msgs = response.get("messages") if isinstance(response, dict) else None
            if msgs:
                wamid = msgs[0].get("id")
            record.wa_message_id = wamid
            record.status = "SENT"
            record.status_updated_at = datetime.now(timezone.utc)
        except httpx.HTTPStatusError as exc:
            record.status = "FAILED"
            detail = _extract_error_detail(exc)
            record.error_title = detail
            logger.warning("WhatsApp send failed: %s", detail)
        except Exception as exc:
            record.status = "FAILED"
            record.error_title = str(exc)
            logger.exception("WhatsApp send error")

        now = datetime.now(timezone.utc)
        conversation.last_message_at = now
        conversation.last_outbound_at = now
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(record)
        return record


def _extract_error_detail(exc: "httpx.HTTPStatusError") -> str:
    try:
        data = exc.response.json()
        err = data.get("error") or {}
        return err.get("message") or json.dumps(data)[:400]
    except Exception:
        return f"HTTP {exc.response.status_code}"
