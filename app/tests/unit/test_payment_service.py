"""Unit tests for PaymentService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.payment_service import PaymentService


class TestPaymentServiceGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = PaymentService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestPaymentListForInvoice:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = PaymentService(db)
        svc.repository = MagicMock()
        svc.list_for_invoice(1)
        svc.repository.list_for_invoice.assert_called_once_with(1)


class TestPaymentConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = PaymentService(db)
        assert svc.db is db
