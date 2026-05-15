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


def send_otp_email(email: str, code: str, purpose: str) -> dict[str, Any]:
    """
    Send a styled OTP email for authentication / password reset.
    """
    title = "Verification Code"
    if "PASSWORD_RESET" in purpose.upper():
        title = "Reset Your Password"
    elif "LOGIN" in purpose.upper():
        title = "Two-Factor Authentication"

    context = {
        "title": title,
        "purpose": purpose.lower().replace("_", " "),
        "otp": code
    }

    text_template = (
        "Carepoint HMS\n\n"
        "{title}\n"
        "Hello,\n\n"
        "Your verification code for {purpose} is: {otp}\n\n"
        "This code will expire in 10 minutes. If you did not request this, please ignore this email.\n"
    )

    html_template = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: #f9fafb;
            margin: 0;
            padding: 40px;
            -webkit-font-smoothing: antialiased;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 16px;
            padding: 48px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
        .header {
            text-align: center;
            margin-bottom: 32px;
        }
        .logo {
            font-weight: 800;
            font-size: 24px;
            color: #0d9488;
            letter-spacing: -0.025em;
        }
        h1 {
            color: #111827;
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 16px;
            text-align: center;
        }
        p {
            color: #4b5563;
            font-size: 16px;
            line-height: 1.6;
            margin-bottom: 24px;
        }
        .otp-container {
            background-color: #f0fdfa;
            border: 1px solid #ccfbf1;
            border-radius: 12px;
            padding: 24px;
            text-align: center;
            margin: 32px 0;
        }
        .otp-code {
            font-family: 'Courier New', monospace;
            font-size: 36px;
            font-weight: 800;
            color: #0f766e;
            letter-spacing: 0.25em;
        }
        .footer {
            text-align: center;
            margin-top: 48px;
            color: #9ca3af;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="logo">CAREPOINT</span>
        </div>
        <h1>{title}</h1>
        <p>Hello,</p>
        <p>You requested a <strong>{purpose}</strong> for your Carepoint HMS account. Use the verification code below to complete the process:</p>
        
        <div class="otp-container">
            <div class="otp-code">{otp}</div>
        </div>
        
        <p>This code will expire in 10 minutes. If you did not request this, please ignore this email or contact support if you have concerns.</p>
        
        <div class="footer">
            &copy; 2026 Carepoint HMS. All rights reserved.<br>
            Carepoint Hospital Management System
        </div>
    </div>
</body>
</html>
    """

    return send_templated_email(
        subject=f"Carepoint HMS - {title}",
        recipients=email,
        text_template=text_template,
        html_template=html_template,
        context=context
    )


def build_password_reset_email_content(
    reset_link: str,
    expires_minutes: int = 30,
) -> dict[str, str]:
    """
    Render the password reset email (subject, plain text, and HTML) without
    sending it.

    This lets callers dispatch the same styled message through any transport
    — the tenant's own email configuration or the platform SMTP — instead of
    being locked into one sender.

    Returns:
        dict[str, str]: ``{"subject", "body_text", "body_html"}``.
    """
    context = {
        "reset_link": reset_link,
        "expires_minutes": str(expires_minutes),
    }

    text_template = (
        "Carepoint HMS\n\n"
        "Reset Your Password\n"
        "Hello,\n\n"
        "We received a request to reset the password for your Carepoint HMS account.\n"
        "Use the link below to choose a new password:\n\n"
        "{reset_link}\n\n"
        "This link will expire in {expires_minutes} minutes. "
        "If you did not request a password reset, please ignore this email — "
        "your password will remain unchanged.\n"
    )

    html_template = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: #f9fafb;
            margin: 0;
            padding: 40px;
            -webkit-font-smoothing: antialiased;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 16px;
            padding: 48px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
        .header {
            text-align: center;
            margin-bottom: 32px;
        }
        .logo {
            font-weight: 800;
            font-size: 24px;
            color: #0d9488;
            letter-spacing: -0.025em;
        }
        h1 {
            color: #111827;
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 16px;
            text-align: center;
        }
        p {
            color: #4b5563;
            font-size: 16px;
            line-height: 1.6;
            margin-bottom: 24px;
        }
        .button-container {
            text-align: center;
            margin: 32px 0;
        }
        .reset-button {
            display: inline-block;
            background-color: #0d9488;
            color: #ffffff !important;
            font-size: 16px;
            font-weight: 700;
            text-decoration: none;
            padding: 14px 32px;
            border-radius: 12px;
        }
        .link-fallback {
            font-size: 13px;
            color: #6b7280;
            word-break: break-all;
        }
        .footer {
            text-align: center;
            margin-top: 48px;
            color: #9ca3af;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="logo">CAREPOINT</span>
        </div>
        <h1>Reset Your Password</h1>
        <p>Hello,</p>
        <p>We received a request to reset the password for your Carepoint HMS account. Click the button below to choose a new password:</p>

        <div class="button-container">
            <a href="{reset_link}" class="reset-button">Reset Password</a>
        </div>

        <p class="link-fallback">If the button does not work, copy and paste this link into your browser:<br>{reset_link}</p>

        <p>This link will expire in {expires_minutes} minutes. If you did not request a password reset, please ignore this email — your password will remain unchanged.</p>

        <div class="footer">
            &copy; 2026 Carepoint HMS. All rights reserved.<br>
            Carepoint Hospital Management System
        </div>
    </div>
</body>
</html>
    """

    return {
        "subject": "Carepoint HMS - Reset Your Password",
        "body_text": render_email_template(text_template, context),
        "body_html": render_email_template(html_template, context),
    }


def send_password_reset_email(
    email: str,
    reset_link: str,
    expires_minutes: int = 30,
) -> dict[str, Any]:
    """
    Send a styled password reset email containing a tokenized reset link via
    the platform SMTP transport.

    Args:
        email: Recipient email address.
        reset_link: Fully built frontend URL carrying the reset token.
        expires_minutes: How long the reset link remains valid, in minutes.

    Returns:
        dict[str, Any]: Structured send result from `send_email`.
    """
    content = build_password_reset_email_content(reset_link, expires_minutes)
    return send_email(
        subject=content["subject"],
        recipients=email,
        body_text=content["body_text"],
        body_html=content["body_html"],
    )