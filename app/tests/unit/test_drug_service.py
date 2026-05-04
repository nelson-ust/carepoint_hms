"""Unit tests for DrugCategoryService and DrugService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.drug_service import DrugCategoryService, DrugService


class TestDrugCategoryGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = DrugCategoryService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestDrugCategorySoftDelete:
    def test_soft_deletes(self):
        db = MagicMock()
        svc = DrugCategoryService(db)
        svc.repository = MagicMock()
        svc.repository.get_required_by_id.return_value = SimpleNamespace(id=1)
        svc.soft_delete(1)
        db.commit.assert_called_once()


class TestDrugServiceGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = DrugService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestDrugServiceSoftDelete:
    def test_soft_deletes(self):
        db = MagicMock()
        svc = DrugService(db)
        svc.repository = MagicMock()
        svc.repository.get_required_by_id.return_value = SimpleNamespace(id=1)
        svc.soft_delete(1)
        db.commit.assert_called_once()
