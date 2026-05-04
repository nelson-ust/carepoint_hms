"""Unit tests for LabCatalogService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.lab_service import LabCatalogService


class TestLabCatalogGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = LabCatalogService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestLabCatalogCreate:
    def test_creates_and_commits(self):
        db = MagicMock()
        svc = LabCatalogService(db)
        svc.repository = MagicMock()
        cat = SimpleNamespace(id=1)
        svc.repository.create.return_value = cat
        payload = MagicMock()
        svc.create(payload)
        db.commit.assert_called_once()


class TestLabCatalogSoftDelete:
    def test_soft_deletes(self):
        db = MagicMock()
        svc = LabCatalogService(db)
        svc.repository = MagicMock()
        svc.repository.get_required_by_id.return_value = SimpleNamespace(id=1)
        svc.soft_delete(1)
        db.commit.assert_called_once()


class TestLabCatalogConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = LabCatalogService(db)
        assert svc.db is db
