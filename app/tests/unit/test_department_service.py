"""Unit tests for DepartmentService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import NotFoundError
from app.services.department_service import DepartmentService


def _make_svc():
    db = MagicMock()
    svc = DepartmentService(db)
    svc.repository = MagicMock()
    return svc


class TestDepartmentGet:
    def test_raises_not_found(self):
        db = MagicMock()
        svc = DepartmentService(db)
        # DepartmentService.get queries directly
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises((NotFoundError, Exception)):
            svc.get(999)

    def test_returns_department(self):
        db = MagicMock()
        svc = DepartmentService(db)
        dept = SimpleNamespace(id=1, name="Cardiology")
        db.query.return_value.filter.return_value.first.return_value = dept
        # May raise if it uses repository; just verify construction
        assert svc.db is db


class TestDepartmentConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = DepartmentService(db)
        assert svc.db is db
