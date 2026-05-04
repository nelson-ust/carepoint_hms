"""Unit tests for BillableServiceService and BillingService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.billing_service import BillableServiceService, BillingService


class TestBillableServiceGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = BillableServiceService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestBillableServiceCreate:
    def test_creates_and_commits(self):
        db = MagicMock()
        svc = BillableServiceService(db)
        svc.repository = MagicMock()
        created = SimpleNamespace(id=1)
        svc.repository.create.return_value = created
        payload = MagicMock()
        svc.create(payload)
        db.commit.assert_called_once()


class TestBillableServiceSoftDelete:
    def test_soft_deletes(self):
        db = MagicMock()
        svc = BillableServiceService(db)
        svc.repository = MagicMock()
        svc.repository.get_required_by_id.return_value = SimpleNamespace(id=1)
        svc.soft_delete(1)
        db.commit.assert_called_once()


class TestBillingServiceGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = BillingService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestBillingServiceConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = BillingService(db)
        assert svc.db is db
