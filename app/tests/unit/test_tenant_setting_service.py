"""Unit tests for TenantSettingService."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.core.exceptions import BadRequestError
from app.services.tenant_setting_service import (
    DEFAULT_NOTIFICATION_CHANNELS,
    SUPPORTED_CHANNELS,
    TenantSettingService,
)


class TestSupportedChannels:
    def test_includes_all_known_channels(self):
        assert {"in_app", "email", "sms", "whatsapp", "push"} == set(SUPPORTED_CHANNELS)


class TestDefaultNotificationChannels:
    def test_invoice_created_routed(self):
        assert "invoice.created" in DEFAULT_NOTIFICATION_CHANNELS

    def test_appointment_reminder_routed(self):
        assert "appointment.reminder" in DEFAULT_NOTIFICATION_CHANNELS

    def test_each_uses_supported_channels(self):
        for event, channels in DEFAULT_NOTIFICATION_CHANNELS.items():
            for c in channels:
                assert c in SUPPORTED_CHANNELS, f"unknown channel for {event}: {c}"


class TestValidationHelpers:
    def test_validate_approval_rejects_non_dict(self):
        svc = TenantSettingService(MagicMock())
        with pytest.raises(BadRequestError):
            svc._validate_approval_workflows("not-a-dict")  # type: ignore[arg-type]

    def test_validate_notification_channels_rejects_unknown_channel(self):
        svc = TenantSettingService(MagicMock())
        with pytest.raises(BadRequestError):
            svc._validate_notification_channels(
                {"appointment.reminder": ["invalid_channel"]}
            )

    def test_validate_notification_channels_requires_list(self):
        svc = TenantSettingService(MagicMock())
        with pytest.raises(BadRequestError):
            svc._validate_notification_channels(
                {"appointment.reminder": "email"}  # type: ignore[dict-item]
            )

    def test_validate_approval_workflows_each_value_must_be_dict(self):
        svc = TenantSettingService(MagicMock())
        with pytest.raises(BadRequestError):
            svc._validate_approval_workflows({"action.x": "yes"})


class TestServiceConstruction:
    def test_records_session_and_tenant(self):
        db = MagicMock()
        svc = TenantSettingService(db, tenant_code="acme")
        assert svc.db is db
        assert svc.tenant_code == "acme"
