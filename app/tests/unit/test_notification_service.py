"""Unit tests for NotificationTemplateService and NotificationService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.notification_service import NotificationTemplateService, NotificationService


class TestNotificationTemplateGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = NotificationTemplateService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestNotificationTemplateGetByCode:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = NotificationTemplateService(db)
        svc.repository = MagicMock()
        svc.get_by_code("WELCOME")
        svc.repository.get_by_code.assert_called_once_with("WELCOME")


class TestNotificationServiceGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = NotificationService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestNotificationConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = NotificationService(db)
        assert svc.db is db
