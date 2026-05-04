# utils/sms_util.py
from __future__ import annotations

"""
SMS and WhatsApp messaging utilities for Carepoint HMS.

Purpose
-------
This module centralizes outbound SMS and WhatsApp messaging using Twilio.

Main features
-------------
- send plain SMS messages
- send WhatsApp messages
- normalize recipient numbers
- support optional messaging service SID or direct sender number
- send OTP messages
- render simple message templates
- return structured result payloads for service/repository use

Expected settings
-----------------
This module expects settings such as:

- SMS_ENABLED
- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_SMS_FROM
- TWILIO_MESSAGING_SERVICE_SID
- TWILIO_WHATSAPP_FROM
- TWILIO_WHATSAPP_MESSAGING_SERVICE_SID
- TWILIO_STATUS_CALLBACK_URL
"""

import logging
from typing import Any, Optional

from twilio.base.exceptions import TwilioException
from twilio.rest import Client

try:
    from app.core.config import settings
except Exception:  # pragma: no cover
    settings = None


logger = logging.getLogger(__name__)


# Per-process latch that lets us log "SMS not configured" exactly once
# and then stay quiet — same pattern as :mod:`app.utils.email_utils`.
_SMS_UNCONFIGURED_WARNED: bool = False


def _sms_provider_configured() -> bool:
    """Return True if Twilio SMS configuration is present."""
    return bool(settings is not None and getattr(settings, "sms_configured", False))


def _require_sms_config() -> None:
    """
    Ensure SMS configuration is available before sending.

    Raises ``RuntimeError`` with the original "SMS configuration is
    incomplete." text preserved for back-compat, but the warning itself
    is emitted at WARNING level **once per process** and at DEBUG level
    on subsequent calls.
    """
    global _SMS_UNCONFIGURED_WARNED
    if _sms_provider_configured():
        return

    if not _SMS_UNCONFIGURED_WARNED:
        logger.warning(
            "SMS delivery skipped — Twilio is not configured. "
            "Set SMS_ENABLED + TWILIO_* settings to enable outgoing SMS."
        )
        _SMS_UNCONFIGURED_WARNED = True
    else:
        logger.debug("SMS delivery skipped — Twilio is not configured.")
    raise RuntimeError("SMS configuration is incomplete.")


def _get_twilio_client() -> Client:
    """
    Create and return a Twilio API client.
    """
    _require_sms_config()
    return Client(
        settings.twilio_account_sid_value,
        settings.twilio_auth_token_value,
    )


def normalize_phone_number(phone_number: str) -> str:
    """
    Normalize a phone number into a Twilio-friendly format.

    Rules
    -----
    - Removes spaces
    - Preserves leading '+'
    - Rejects empty input

    Note
    ----
    This function does not fully validate regional numbering plans. It keeps
    the logic lightweight and generic for application use.

    Args:
        phone_number: Raw phone number.

    Returns:
        str: Normalized phone number.

    Raises:
        ValueError: If the phone number is empty.
    """
    if not phone_number or not phone_number.strip():
        raise ValueError("Phone number is required.")

    normalized = phone_number.strip().replace(" ", "")
    return normalized


def format_sms_recipient(phone_number: str) -> str:
    """
    Format a phone number for SMS delivery.

    Args:
        phone_number: Raw recipient phone number.

    Returns:
        str: Normalized phone number.
    """
    return normalize_phone_number(phone_number)


def format_whatsapp_recipient(phone_number: str) -> str:
    """
    Format a phone number for WhatsApp delivery.

    Args:
        phone_number: Raw recipient phone number.

    Returns:
        str: WhatsApp-formatted recipient, e.g. 'whatsapp:+234...'
    """
    normalized = normalize_phone_number(phone_number)
    return normalized if normalized.startswith("whatsapp:") else f"whatsapp:{normalized}"


def render_message_template(template: str, context: Optional[dict[str, Any]] = None) -> str:
    """
    Render a simple message template using Python string formatting.

    Example:
        template = "Hello {name}, your OTP is {otp}"
        context = {"name": "Nelson", "otp": "123456"}

    Args:
        template: Message template.
        context: Placeholder values.

    Returns:
        str: Rendered message text.
    """
    context = context or {}
    return template.format(**context)


