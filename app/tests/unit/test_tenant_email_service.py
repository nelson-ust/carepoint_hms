"""Unit tests for TenantEmailService."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.core.enums import EmailProvider
from app.core.exceptions import BadRequestError
from app.services.tenant_email_service import (
    PROVIDER_REQUIREMENTS,
    TenantEmailService,
    _CRED_FIELDS,
)


class TestProviderRequirements:
    def test_smtp_requires_host_port_from(self):
        assert set(PROVIDER_REQUIREMENTS[EmailProvider.SMTP]) >= {"smtp_host", "smtp_port", "from_email"}

    def test_sendgrid_requires_api_key(self):
        assert "api_key" in PROVIDER_REQUIREMENTS[EmailProvider.SENDGRID]

    def test_ses_requires_api_secret_and_region(self):
        reqs = set(PROVIDER_REQUIREMENTS[EmailProvider.SES])
        assert "api_secret" in reqs
        assert "api_region" in reqs


class TestCredFieldMap:
    def test_has_smtp_password(self):
        assert _CRED_FIELDS["smtp_password"] == "smtp_password_encrypted"

    def test_has_api_key(self):
        assert _CRED_FIELDS["api_key"] == "api_key_encrypted"


class TestValidation:
    def test_invalid_smtp_security_rejected(self):
        svc = TenantEmailService(MagicMock())
        with pytest.raises(BadRequestError):
            svc.create(
                display_name="X",
                from_email="x@x.com",
                smtp_security="WRONG",
            )

    def test_unknown_credential_field_rejected(self):
        svc = TenantEmailService(MagicMock())
        with pytest.raises(BadRequestError):
            svc._validate_credentials({"weird_credential": "x"})

    def test_known_credentials_accepted(self):
        svc = TenantEmailService(MagicMock())
        # Should not raise.
        svc._validate_credentials({"smtp_password": "x", "api_key": "y"})


class TestFooterAttachment:
    def test_with_footer_appends(self):
        out = TenantEmailService._with_footer("Hello", "Sig")
        assert "Hello" in out and "Sig" in out

    def test_without_footer_returns_original(self):
        assert TenantEmailService._with_footer("Hello", None) == "Hello"

    def test_without_body_returns_none(self):
        assert TenantEmailService._with_footer(None, "Sig") is None


class TestSendEmailEarlyExit:
    def test_returns_false_when_no_recipients(self):
        svc = TenantEmailService(MagicMock())
        assert svc.send_email(subject="x", recipients=[], body_text="x") is False

    def test_returns_false_when_no_active_config(self):
        svc = TenantEmailService(MagicMock())
        # get_active_config returns None
        with patch.object(svc, "get_active_config", return_value=None):
            assert (
                svc.send_email(subject="x", recipients=["x@x.com"], body_text="x")
                is False
            )
