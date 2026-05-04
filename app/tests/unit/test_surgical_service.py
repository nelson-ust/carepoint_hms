"""Unit tests for OperatingTheatreService and SurgicalCatalogService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.surgical_service import OperatingTheatreService, SurgicalCatalogService


class TestOperatingTheatreGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = OperatingTheatreService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestOperatingTheatreCreate:
    def test_creates_and_commits(self):
        db = MagicMock()
        svc = OperatingTheatreService(db)
        svc.repository = MagicMock()
        theatre = SimpleNamespace(id=1)
        svc.repository.create.return_value = theatre
        svc.repository.get_required_by_id.return_value = theatre
        payload = MagicMock()
        svc.create(payload)
        db.commit.assert_called_once()


class TestSurgicalCatalogGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = SurgicalCatalogService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestSurgicalCatalogSoftDelete:
    def test_soft_deletes(self):
        db = MagicMock()
        svc = SurgicalCatalogService(db)
        svc.repository = MagicMock()
        svc.repository.get_required_by_id.return_value = SimpleNamespace(id=1)
        svc.soft_delete(1)
        db.commit.assert_called_once()
