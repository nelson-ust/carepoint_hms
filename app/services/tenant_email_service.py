"""
Per-tenant outbound-email service.

Each tenant points the platform at *their own* email infrastructure so
messages to their patients/users come from a sender they control. Six
provider flavours are supported:

* ``SMTP`` — classic host/port/TLS, dispatched via :mod:`smtplib`.
* ``SENDGRID``, ``SES``, ``MAILGUN``, ``POSTMARK``, ``RESEND`` — sent
  through the provider's HTTP API using an encrypted API key.

Public surface:

* :class:`TenantEmailService` — CRUD + test + send wrapped around
  :class:`TenantEmailConfig`.
* :func:`send_tenant_email` — module-level helper that prefers the
  active tenant configuration and falls back to the platform SMTP
  when no tenant config is set.

Credentials never travel through the database in plaintext. The service
encrypts on the way in via :func:`app.core.cryptography.encrypt_string`
and decrypts on demand only for the send adapter.
"""
from __future__ import annotations

import json
import logging
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from app.core.cryptography import decrypt_string, encrypt_string
from app.core.enums import EmailProvider
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import TenantEmailConfig


logger = logging.getLogger(__name__)


# Required credential fields per provider — used by ``test_config`` and
# at send time to surface misconfiguration before contacting the wire.
PROVIDER_REQUIREMENTS: dict[EmailProvider, tuple[str, ...]] = {
    EmailProvider.SMTP: ("smtp_host", "smtp_port", "from_email"),
    EmailProvider.SENDGRID: ("api_key", "from_email"),
    EmailProvider.SES: ("api_key", "api_secret", "api_region", "from_email"),
    EmailProvider.MAILGUN: ("api_key", "api_domain", "from_email"),
    EmailProvider.POSTMARK: ("api_key", "from_email"),
    EmailProvider.RESEND: ("api_key", "from_email"),
}


