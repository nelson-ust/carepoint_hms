"""Unit tests for ProcedureCatalogService and ProcedureOrderService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.procedure_service import ProcedureCatalogService, ProcedureOrderService


class TestProcedureCatalogGet:
    def test_delegates_to_repository(self):
        svc = ProcedureCatalogService(MagicMock())
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestProcedureCatalogCreate:
    def test_creates_and_commits(self):
        db = MagicMock()
        svc = ProcedureCatalogService(db)
        svc.repository = MagicMock()
        cat = SimpleNamespace(id=1)
        svc.repository.create.return_value = cat
        payload = MagicMock()
        svc.create(payload)
        db.commit.assert_called_once()


class TestProcedureCatalogSoftDelete:
    def test_soft_deletes_and_commits(self):
        db = MagicMock()
        svc = ProcedureCatalogService(db)
        svc.repository = MagicMock()
        cat = SimpleNamespace(id=1)
        svc.repository.get_required_by_id.return_value = cat
        svc.soft_delete(1)
        db.commit.assert_called_once()


class TestProcedureOrderGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = ProcedureOrderService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)
