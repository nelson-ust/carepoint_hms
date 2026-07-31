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


# =====================================================================
# Branded email layout
# =====================================================================
#
# A single, reusable HTML shell so every transactional email the platform
# sends (OTP, invoices, receipts, dunning, patient notifications) looks
# consistent and carries structured detail rather than a wall of plain text.
#
# Design constraints for maximum email-client compatibility (Gmail, Outlook,
# Apple Mail, mobile clients):
#   * table-based layout, fixed 600px content width
#   * every visual style is INLINE on the element (a small <style> block is
#     included only for dark-mode / responsive niceties; clients that strip it
#     still render correctly from the inline styles)
#   * no external CSS, no web fonts, no JavaScript
#   * a hidden preheader so the inbox preview line is meaningful

import html as _html
from typing import Sequence, Tuple

_BRAND_ACCENT = "#0d9488"       # teal-600 (matches the app's emerald/teal brand)
_BRAND_ACCENT_DARK = "#0f766e"  # teal-700
_INK = "#111827"                # gray-900
_MUTED = "#6b7280"              # gray-500
_LINE = "#e5e7eb"               # gray-200
_CANVAS = "#f3f4f6"             # gray-100
_SOFT = "#f0fdfa"               # teal-50


def _brand_name() -> str:
    return str(getattr(settings, "APP_NAME", None) or "CarePoint HMS")


def _esc(value: Any) -> str:
    """HTML-escape a value for safe interpolation into the template."""
    if value is None:
        return ""
    return _html.escape(str(value))


