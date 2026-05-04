"""Unit tests for VisitFlowService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import AlreadyExistsError, BadRequestError, NotFoundError
from app.services.visit_flow_service import VisitFlowService


def _make_svc():
    db = MagicMock()
    svc = VisitFlowService(db)
    svc.repository = MagicMock()
    return svc


class TestGetTemplate:
    def test_raises_not_found(self):
        svc = _make_svc()
        svc.repository.get_template_by_id.return_value = None
        with pytest.raises(NotFoundError, match="template not found"):
            svc.get_template(999)

    def test_returns_template(self):
        svc = _make_svc()
        tmpl = SimpleNamespace(id=1, code="DEFAULT")
        svc.repository.get_template_by_id.return_value = tmpl
        assert svc.get_template(1) is tmpl


class TestCreateTemplate:
    def test_rejects_duplicate_code(self):
        svc = _make_svc()
        svc.repository.template_code_exists.return_value = True
        payload = MagicMock(code="DEFAULT")
        with pytest.raises(AlreadyExistsError, match="code already exists"):
            svc.create_template(payload)


class TestDeleteTemplate:
    def test_raises_not_found(self):
        svc = _make_svc()
        svc.repository.get_template_by_id.return_value = None
        with pytest.raises(NotFoundError):
            svc.delete_template(999)


class TestResolveFlowStepStatus:
    def test_rejects_invalid_status(self):
        svc = _make_svc()
        with pytest.raises(BadRequestError, match="Unsupported"):
            svc._resolve_flow_step_status("BOGUS")

    def test_returns_default_when_none(self):
        from app.core.enums import VisitFlowStepStatus
        svc = _make_svc()
        result = svc._resolve_flow_step_status(None)
        assert result == VisitFlowStepStatus.PENDING


class TestVisitFlowConstruction:
    def test_initializes_with_session(self):
        db = MagicMock()
        svc = VisitFlowService(db)
        assert svc.db is db