_CRED_FIELDS = {
    "smtp_password": "smtp_password_encrypted",
    "api_key": "api_key_encrypted",
    "api_secret": "api_secret_encrypted",
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TenantEmailService:
    """
    Manage and dispatch through the active tenant email configuration.

    Operates against the **tenant** database — configurations are scoped
    to whichever tenant context the request is running in.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def list_configs(self, *, only_active: bool = False) -> list[TenantEmailConfig]:
        q = self.db.query(TenantEmailConfig).filter(
            TenantEmailConfig.is_deleted.is_(False)
        )
        if only_active:
            q = q.filter(TenantEmailConfig.is_active.is_(True))
        return q.order_by(
            TenantEmailConfig.is_default.desc(),
            TenantEmailConfig.id.asc(),
        ).all()

    def get(self, config_id: int) -> TenantEmailConfig:
        rec = (
            self.db.query(TenantEmailConfig)
            .filter(
                TenantEmailConfig.id == config_id,
                TenantEmailConfig.is_deleted.is_(False),
            )
            .first()
        )
        if rec is None:
            raise NotFoundError(message="Email configuration not found.")
        return rec

    def get_active_config(self) -> Optional[TenantEmailConfig]:
        """
        Return the configuration the dispatcher should use right now.
        Preference order: ``is_default=True`` ⇒ first active by id.
        """
        rows = (
            self.db.query(TenantEmailConfig)
            .filter(
                TenantEmailConfig.is_active.is_(True),
                TenantEmailConfig.is_deleted.is_(False),
            )
            .order_by(
                TenantEmailConfig.is_default.desc(),
                TenantEmailConfig.id.asc(),
            )
            .all()
        )
        return rows[0] if rows else None

    def get_decrypted_credentials(self, config: TenantEmailConfig) -> dict[str, str]:
        out: dict[str, str] = {}
        for plain, enc in _CRED_FIELDS.items():
            cipher = getattr(config, enc, None)
            if not cipher:
                continue
            try:
                out[plain] = decrypt_string(cipher)
            except Exception as exc:
                logger.exception(
                    "Could not decrypt %s for tenant_email_config %s: %s",
                    plain,
                    config.id,
                    exc,
                )
        return out

    # ------------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        provider: EmailProvider = EmailProvider.SMTP,
        display_name: str,
        description: Optional[str] = None,
        from_email: str,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        footer_text: Optional[str] = None,
        footer_html: Optional[str] = None,
        is_active: bool = True,
        is_default: bool = True,
        sandbox_mode: bool = False,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_security: str = "TLS",
        smtp_username: Optional[str] = None,
        api_base_url: Optional[str] = None,
        api_region: Optional[str] = None,
        api_domain: Optional[str] = None,
        credentials: Optional[dict[str, str]] = None,
    ) -> TenantEmailConfig:
        self._validate_credentials(credentials)
        if smtp_security.upper() not in {"NONE", "TLS", "SSL"}:
            raise BadRequestError(message="smtp_security must be one of NONE, TLS, SSL.")

        rec = TenantEmailConfig(
            provider=provider,
            display_name=display_name.strip(),
            description=description,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_security=smtp_security.upper(),
            smtp_username=smtp_username,
            api_base_url=api_base_url,
            api_region=api_region,
            api_domain=api_domain,
            from_email=from_email.strip(),
            from_name=from_name,
            reply_to=reply_to,
            footer_text=footer_text,
            footer_html=footer_html,
            is_active=is_active,
            is_default=is_default,
            sandbox_mode=sandbox_mode,
        )
        self._apply_credentials(rec, credentials)

        self.db.add(rec)
        self.db.flush()

        if rec.is_default:
            self._enforce_single_default(rec)

        self.db.commit()
        self.db.refresh(rec)
        return rec

    def update(
        self,
        config_id: int,
        *,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        provider: Optional[EmailProvider] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        footer_text: Optional[str] = None,
        footer_html: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_default: Optional[bool] = None,
        sandbox_mode: Optional[bool] = None,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_security: Optional[str] = None,
        smtp_username: Optional[str] = None,
        api_base_url: Optional[str] = None,
        api_region: Optional[str] = None,
        api_domain: Optional[str] = None,
        credentials: Optional[dict[str, str]] = None,
    ) -> TenantEmailConfig:
        rec = self.get(config_id)
        self._validate_credentials(credentials)
        if smtp_security is not None and smtp_security.upper() not in {"NONE", "TLS", "SSL"}:
            raise BadRequestError(message="smtp_security must be one of NONE, TLS, SSL.")

        for field, value in (
            ("display_name", display_name.strip() if display_name is not None else None),
            ("description", description),
            ("provider", provider),
            ("from_email", from_email.strip() if from_email else None),
            ("from_name", from_name),
            ("reply_to", reply_to),
            ("footer_text", footer_text),
            ("footer_html", footer_html),
            ("is_active", is_active),
            ("sandbox_mode", sandbox_mode),
            ("smtp_host", smtp_host),
            ("smtp_port", smtp_port),
            ("smtp_security", smtp_security.upper() if smtp_security else None),
            ("smtp_username", smtp_username),
            ("api_base_url", api_base_url),
            ("api_region", api_region),
            ("api_domain", api_domain),
        ):
            if value is not None:
                setattr(rec, field, value)

        if credentials:
            self._apply_credentials(rec, credentials)

        if is_default is True:
            rec.is_default = True
            self._enforce_single_default(rec)
        elif is_default is False:
            rec.is_default = False

        self.db.commit()
        self.db.refresh(rec)
        return rec

    def delete(self, config_id: int) -> None:
        rec = self.get(config_id)
        rec.soft_delete()
        rec.is_active = False
        self.db.commit()

    # ------------------------------------------------------------------
    # TEST
    # ------------------------------------------------------------------

    def test_config(self, config_id: int) -> dict[str, Any]:
        """
        Lightweight check: required fields present + credentials decryptable.
        For SMTP we additionally attempt a connection (no message sent).
        """
        rec = self.get(config_id)
        creds = self.get_decrypted_credentials(rec)

        required = PROVIDER_REQUIREMENTS.get(rec.provider, ())
        missing = []
        for field in required:
            if field in creds and creds[field]:
                continue
            value = getattr(rec, field, None)
            if value in (None, ""):
                missing.append(field)

        rec.last_test_at = datetime.now(timezone.utc)
        if missing:
            rec.last_test_status = "FAILED"
            rec.last_test_error = f"Missing fields: {', '.join(missing)}"
            self.db.commit()
            return {"ok": False, "missing": missing}

        # SMTP-specific connectivity check.
        if rec.provider == EmailProvider.SMTP:
            try:
                self._open_smtp(rec, creds).quit()
            except Exception as exc:
                rec.last_test_status = "FAILED"
                rec.last_test_error = str(exc)[:500]
                self.db.commit()
                return {"ok": False, "error": str(exc)[:200]}

        rec.last_test_status = "OK"
        rec.last_test_error = None
        self.db.commit()
        return {"ok": True, "missing": []}

    # ------------------------------------------------------------------
    # SEND
    # ------------------------------------------------------------------

    def send_email(
        self,
        *,
        subject: str,
        recipients: Iterable[str],
        body_text: str,
        body_html: Optional[str] = None,
        cc: Optional[Iterable[str]] = None,
        bcc: Optional[Iterable[str]] = None,
        config: Optional[TenantEmailConfig] = None,
    ) -> bool:
        """
        Send through the tenant's active configuration.

        Returns ``True`` on success, ``False`` on a controlled failure
        (logged but not raised) so callers can decide whether to fall
        back to the platform SMTP.
        """
        recipients = [r.strip() for r in recipients if r and r.strip()]
        if not recipients:
            return False

        rec = config or self.get_active_config()
        if rec is None:
            return False

        creds = self.get_decrypted_credentials(rec)
        body_text_full = self._with_footer(body_text, rec.footer_text)
        body_html_full = self._with_footer(body_html, rec.footer_html) if body_html else None

        try:
            ok = self._send_with(
                rec,
                creds,
                subject=subject,
                recipients=recipients,
                cc=list(cc or []),
                bcc=list(bcc or []),
                body_text=body_text_full,
                body_html=body_html_full,
            )
        except Exception as exc:
            logger.exception("Tenant email send failed (config=%s): %s", rec.id, exc)
            ok = False

        if ok:
            rec.last_used_at = datetime.now(timezone.utc)
            rec.sent_count = (rec.sent_count or 0) + 1
            self.db.commit()
        return ok

    # ------------------------------------------------------------------
    # Provider adapters
    # ------------------------------------------------------------------

    def _send_with(
        self,
        rec: TenantEmailConfig,
        creds: dict[str, str],
        *,
        subject: str,
        recipients: list[str],
        cc: list[str],
        bcc: list[str],
        body_text: str,
        body_html: Optional[str],
    ) -> bool:
        if rec.sandbox_mode:
            logger.info(
                "Tenant email sandbox: would send subject=%r to=%s via=%s",
                subject, recipients, rec.provider,
            )
            return True

        if rec.provider == EmailProvider.SMTP:
            return self._send_via_smtp(
                rec, creds, subject=subject, recipients=recipients,
                cc=cc, bcc=bcc, body_text=body_text, body_html=body_html,
            )
        if rec.provider == EmailProvider.SENDGRID:
            return self._send_via_sendgrid(
                rec, creds, subject=subject, recipients=recipients,
                cc=cc, bcc=bcc, body_text=body_text, body_html=body_html,
            )
        if rec.provider == EmailProvider.MAILGUN:
            return self._send_via_mailgun(
                rec, creds, subject=subject, recipients=recipients,
                cc=cc, bcc=bcc, body_text=body_text, body_html=body_html,
            )
        if rec.provider == EmailProvider.POSTMARK:
            return self._send_via_postmark(
                rec, creds, subject=subject, recipients=recipients,
                cc=cc, bcc=bcc, body_text=body_text, body_html=body_html,
            )
        if rec.provider == EmailProvider.RESEND:
            return self._send_via_resend(
                rec, creds, subject=subject, recipients=recipients,
                cc=cc, bcc=bcc, body_text=body_text, body_html=body_html,
            )
        if rec.provider == EmailProvider.SES:
            return self._send_via_ses(
                rec, creds, subject=subject, recipients=recipients,
                cc=cc, bcc=bcc, body_text=body_text, body_html=body_html,
            )
        logger.warning("Unsupported tenant email provider: %s", rec.provider)
        return False

    def _open_smtp(self, rec: TenantEmailConfig, creds: dict[str, str]) -> smtplib.SMTP:
        if not rec.smtp_host or not rec.smtp_port:
            raise BadRequestError(message="SMTP host/port are required.")
        timeout = 30
        if (rec.smtp_security or "TLS").upper() == "SSL":
            ctx = ssl.create_default_context()
            smtp = smtplib.SMTP_SSL(rec.smtp_host, int(rec.smtp_port), timeout=timeout, context=ctx)
        else:
            smtp = smtplib.SMTP(rec.smtp_host, int(rec.smtp_port), timeout=timeout)
            if (rec.smtp_security or "TLS").upper() == "TLS":
                smtp.starttls(context=ssl.create_default_context())
        if rec.smtp_username:
            password = creds.get("smtp_password") or ""
            smtp.login(rec.smtp_username, password)
        return smtp

    def _send_via_smtp(
        self,
        rec: TenantEmailConfig,
        creds: dict[str, str],
        *,
        subject: str,
        recipients: list[str],
        cc: list[str],
        bcc: list[str],
        body_text: str,
        body_html: Optional[str],
    ) -> bool:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr((rec.from_name or "", rec.from_email))
        msg["To"] = ", ".join(recipients)
        if cc:
            msg["Cc"] = ", ".join(cc)
        if rec.reply_to:
            msg["Reply-To"] = rec.reply_to

        msg.set_content(body_text)
        if body_html:
            msg.add_alternative(body_html, subtype="html")

        all_dests = list(recipients) + list(cc) + list(bcc)
        smtp = self._open_smtp(rec, creds)
        try:
            smtp.send_message(msg, to_addrs=all_dests)
        finally:
            try:
                smtp.quit()
            except Exception:
                pass
        return True

    # ------------------------------------------------------------------
    # API providers (lazy httpx import so the project still imports
    # cleanly when httpx isn't installed in a minimal environment).
    # ------------------------------------------------------------------

    def _httpx(self):
        try:
            import httpx  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise BadRequestError(
                message="httpx is required for API-based email providers.",
                detail={"error": str(exc)},
            )
        return httpx

    def _send_via_sendgrid(self, rec, creds, *, subject, recipients, cc, bcc, body_text, body_html) -> bool:
        api_key = creds.get("api_key")
        if not api_key:
            raise BadRequestError(message="SendGrid api_key is missing.")

        personalization = {"to": [{"email": r} for r in recipients]}
        if cc:
            personalization["cc"] = [{"email": r} for r in cc]
        if bcc:
            personalization["bcc"] = [{"email": r} for r in bcc]

        content = [{"type": "text/plain", "value": body_text}]
        if body_html:
            content.append({"type": "text/html", "value": body_html})

        payload = {
            "personalizations": [personalization],
            "from": {"email": rec.from_email, "name": rec.from_name or ""},
            "subject": subject,
            "content": content,
        }
        if rec.reply_to:
            payload["reply_to"] = {"email": rec.reply_to}

        httpx = self._httpx()
        url = (rec.api_base_url or "https://api.sendgrid.com").rstrip("/") + "/v3/mail/send"
        with httpx.Client(timeout=30) as client:
            r = client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                content=json.dumps(payload),
            )
        return r.status_code // 100 == 2

    def _send_via_mailgun(self, rec, creds, *, subject, recipients, cc, bcc, body_text, body_html) -> bool:
        api_key = creds.get("api_key")
        if not api_key or not rec.api_domain:
            raise BadRequestError(message="Mailgun api_key + api_domain are required.")
        httpx = self._httpx()
        base = (rec.api_base_url or "https://api.mailgun.net").rstrip("/")
        url = f"{base}/v3/{rec.api_domain}/messages"
        data = [
            ("from", formataddr((rec.from_name or "", rec.from_email))),
            ("subject", subject),
            ("text", body_text),
        ]
        for r in recipients:
            data.append(("to", r))
        for r in cc:
            data.append(("cc", r))
        for r in bcc:
            data.append(("bcc", r))
        if rec.reply_to:
            data.append(("h:Reply-To", rec.reply_to))
        if body_html:
            data.append(("html", body_html))
        with httpx.Client(timeout=30) as client:
            r = client.post(url, auth=("api", api_key), data=data)
        return r.status_code // 100 == 2

    def _send_via_postmark(self, rec, creds, *, subject, recipients, cc, bcc, body_text, body_html) -> bool:
        api_key = creds.get("api_key")
        if not api_key:
            raise BadRequestError(message="Postmark api_key is missing.")
        httpx = self._httpx()
        url = (rec.api_base_url or "https://api.postmarkapp.com").rstrip("/") + "/email"
        payload = {
            "From": formataddr((rec.from_name or "", rec.from_email)),
            "To": ", ".join(recipients),
            "Subject": subject,
            "TextBody": body_text,
        }
        if cc:
            payload["Cc"] = ", ".join(cc)
        if bcc:
            payload["Bcc"] = ", ".join(bcc)
        if rec.reply_to:
            payload["ReplyTo"] = rec.reply_to
        if body_html:
            payload["HtmlBody"] = body_html
        with httpx.Client(timeout=30) as client:
            r = client.post(
                url,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Postmark-Server-Token": api_key,
                },
                content=json.dumps(payload),
            )
        return r.status_code // 100 == 2

    def _send_via_resend(self, rec, creds, *, subject, recipients, cc, bcc, body_text, body_html) -> bool:
        api_key = creds.get("api_key")
        if not api_key:
            raise BadRequestError(message="Resend api_key is missing.")
        httpx = self._httpx()
        url = (rec.api_base_url or "https://api.resend.com").rstrip("/") + "/emails"
        payload = {
            "from": formataddr((rec.from_name or "", rec.from_email)),
            "to": list(recipients),
            "subject": subject,
            "text": body_text,
        }
        if cc:
            payload["cc"] = list(cc)
        if bcc:
            payload["bcc"] = list(bcc)
        if rec.reply_to:
            payload["reply_to"] = rec.reply_to
        if body_html:
            payload["html"] = body_html
        with httpx.Client(timeout=30) as client:
            r = client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                content=json.dumps(payload),
            )
        return r.status_code // 100 == 2

    def _send_via_ses(self, rec, creds, *, subject, recipients, cc, bcc, body_text, body_html) -> bool:
        try:
            import boto3  # type: ignore
        except Exception as exc:
            raise BadRequestError(
                message="boto3 is required for SES email delivery.",
                detail={"error": str(exc)},
            )
        api_key = creds.get("api_key")
        api_secret = creds.get("api_secret")
        region = rec.api_region or "us-east-1"
        if not api_key or not api_secret:
            raise BadRequestError(message="SES api_key + api_secret are required.")

        client = boto3.client(
            "ses",
            aws_access_key_id=api_key,
            aws_secret_access_key=api_secret,
            region_name=region,
        )
        body = {"Text": {"Data": body_text}}
        if body_html:
            body["Html"] = {"Data": body_html}
        client.send_email(
            Source=formataddr((rec.from_name or "", rec.from_email)),
            Destination={"ToAddresses": list(recipients), "CcAddresses": list(cc), "BccAddresses": list(bcc)},
            Message={"Subject": {"Data": subject}, "Body": body},
            ReplyToAddresses=[rec.reply_to] if rec.reply_to else [],
        )
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_credentials(self, credentials: Optional[dict[str, str]]) -> None:
        if not credentials:
            return
        unknown = sorted(set(credentials.keys()) - _CRED_FIELDS.keys())
        if unknown:
            raise BadRequestError(
                message=f"Unsupported credential field(s): {unknown}",
                detail={"allowed": sorted(_CRED_FIELDS.keys())},
            )

    def _apply_credentials(
        self,
        rec: TenantEmailConfig,
        credentials: Optional[dict[str, str]],
    ) -> None:
        if not credentials:
            return
        for plain, encrypted_attr in _CRED_FIELDS.items():
            if plain not in credentials:
                continue
            value = credentials[plain]
            if value in (None, ""):
                setattr(rec, encrypted_attr, None)
            else:
                setattr(rec, encrypted_attr, encrypt_string(str(value)))

    def _enforce_single_default(self, default_rec: TenantEmailConfig) -> None:
        (
            self.db.query(TenantEmailConfig)
            .filter(
                TenantEmailConfig.id != default_rec.id,
                TenantEmailConfig.is_deleted.is_(False),
            )
            .update({TenantEmailConfig.is_default: False})
        )

    @staticmethod
    def _with_footer(body: Optional[str], footer: Optional[str]) -> Optional[str]:
        if not body:
            return body
        if not footer:
            return body
        return f"{body}\n\n{footer}"


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------


def send_tenant_email(
    db: Optional[Session],
    *,
    subject: str,
    recipients: Iterable[str],
    body_text: str,
    body_html: Optional[str] = None,
    cc: Optional[Iterable[str]] = None,
    bcc: Optional[Iterable[str]] = None,
    fall_back_to_platform: bool = True,
) -> bool:
    """
    Best-effort email dispatch that prefers the tenant configuration.

    ``db`` should be a tenant-scoped :class:`Session`. When it is None
    (for example, when called from a SaaS-level path that has no tenant
    DB), the function falls straight through to the platform SMTP.
    """
    recipients_list = [r.strip() for r in recipients if r and r.strip()]
    if not recipients_list:
        return False

    # 1. Try tenant configuration when we have a tenant DB session.
    if db is not None:
        try:
            svc = TenantEmailService(db)
            ok = svc.send_email(
                subject=subject,
                recipients=recipients_list,
                body_text=body_text,
                body_html=body_html,
                cc=list(cc or []),
                bcc=list(bcc or []),
            )
            if ok:
                return True
        except Exception as exc:
            logger.warning(
                "Tenant email dispatch failed; falling back to platform: %s", exc
            )

    if not fall_back_to_platform:
        return False

    # 2. Fall back to the platform-wide send_email helper.
    try:
        from app.utils.email_utils import send_email  # type: ignore
    except Exception:
        logger.warning("Platform send_email helper unavailable.")
        return False

    try:
        send_email(subject=subject, recipients=recipients_list, body_text=body_text)
        return True
    except Exception as exc:
        logger.warning("Platform send_email failed: %s", exc)
        return False
