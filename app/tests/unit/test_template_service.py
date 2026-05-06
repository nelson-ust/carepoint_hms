"""Unit tests for TemplateService.

Covers notification template listing/creation, document template
listing/creation (including the ``is_default`` reset behaviour), and
Jinja-based document rendering with happy and unhappy paths.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.services.template_service import TemplateService


def _make_svc():
    db = MagicMock()
    return TemplateService(db), db


class TestNotificationTemplates:
    def test_get_returns_list(self):
        svc, db = _make_svc()
        db.query.return_value.all.return_value = ["t1", "t2"]
        assert svc.get_notification_templates() == ["t1", "t2"]

    def test_create_persists(self):
        svc, db = _make_svc()
        payload = MagicMock()
        # The NotificationTemplate ORM model accepts these columns;
        # the kwargs in model_dump must therefore match them.
        payload.model_dump.return_value = {
            "name": "Notify Tpl",
            "code": "NT",
            "channel": "EMAIL",
            "subject_template": "Hi",
            "body_template": "Hello {{ name }}",
        }
        svc.create_notification_template(payload)
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()


class TestDocumentTemplates:
    def test_get_returns_list(self):
        svc, db = _make_svc()
        db.query.return_value.all.return_value = ["d1"]
        assert svc.get_document_templates() == ["d1"]

    def test_create_resets_existing_default(self):
        svc, db = _make_svc()
        payload = MagicMock()
        payload.is_default = True
        payload.template_type = "INVOICE"
        payload.model_dump.return_value = {
            "code": "DT",
            "template_type": "INVOICE",
            "is_default": True,
            "body_html": "<p>{{x}}</p>",
        }
        svc.create_document_template(payload)
        # First call: query(DocumentTemplate).filter(...).update(...)
        update_chain = db.query.return_value.filter.return_value
        update_chain.update.assert_called_once_with({"is_default": False})
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_create_skips_default_reset_when_not_default(self):
        svc, db = _make_svc()
        payload = MagicMock()
        payload.is_default = False
        payload.template_type = "INVOICE"
        payload.model_dump.return_value = {
            "code": "DT",
            "template_type": "INVOICE",
            "is_default": False,
            "body_html": "<p>x</p>",
        }
        svc.create_document_template(payload)
        # query() shouldn't be invoked for the update path
        db.query.assert_not_called()
        db.add.assert_called_once()


class TestRenderDocument:
    def test_rejects_unknown_template(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundError, match="Template with code"):
            svc.render_document("MISSING", {"x": 1})

    def test_renders_happy_path(self):
        svc, db = _make_svc()
        record = SimpleNamespace(code="GREET", body_html="Hello {{ name }}!")
        db.query.return_value.filter.return_value.first.return_value = record
        out = svc.render_document("GREET", {"name": "World"})
        assert out == "Hello World!"

    def test_wraps_render_errors_in_bad_request(self):
        svc, db = _make_svc()
        # An invalid Jinja template raises during Template construction or render
        record = SimpleNamespace(code="BAD", body_html="{% bogus %}")
        db.query.return_value.filter.return_value.first.return_value = record
        with pytest.raises(BadRequestError, match="Error rendering template"):
            svc.render_document("BAD", {})

    @patch("app.services.template_service.Template")
    def test_render_uses_jinja_template(self, mock_template_cls):
        svc, db = _make_svc()
        record = SimpleNamespace(code="X", body_html="body")
        db.query.return_value.filter.return_value.first.return_value = record
        mock_template_cls.return_value.render.return_value = "OK"
        result = svc.render_document("X", {"k": "v"})
        assert result == "OK"
        mock_template_cls.assert_called_once_with("body")
        mock_template_cls.return_value.render.assert_called_once_with(k="v")


class TestConstruction:
    def test_holds_session(self):
        svc, db = _make_svc()
        assert svc.db is db
