"""Unit tests for TenantPaymentMethodService."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.core.enums import PaymentChannel, PaymentProvider
from app.core.exceptions import BadRequestError
from app.services.tenant_payment_method_service import (
    PROVIDER_REQUIRED_CREDENTIALS,
    TenantPaymentMethodService,
    _CRED_FIELDS,
)


class TestRequiredCredentials:
    def test_paystack_requires_secret_key(self):
        assert "secret_key" in PROVIDER_REQUIRED_CREDENTIALS[PaymentProvider.PAYSTACK]

    def test_manual_has_no_required_credentials(self):
        assert PROVIDER_REQUIRED_CREDENTIALS[PaymentProvider.MANUAL] == tuple()


class TestCredFieldMap:
    def test_has_secret_key(self):
        assert _CRED_FIELDS["secret_key"] == "secret_key_encrypted"

    def test_has_webhook_secret(self):
        assert _CRED_FIELDS["webhook_secret"] == "webhook_secret_encrypted"


class TestProviderChannelValidation:
    def test_gateway_requires_real_provider(self):
        svc = TenantPaymentMethodService(MagicMock())
        with pytest.raises(BadRequestError):
            svc._validate_provider_for_channel(
                PaymentChannel.GATEWAY, PaymentProvider.MANUAL
            )

    def test_cashier_requires_manual(self):
        svc = TenantPaymentMethodService(MagicMock())
        with pytest.raises(BadRequestError):
            svc._validate_provider_for_channel(
                PaymentChannel.CASHIER, PaymentProvider.PAYSTACK
            )

    def test_gateway_with_paystack_ok(self):
        svc = TenantPaymentMethodService(MagicMock())
        # Should not raise.
        svc._validate_provider_for_channel(
            PaymentChannel.GATEWAY, PaymentProvider.PAYSTACK
        )


class TestUnknownCredentialsRejected:
    def test_unknown_credential_field_rejected(self):
        svc = TenantPaymentMethodService(MagicMock())
        with pytest.raises(BadRequestError):
            svc._validate_credentials(PaymentProvider.PAYSTACK, {"weird": "x"})

    def test_known_credentials_accepted(self):
        svc = TenantPaymentMethodService(MagicMock())
        svc._validate_credentials(PaymentProvider.PAYSTACK, {"secret_key": "x"})
