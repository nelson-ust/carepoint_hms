"""Unit tests for RadiologyCatalogService and RadiologyOrderService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.radiology_service import RadiologyCatalogService, RadiologyOrderService


class TestRadiologyCatalogGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = RadiologyCatalogService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestRadiologyCatalogSoftDelete:
    def test_soft_deletes_and_commits(self):
        db = MagicMock()
        svc = RadiologyCatalogService(db)
        svc.repository = MagicMock()
        svc.repository.get_required_by_id.return_value = SimpleNamespace(id=1)
        svc.soft_delete(1)
        db.commit.assert_called_once()


class TestRadiologyOrderGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = RadiologyOrderService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestRadiologyOrderConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = RadiologyOrderService(db)
        assert svc.db is db
