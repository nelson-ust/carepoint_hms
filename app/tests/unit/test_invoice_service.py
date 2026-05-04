"""Unit tests for InvoiceService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.invoice_service import InvoiceService


class TestInvoiceServiceGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = InvoiceService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestInvoiceListForVisit:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = InvoiceService(db)
        svc.repository = MagicMock()
        svc.list_for_visit(1)
        svc.repository.list_for_visit.assert_called_once_with(1)


class TestInvoiceConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = InvoiceService(db)
        assert svc.db is db
