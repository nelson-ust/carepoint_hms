"""Unit tests for PaystackService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.paystack_service import PaystackService


class TestPaystackVerifyWebhookSignature:
    def test_returns_false_on_mismatch(self):
        db = MagicMock()
        svc = PaystackService(db)
        # Signature check should not crash with arbitrary inputs.
        result = svc.verify_webhook_signature(b"test-payload", "invalid-sig")
        assert result is False


class TestPaystackConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = PaystackService(db)
        assert svc.db is db