def render_branded_email(
    *,
    title: str,
    intro: Optional[str] = None,
    body_paragraphs: Optional[Sequence[str]] = None,
    details: Optional[Sequence[Tuple[str, Any]]] = None,
    details_heading: Optional[str] = None,
    highlight_label: Optional[str] = None,
    highlight_value: Optional[str] = None,
    highlight_caption: Optional[str] = None,
    cta_label: Optional[str] = None,
    cta_url: Optional[str] = None,
    footer_note: Optional[str] = None,
    preheader: Optional[str] = None,
    brand_name: Optional[str] = None,
    accent: str = _BRAND_ACCENT,
) -> str:
    """
    Compose a polished, email-client-safe HTML email.

    Args:
        title: Bold headline shown at the top of the card.
        intro: Optional lead sentence under the title.
        body_paragraphs: Optional list of paragraphs (each escaped & wrapped).
        details: Optional list of ``(label, value)`` rows rendered as a
            two-column "receipt" style table — the structured detail.
        details_heading: Optional small heading above the details table.
        highlight_label/value/caption: Optional callout box (e.g. an OTP code,
            an amount due, or a status) drawn in the brand colour.
        cta_label/cta_url: Optional call-to-action button.
        footer_note: Optional small print above the standard footer.
        preheader: Inbox preview text (hidden in the body).
        brand_name: Overrides the header brand (defaults to APP_NAME).
        accent: Brand accent colour.

    Returns:
        A complete HTML document string.
    """
    brand = _esc(brand_name or _brand_name())
    year_hint = ""  # date helpers are avoided here; the footer stays evergreen

    # --- Preheader (hidden preview text) ---
    pre = _esc(preheader or intro or title)
    preheader_html = (
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;'
        f'color:transparent;height:0;width:0;">{pre}</div>'
    )

    # --- Intro + body paragraphs ---
    paras: list[str] = []
    if intro:
        paras.append(intro)
    if body_paragraphs:
        paras.extend(body_paragraphs)
    paragraphs_html = "".join(
        f'<p style="margin:0 0 16px 0;color:#374151;font-size:15px;'
        f'line-height:1.65;">{_esc(p)}</p>'
        for p in paras
    )

    # --- Highlight / callout box ---
    highlight_html = ""
    if highlight_value:
        cap = (
            f'<div style="margin-top:10px;color:{_MUTED};font-size:12px;'
            f'line-height:1.5;">{_esc(highlight_caption)}</div>'
            if highlight_caption
            else ""
        )
        lab = (
            f'<div style="text-transform:uppercase;letter-spacing:.12em;'
            f'font-size:11px;font-weight:700;color:{accent};margin-bottom:8px;">'
            f'{_esc(highlight_label)}</div>'
            if highlight_label
            else ""
        )
        highlight_html = (
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="margin:24px 0;"><tr><td style="background:{_SOFT};'
            f'border:1px solid #ccfbf1;border-radius:12px;padding:22px 24px;'
            f'text-align:center;">{lab}'
            f'<div style="font-size:26px;font-weight:800;color:{_BRAND_ACCENT_DARK};'
            f'letter-spacing:.02em;font-family:Menlo,Consolas,\'Courier New\',monospace;">'
            f'{_esc(highlight_value)}</div>{cap}</td></tr></table>'
        )

    # --- Details table ---
    details_html = ""
    if details:
        rows = []
        for label, value in details:
            rows.append(
                f'<tr>'
                f'<td style="padding:10px 0;border-bottom:1px solid {_LINE};'
                f'color:{_MUTED};font-size:13px;vertical-align:top;width:42%;">'
                f'{_esc(label)}</td>'
                f'<td style="padding:10px 0;border-bottom:1px solid {_LINE};'
                f'color:{_INK};font-size:14px;font-weight:600;text-align:right;'
                f'vertical-align:top;">{_esc(value)}</td>'
                f'</tr>'
            )
        heading = (
            f'<div style="text-transform:uppercase;letter-spacing:.1em;'
            f'font-size:11px;font-weight:700;color:{_MUTED};margin:0 0 6px 0;">'
            f'{_esc(details_heading)}</div>'
            if details_heading
            else ""
        )
        details_html = (
            f'{heading}'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="margin:8px 0 24px 0;border-collapse:collapse;">'
            f'{"".join(rows)}</table>'
        )

    # --- CTA button ---
    cta_html = ""
    if cta_label and cta_url:
        cta_html = (
            f'<table role="presentation" cellpadding="0" cellspacing="0" '
            f'style="margin:8px 0 24px 0;"><tr><td style="border-radius:10px;'
            f'background:{accent};"><a href="{_esc(cta_url)}" target="_blank" '
            f'style="display:inline-block;padding:13px 28px;color:#ffffff;'
            f'font-size:14px;font-weight:700;text-decoration:none;border-radius:10px;">'
            f'{_esc(cta_label)}</a></td></tr></table>'
        )

    footer_note_html = (
        f'<p style="margin:0 0 12px 0;color:{_MUTED};font-size:13px;'
        f'line-height:1.6;">{_esc(footer_note)}</p>'
        if footer_note
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>{_esc(title)}</title>
<style>
  @media (max-width:620px) {{
    .cp-card {{ padding:28px 22px !important; }}
    .cp-wrap {{ padding:16px !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;background:{_CANVAS};">
{preheader_html}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_CANVAS};">
<tr><td align="center" class="cp-wrap" style="padding:32px 16px;">
  <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:100%;">
    <!-- Header -->
    <tr><td style="padding:4px 8px 20px 8px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
        <td style="vertical-align:middle;">
          <span style="display:inline-block;width:34px;height:34px;border-radius:9px;
            background:{accent};color:#ffffff;font-weight:800;font-size:16px;
            line-height:34px;text-align:center;vertical-align:middle;">C</span>
          <span style="margin-left:10px;font-size:17px;font-weight:800;color:{_INK};
            letter-spacing:-.01em;vertical-align:middle;">{brand}</span>
        </td>
        <td style="text-align:right;color:{_MUTED};font-size:12px;vertical-align:middle;">
          Hospital Management System
        </td>
      </tr></table>
    </td></tr>
    <!-- Card -->
    <tr><td class="cp-card" style="background:#ffffff;border:1px solid {_LINE};
      border-radius:16px;padding:40px 40px;">
      <h1 style="margin:0 0 16px 0;color:{_INK};font-size:22px;font-weight:800;
        line-height:1.3;">{_esc(title)}</h1>
      {paragraphs_html}
      {highlight_html}
      {details_html}
      {cta_html}
      {footer_note_html}
    </td></tr>
    <!-- Footer -->
    <tr><td style="padding:24px 12px;text-align:center;color:{_MUTED};font-size:12px;
      line-height:1.6;">
      This is an automated message from {brand}.{year_hint}<br>
      Please do not reply directly to this email.
    </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>"""


def render_branded_email_text(
    *,
    title: str,
    intro: Optional[str] = None,
    body_paragraphs: Optional[Sequence[str]] = None,
    details: Optional[Sequence[Tuple[str, Any]]] = None,
    highlight_label: Optional[str] = None,
    highlight_value: Optional[str] = None,
    highlight_caption: Optional[str] = None,
    cta_label: Optional[str] = None,
    cta_url: Optional[str] = None,
    footer_note: Optional[str] = None,
    brand_name: Optional[str] = None,
    **_ignored: Any,
) -> str:
    """Plain-text counterpart of :func:`render_branded_email` (fallback body)."""
    brand = brand_name or _brand_name()
    lines: list[str] = [brand, "=" * len(brand), "", title, ""]
    if intro:
        lines += [intro, ""]
    for p in body_paragraphs or []:
        lines += [p, ""]
    if highlight_value:
        if highlight_label:
            lines.append(f"{highlight_label}: {highlight_value}")
        else:
            lines.append(str(highlight_value))
        if highlight_caption:
            lines.append(highlight_caption)
        lines.append("")
    if details:
        width = max((len(str(l)) for l, _ in details), default=0)
        for label, value in details:
            lines.append(f"{str(label).ljust(width)}  {value}")
        lines.append("")
    if cta_label and cta_url:
        lines += [f"{cta_label}: {cta_url}", ""]
    if footer_note:
        lines += [footer_note, ""]
    lines.append(f"— The {brand} Team")
    return "\n".join(lines)


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

    purpose_label = purpose.lower().replace("_", " ")
    common = dict(
        title=title,
        intro=f"You requested a {purpose_label} for your {_brand_name()} account. "
        "Use the verification code below to continue.",
        highlight_label="Your verification code",
        highlight_value=code,
        highlight_caption="This code expires in 10 minutes.",
        footer_note="If you didn't request this, you can safely ignore this email — "
        "your account remains secure. Never share this code with anyone.",
        preheader=f"Your {_brand_name()} code is {code} (expires in 10 minutes).",
    )

    return send_email(
        subject=f"{_brand_name()} — {title}",
        recipients=email,
        body_text=render_branded_email_text(**common),
        body_html=render_branded_email(**common),
    )


def send_developer_verification_email(
    *,
    email: str,
    contact_name: str,
    organization_name: str,
    token: str,
    expires_hours: int = 48,
    verify_url: Optional[str] = None,
) -> dict[str, Any]:
    """
    Send the developer-account email-verification message.

    Contains the one-time verification token (and, when a frontend URL is
    configured, a one-click verification link). Best-effort: callers should
    treat a failure as non-fatal — the token is also returned by the register
    endpoint as a fallback.
    """
    brand = _brand_name()
    greeting = f"Hi {contact_name}," if contact_name else "Hello,"
    intro = (
        f"{greeting} thanks for registering "
        f"{organization_name or 'your organization'} on the {brand} Developer "
        "Platform. Confirm your email to activate your account and start "
        "creating API keys."
    )
    common: dict[str, Any] = dict(
        title="Verify your developer email",
        intro=intro,
        highlight_label="Your verification token",
        highlight_value=token,
        highlight_caption=f"This token expires in {expires_hours} hours.",
        footer_note=(
            "If you didn't create this account, you can safely ignore this "
            "email — no account is activated until it is verified."
        ),
        preheader=f"Confirm your {brand} developer account to activate API access.",
    )
    if verify_url:
        common["cta_label"] = "Verify my email"
        common["cta_url"] = verify_url
        common["body_paragraphs"] = [
            "Click the button below to verify automatically, or open the "
            "Developer Portal verification page and paste the token above."
        ]

    return send_email(
        subject=f"{brand} — Verify your developer account",
        recipients=email,
        body_text=render_branded_email_text(**common),
        body_html=render_branded_email(**common),
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
    common = dict(
        title="Reset your password",
        intro="We received a request to reset the password for your "
        f"{_brand_name()} account. Click the button below to choose a new password.",
        body_paragraphs=[
            "If the button doesn't work, copy and paste this link into your browser:",
            reset_link,
        ],
        cta_label="Reset password",
        cta_url=reset_link,
        footer_note=(
            f"This link expires in {expires_minutes} minutes. If you didn't request a "
            "password reset, you can ignore this email — your password stays unchanged."
        ),
        preheader="Reset your password — this link expires soon.",
    )

    return {
        "subject": f"{_brand_name()} — Reset your password",
        "body_text": render_branded_email_text(**common),
        "body_html": render_branded_email(**common),
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