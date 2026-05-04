"""Unit tests for TenantDomainService."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.core.exceptions import BadRequestError
from app.services.tenant_domain_service import (
    TenantDomainService,
    _generate_verification_token,
    _normalize_domain,
)


class TestNormalizeDomain:
    def test_strips_scheme_and_path(self):
        assert _normalize_domain("https://Acme.Carepointhms.com/login") == "acme.carepointhms.com"

    def test_lowercases(self):
        assert _normalize_domain("Acme.Example.COM") == "acme.example.com"

    def test_rejects_empty(self):
        with pytest.raises(BadRequestError):
            _normalize_domain("")

    def test_rejects_bad_format(self):
        with pytest.raises(BadRequestError):
            _normalize_domain("not a domain")


class TestVerificationToken:
    def test_token_has_prefix(self):
        token = _generate_verification_token()
        assert token.startswith("carepoint-verify-")

    def test_token_has_entropy(self):
        a = _generate_verification_token()
        b = _generate_verification_token()
        assert a != b


class TestDomainServiceConstructor:
    def test_constructs_cleanly(self):
        svc = TenantDomainService(MagicMock())
        assert svc.db is not None
