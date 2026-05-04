# utils/email_utils.py
from __future__ import annotations

"""
Email utilities for Carepoint HMS.

Purpose
-------
This module centralizes email composition and delivery logic for the
application.

Features
--------
- plain text and HTML email support
- CC, BCC, and Reply-To support
- attachment support
- configurable SMTP transport using app settings
- structured return payload for easier service-layer handling
- lightweight template rendering via Python string formatting

Expected settings
-----------------
This module expects app.core.config.settings to expose:

- EMAILS_ENABLED
- SMTP_HOST
- SMTP_PORT
- SMTP_USERNAME
- SMTP_PASSWORD
- SMTP_FROM_EMAIL
- SMTP_FROM_NAME
- SMTP_USE_TLS
- SMTP_USE_SSL

Notes
-----
- This utility uses Python's standard `email.message.EmailMessage`
  and `smtplib`.
- Do not log secrets or full sensitive email bodies in production logs.
"""

import logging
import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Iterable, Optional

try:
    from app.core.config import settings
except Exception:  # pragma: no cover
    settings = None


logger = logging.getLogger(__name__)


# Single per-process latch that lets us log "email not configured" exactly
# once and then stay quiet for the rest of the run. Operators see the
# warning the first time it matters; production logs aren't drowned by
# the same message on every send.
_EMAIL_UNCONFIGURED_WARNED: bool = False


def _email_provider_configured() -> bool:
    """Return True if SMTP / from-address configuration is present."""
    return bool(settings is not None and getattr(settings, "email_configured", False))


def _require_email_config() -> None:
    """
    Ensure email settings are available before sending.

    Raises ``RuntimeError`` (with the original "Email configuration is
    incomplete." text preserved for back-compat) when SMTP isn't wired up.
    The message itself is emitted at WARNING level **once per process**
    and at DEBUG level on subsequent calls.
    """
    global _EMAIL_UNCONFIGURED_WARNED
    if _email_provider_configured():
        return

    if not _EMAIL_UNCONFIGURED_WARNED:
        logger.warning(
            "Email delivery skipped — SMTP is not configured. "
            "Set EMAILS_ENABLED + SMTP_* settings to enable outgoing email."
        )
        _EMAIL_UNCONFIGURED_WARNED = True
    else:
        logger.debug("Email delivery skipped — SMTP is not configured.")
    raise RuntimeError("Email configuration is incomplete.")


def _normalize_recipients(recipients: str | Iterable[str] | None) -> list[str]:
    """
    Normalize recipient input into a clean list of email addresses.

    Args:
        recipients: A single email string, an iterable of emails, or None.

    Returns:
        list[str]: Cleaned list of recipient emails.

    Raises:
        ValueError: If no valid recipient remains after normalization.
    """
    if recipients is None:
        return []

    if isinstance(recipients, str):
        recipients = [recipients]

    normalized = [item.strip() for item in recipients if item and item.strip()]

    return normalized


def _ensure_primary_recipient_exists(
    to_recipients: list[str],
    cc_recipients: list[str],
    bcc_recipients: list[str],
) -> None:
    """
    Ensure at least one recipient exists across To/CC/BCC.

    Raises:
        ValueError: If no recipients were supplied.
    """
    if not (to_recipients or cc_recipients or bcc_recipients):
        raise ValueError("At least one recipient is required.")


def _build_from_header() -> str:
    """
    Build the From header value.
    """
    _require_email_config()
    return f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"


def render_email_template(template: str, context: Optional[dict[str, Any]] = None) -> str:
    """
    Render a simple email template using Python string formatting.

    Example:
        template = "Hello {name}, your OTP is {otp}"
        context = {"name": "Nelson", "otp": "123456"}

    Args:
        template: Template string with named placeholders.
        context: Dictionary of replacement values.

    Returns:
        str: Rendered string.
    """
    context = context or {}
    return template.format(**context)


def add_attachments(
    message: EmailMessage,
    attachments: Optional[Iterable[str | Path]] = None,
) -> None:
    """
    Attach files to an EmailMessage.

    Args:
        message: EmailMessage object to modify.
        attachments: Iterable of file paths.

    Raises:
        FileNotFoundError: If any attachment path does not exist.
    """
    if not attachments:
        return

    for attachment in attachments:
        file_path = Path(attachment)

        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"Attachment not found: {file_path}")

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            maintype, subtype = mime_type.split("/", 1)
        else:
            # Fallback when MIME type cannot be guessed.
            maintype, subtype = "application", "octet-stream"

        with file_path.open("rb") as file_handle:
            file_data = file_handle.read()

        message.add_attachment(
            file_data,
            maintype=maintype,
            subtype=subtype,
            filename=file_path.name,
        )