def _build_sms_payload(
    *,
    to: str,
    body: str,
    status_callback: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build a Twilio SMS payload.
    """
    payload: dict[str, Any] = {
        "to": format_sms_recipient(to),
        "body": body,
    }

    # Prefer Messaging Service SID where configured.
    if settings.TWILIO_MESSAGING_SERVICE_SID:
        payload["messaging_service_sid"] = settings.TWILIO_MESSAGING_SERVICE_SID
    else:
        payload["from_"] = settings.TWILIO_SMS_FROM

    callback_url = status_callback or getattr(settings, "TWILIO_STATUS_CALLBACK_URL", None)
    if callback_url:
        payload["status_callback"] = callback_url

    return payload


def _build_whatsapp_payload(
    *,
    to: str,
    body: str,
    status_callback: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build a Twilio WhatsApp payload.
    """
    payload: dict[str, Any] = {
        "to": format_whatsapp_recipient(to),
        "body": body,
    }

    if settings.TWILIO_WHATSAPP_MESSAGING_SERVICE_SID:
        payload["messaging_service_sid"] = settings.TWILIO_WHATSAPP_MESSAGING_SERVICE_SID
    else:
        payload["from_"] = settings.TWILIO_WHATSAPP_FROM

    callback_url = status_callback or getattr(settings, "TWILIO_STATUS_CALLBACK_URL", None)
    if callback_url:
        payload["status_callback"] = callback_url

    return payload


def send_sms(
    *,
    to: str,
    body: str,
    status_callback: Optional[str] = None,
) -> dict[str, Any]:
    """
    Send an SMS message through Twilio.

    Args:
        to: Recipient phone number.
        body: Message body.
        status_callback: Optional Twilio status callback URL.

    Returns:
        dict[str, Any]: Structured send result.
    """
    _require_sms_config()
    client = _get_twilio_client()

    try:
        payload = _build_sms_payload(
            to=to,
            body=body,
            status_callback=status_callback,
        )
        message = client.messages.create(**payload)

        return {
            "success": True,
            "channel": "sms",
            "sid": message.sid,
            "status": message.status,
            "to": message.to,
            "body": body,
            "error": None,
        }
    except TwilioException as exc:
        return {
            "success": False,
            "channel": "sms",
            "sid": None,
            "status": "failed",
            "to": format_sms_recipient(to),
            "body": body,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "success": False,
            "channel": "sms",
            "sid": None,
            "status": "failed",
            "to": format_sms_recipient(to),
            "body": body,
            "error": str(exc),
        }


def send_whatsapp_message(
    *,
    to: str,
    body: str,
    status_callback: Optional[str] = None,
) -> dict[str, Any]:
    """
    Send a WhatsApp message through Twilio.

    Args:
        to: Recipient phone number.
        body: Message body.
        status_callback: Optional Twilio status callback URL.

    Returns:
        dict[str, Any]: Structured send result.
    """
    _require_sms_config()
    client = _get_twilio_client()

    try:
        payload = _build_whatsapp_payload(
            to=to,
            body=body,
            status_callback=status_callback,
        )
        message = client.messages.create(**payload)

        return {
            "success": True,
            "channel": "whatsapp",
            "sid": message.sid,
            "status": message.status,
            "to": message.to,
            "body": body,
            "error": None,
        }
    except TwilioException as exc:
        return {
            "success": False,
            "channel": "whatsapp",
            "sid": None,
            "status": "failed",
            "to": format_whatsapp_recipient(to),
            "body": body,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "success": False,
            "channel": "whatsapp",
            "sid": None,
            "status": "failed",
            "to": format_whatsapp_recipient(to),
            "body": body,
            "error": str(exc),
        }


def send_templated_sms(
    *,
    to: str,
    template: str,
    context: Optional[dict[str, Any]] = None,
    status_callback: Optional[str] = None,
) -> dict[str, Any]:
    """
    Render and send a templated SMS.
    """
    body = render_message_template(template, context)
    return send_sms(
        to=to,
        body=body,
        status_callback=status_callback,
    )


def send_templated_whatsapp(
    *,
    to: str,
    template: str,
    context: Optional[dict[str, Any]] = None,
    status_callback: Optional[str] = None,
) -> dict[str, Any]:
    """
    Render and send a templated WhatsApp message.
    """
    body = render_message_template(template, context)
    return send_whatsapp_message(
        to=to,
        body=body,
        status_callback=status_callback,
    )


def send_otp_sms(
    *,
    to: str,
    otp_code: str,
    app_name: Optional[str] = None,
    expiry_minutes: Optional[int] = None,
    status_callback: Optional[str] = None,
) -> dict[str, Any]:
    """
    Send an OTP by SMS.

    Args:
        to: Recipient phone number.
        otp_code: OTP code.
        app_name: Optional application name.
        expiry_minutes: Optional OTP validity period.
        status_callback: Optional Twilio callback URL.

    Returns:
        dict[str, Any]: Structured send result.
    """
    resolved_app_name = app_name or getattr(settings, "APP_NAME", "Carepoint HMS")
    resolved_expiry = expiry_minutes or getattr(settings, "OTP_EXPIRE_MINUTES", 10)

    body = (
        f"{resolved_app_name}: Your OTP is {otp_code}. "
        f"It expires in {resolved_expiry} minute(s). "
        f"Do not share this code."
    )

    return send_sms(
        to=to,
        body=body,
        status_callback=status_callback,
    )


def send_otp_whatsapp(
    *,
    to: str,
    otp_code: str,
    app_name: Optional[str] = None,
    expiry_minutes: Optional[int] = None,
    status_callback: Optional[str] = None,
) -> dict[str, Any]:
    """
    Send an OTP by WhatsApp.

    Args:
        to: Recipient phone number.
        otp_code: OTP code.
        app_name: Optional application name.
        expiry_minutes: Optional OTP validity period.
        status_callback: Optional Twilio callback URL.

    Returns:
        dict[str, Any]: Structured send result.
    """
    resolved_app_name = app_name or getattr(settings, "APP_NAME", "Carepoint HMS")
    resolved_expiry = expiry_minutes or getattr(settings, "OTP_EXPIRE_MINUTES", 10)

    body = (
        f"{resolved_app_name}: Your OTP is {otp_code}. "
        f"It expires in {resolved_expiry} minute(s). "
        f"Do not share this code."
    )

    return send_whatsapp_message(
        to=to,
        body=body,
        status_callback=status_callback,
    )