def build_email_message(
    *,
    subject: str,
    recipients: str | Iterable[str],
    body_text: str,
    body_html: Optional[str] = None,
    cc: str | Iterable[str] | None = None,
    bcc: str | Iterable[str] | None = None,
    reply_to: Optional[str] = None,
    attachments: Optional[Iterable[str | Path]] = None,
) -> EmailMessage:
    """
    Build an EmailMessage instance.

    Args:
        subject: Email subject.
        recipients: Primary recipients.
        body_text: Plain text email body.
        body_html: Optional HTML body.
        cc: Optional CC recipients.
        bcc: Optional BCC recipients.
        reply_to: Optional Reply-To address.
        attachments: Optional file paths to attach.

    Returns:
        EmailMessage: Prepared email message object.
    """
    _require_email_config()

    to_recipients = _normalize_recipients(recipients)
    cc_recipients = _normalize_recipients(cc)
    bcc_recipients = _normalize_recipients(bcc)

    _ensure_primary_recipient_exists(to_recipients, cc_recipients, bcc_recipients)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _build_from_header()

    if to_recipients:
        msg["To"] = ", ".join(to_recipients)

    if cc_recipients:
        msg["Cc"] = ", ".join(cc_recipients)

    if reply_to:
        msg["Reply-To"] = reply_to.strip()

    # Plain text body is always included.
    msg.set_content(body_text)

    # Add HTML alternative when provided.
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    # Add attachments after body setup.
    add_attachments(msg, attachments)

    # BCC is not typically added as a visible header for recipients,
    # but smtplib.send_message can still deliver to them if present.
    if bcc_recipients:
        msg["Bcc"] = ", ".join(bcc_recipients)

    return msg


def _open_smtp_connection(timeout: int = 30) -> smtplib.SMTP:
    """
    Open and return an SMTP connection.

    Uses SSL directly when configured; otherwise uses plain SMTP and upgrades
    with STARTTLS when enabled.

    Args:
        timeout: SMTP socket timeout in seconds.

    Returns:
        smtplib.SMTP: Connected SMTP client object.
    """
    _require_email_config()

    if settings.SMTP_USE_SSL:
        smtp = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)
    else:
        smtp = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)
        smtp.ehlo()
        if settings.SMTP_USE_TLS:
            smtp.starttls()
            smtp.ehlo()

    # Authenticate after the connection is secured.
    smtp.login(settings.SMTP_USERNAME, settings.smtp_password_value)
    return smtp


def send_email(
    *,
    subject: str,
    recipients: str | Iterable[str],
    body_text: str,
    body_html: Optional[str] = None,
    cc: str | Iterable[str] | None = None,
    bcc: str | Iterable[str] | None = None,
    reply_to: Optional[str] = None,
    attachments: Optional[Iterable[str | Path]] = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Send an email using the configured SMTP transport.

    Args:
        subject: Email subject.
        recipients: Primary recipients.
        body_text: Plain text body.
        body_html: Optional HTML body.
        cc: Optional CC recipients.
        bcc: Optional BCC recipients.
        reply_to: Optional Reply-To header.
        attachments: Optional file attachments.
        timeout: SMTP timeout in seconds.

    Returns:
        dict[str, Any]: Structured send result.

    Example return:
        {
            "success": True,
            "message": "Email sent successfully.",
            "recipients": [...],
            "cc": [...],
            "bcc": [...],
            "subject": "Welcome"
        }
    """
    _require_email_config()

    to_recipients = _normalize_recipients(recipients)
    cc_recipients = _normalize_recipients(cc)
    bcc_recipients = _normalize_recipients(bcc)

    message = build_email_message(
        subject=subject,
        recipients=to_recipients,
        body_text=body_text,
        body_html=body_html,
        cc=cc_recipients,
        bcc=bcc_recipients,
        reply_to=reply_to,
        attachments=attachments,
    )

    all_recipients = to_recipients + cc_recipients + bcc_recipients

    try:
        with _open_smtp_connection(timeout=timeout) as smtp:
            # send_message returns a dict of refused recipients if any failed.
            send_errors = smtp.send_message(message, to_addrs=all_recipients)

        success = len(send_errors) == 0

        return {
            "success": success,
            "message": "Email sent successfully." if success else "Email partially sent.",
            "subject": subject,
            "recipients": to_recipients,
            "cc": cc_recipients,
            "bcc": bcc_recipients,
            "failed_recipients": send_errors,
        }

    except smtplib.SMTPException as exc:
        return {
            "success": False,
            "message": "Failed to send email.",
            "subject": subject,
            "recipients": to_recipients,
            "cc": cc_recipients,
            "bcc": bcc_recipients,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "success": False,
            "message": "Unexpected email error.",
            "subject": subject,
            "recipients": to_recipients,
            "cc": cc_recipients,
            "bcc": bcc_recipients,
            "error": str(exc),
        }


def send_templated_email(
    *,
    subject: str,
    recipients: str | Iterable[str],
    text_template: str,
    html_template: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
    cc: str | Iterable[str] | None = None,
    bcc: str | Iterable[str] | None = None,
    reply_to: Optional[str] = None,
    attachments: Optional[Iterable[str | Path]] = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Render and send a templated email.

    Args:
        subject: Email subject.
        recipients: Primary recipients.
        text_template: Plain text template.
        html_template: Optional HTML template.
        context: Template context dictionary.
        cc: Optional CC recipients.
        bcc: Optional BCC recipients.
        reply_to: Optional Reply-To header.
        attachments: Optional attachments.
        timeout: SMTP timeout.

    Returns:
        dict[str, Any]: Structured send result.
    """
    context = context or {}

    body_text = render_email_template(text_template, context)
    body_html = render_email_template(html_template, context) if html_template else None

    return send_email(
        subject=subject,
        recipients=recipients,
        body_text=body_text,
        body_html=body_html,
        cc=cc,
        bcc=bcc,
        reply_to=reply_to,
        attachments=attachments,
        timeout=timeout,
    )